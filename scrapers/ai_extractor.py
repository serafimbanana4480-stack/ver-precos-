import json
import logging
import re
from typing import List, Dict, Any, Optional
import httpx
from scrapers.schema import VehicleListing
from config import settings

logger = logging.getLogger(__name__)

class AIExtractor:
    def __init__(self):
        self.ollama_url = f"{settings.ollama_url}/api/generate"
        self.model = settings.ai_scraper_model
        self.timeout = 120.0  # Increased timeout for larger models

    async def extract_from_html(self, html: str, source: str, max_listings: int = 10) -> List[Dict[str, Any]]:
        """
        Extract vehicle listings from HTML using AI.
        """
        logger.info(f"[AI_EXTRACT] Extracting up to {max_listings} listings from {source}")
        
        # Clean HTML to reduce tokens - extract only relevant parts
        from bs4 import BeautifulSoup
        soup = BeautifulSoup(html, 'lxml')
        
        # Remove scripts, styles, and non-essential elements
        for tag in soup(['script', 'style', 'nav', 'footer', 'header', 'aside']):
            tag.decompose()
        
        # Get text content with structure preserved
        clean_html = str(soup)[:25000]  # Increased limit for better extraction
        
        prompt = f"""You are a web scraping assistant. Extract vehicle listings from this HTML from {source}.

IMPORTANT: Return ONLY valid JSON. No explanations, no markdown code blocks.

Extract these fields for each listing:
- source: The website source (e.g. "standvirtual", "olx", "autosapo", "custojusto")
- brand: Vehicle brand (e.g. "BMW", "Mercedes-Benz", "Volkswagen")
- model: Vehicle model (e.g. "Série 3", "Classe C", "Golf")
- vehicle_type: string ("carros", "motos")
- seller_type: string ("particular", "profissional")
- title: Full listing title
- price: Numeric price value only (e.g. 12500)
- url: Full URL to the listing
- year: Year as integer (e.g. 2020)
- km: Kilometers as integer (e.g. 50000)
- fuel_type: Fuel type if available
- transmission: Transmission type if available
- location: City/location if available
- images: List of image URLs if available
- is_national: true if "nacional", false if "importado" or None
- num_owners: integer representing number of previous owners if mentioned (e.g. 1 para "único dono")
- warranty_months: integer representing months of warranty if mentioned (e.g. 18)
- condition_status: string ("novo", "usado", "danificado")

HTML content:
{clean_html}

Return a JSON array with up to {max_listings} listings:
[{{"source": "...", "brand": "...", "model": "...", "vehicle_type": "...", "seller_type": "...", "title": "...", "price": 0, "url": "...", "year": 0, "km": 0, "fuel_type": "...", "transmission": "...", "location": "...", "images": [], "is_national": null, "num_owners": null, "warranty_months": null, "condition_status": null}}]"""
        
        payload = {
            "model": self.model,
            "prompt": prompt,
            "stream": False,
            "format": "json"
        }
        
        try:
            async with httpx.AsyncClient(timeout=self.timeout) as client:
                response = await client.post(self.ollama_url, json=payload)
                if response.status_code != 200:
                    logger.error(f"[AI_EXTRACT] Ollama error: {response.status_code}")
                    return []
                
                result = response.json()
                raw_text = result.get("response", "")
                
                return self._parse_llm_response(raw_text)
                
        except Exception as e:
            logger.error(f"[AI_EXTRACT] Extraction failed: {e}")
            return []

    def _parse_llm_response(self, raw_text: str) -> List[Dict[str, Any]]:
        """
        Parse the LLM response resiliently, looking for JSON blocks.
        """
        # Try to find a JSON list block first
        list_block = re.search(r'```json\s*(\[[\s\S]*?\])\s*```', raw_text)
        if list_block:
            json_str = list_block.group(1)
        else:
            # Try to find a JSON object block
            dict_block = re.search(r'```json\s*(\{[\s\S]*?\})\s*```', raw_text)
            if dict_block:
                json_str = dict_block.group(1)
            else:
                # Fallback: try to find anything that looks like a JSON list
                json_list = re.search(r'(\[[\s\S]*?\])', raw_text)
                if json_list:
                    json_str = json_list.group(1)
                else:
                    # Fallback: try to find anything that looks like a JSON object
                    json_dict = re.search(r'(\{[\s\S]*?\})', raw_text)
                    if json_dict:
                        json_str = json_dict.group(1)
                    else:
                        json_str = raw_text

        try:
            data = json.loads(json_str)
            if not isinstance(data, list):
                if isinstance(data, dict):
                    data = [data]
                else:
                    return []
            
            # Validate and format each item using our Pydantic schema
            listings = []
            for item in data:
                try:
                    # The Pydantic model handles the formatting quirks via its field_validators
                    listing = VehicleListing(**item)
                    listings.append(listing.model_dump())
                except Exception as ve:
                    logger.warning(f"[AI_EXTRACT] Item validation failed: {ve}")
                    continue
            
            return listings
            
        except json.JSONDecodeError as e:
            logger.error(f"[AI_EXTRACT] JSON decode error: {e}")
            return []

def get_ai_extractor():
    return AIExtractor()

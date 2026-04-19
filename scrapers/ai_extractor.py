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
        self.timeout = 60.0

    async def extract_from_html(self, html: str, source: str, max_listings: int = 10) -> List[Dict[str, Any]]:
        """
        Extract vehicle listings from HTML using AI.
        """
        logger.info(f"[AI_EXTRACT] Extracting up to {max_listings} listings from {source}")
        
        # Clean HTML to reduce tokens
        # In a real scenario, we might use BeautifulSoup to extract only relevant parts
        # For now, let's assume we send a simplified version
        
        prompt = f"""
        Extract the vehicle listings from the following HTML from {source}.
        Return a JSON list of objects. Each object should represent a vehicle listing.
        
        Fields to extract:
        - title
        - price (extract numeric value if possible, e.g. 10500)
        - url
        - year
        - km (mileage)
        - fuel_type
        - transmission
        - location
        - images (list of URLs)
        
        HTML content:
        {html[:10000]}  # Truncate for now to avoid token limits
        
        Return ONLY a JSON block like this:
        ```json
        [
          {{
            "title": "...",
            "price": "...",
            "url": "...",
            ...
          }}
        ]
        ```
        """
        
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

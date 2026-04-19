import re

with open("scrapers/ai_extractor.py", "r", encoding="utf-8") as f:
    content = f.read()

# Add import
import_statement = "from scrapers.schema import VehicleListing\n"
if "from scrapers.schema" not in content:
    content = content.replace("from bs4 import BeautifulSoup", "from bs4 import BeautifulSoup\n" + import_statement)

# We can find the start and end of `_parse_llm_response` and replace it using string split/find.
start_str = "    def _parse_llm_response(self, raw_text: str, source: str) -> List[Dict[str, Any]]:"
end_str = "    def _parse_number_from_string(self, s: str) -> Optional[float]:"

start_idx = content.find(start_str)
end_idx = content.find(end_str)

if start_idx != -1 and end_idx != -1:
    new_method = """    def _parse_llm_response(self, raw_text: str, source: str) -> List[Dict[str, Any]]:
        \"\"\"Parse the LLM response into standardized listings\"\"\"
        
        # Try to find JSON array in the response
        # LLMs sometimes wrap the JSON in markdown code blocks or add reasoning
        # 1. Look for ```json ... ``` blocks
        json_block_match = re.search(r'```json\s*(\[[\s\S]*?\])\s*```', raw_text)
        if json_block_match:
            try:
                raw_listings = json.loads(json_block_match.group(1))
            except json.JSONDecodeError:
                raw_listings = None
        else:
            # 2. Look for any [...] block
            json_match = re.search(r'(\[[\s\S]*\])', raw_text)
            if json_match:
                try:
                    raw_listings = json.loads(json_match.group(1))
                except json.JSONDecodeError:
                    raw_listings = None
            else:
                raw_listings = None

        if not raw_listings:
            logger.warning(f"[AI_EXTRACT] No valid JSON array found in LLM response")
            return []
        
        if not isinstance(raw_listings, list):
            return []
        
        # Normalize each listing
        listings = []
        base_urls = {
            "olx": "https://www.olx.pt",
            "standvirtual": "https://www.standvirtual.com",
            "autosapo": "https://autos.sapo.pt",
            "custojusto": "https://www.custojusto.pt"
        }
        base_url = base_urls.get(source, "")
        
        for item in raw_listings:
            if not isinstance(item, dict):
                continue
            
            # Map alternative field names
            item["title"] = item.get("title") or item.get("name") or ""
            item["location"] = item.get("location") or item.get("localizacao") or ""
            item["fuel"] = item.get("fuel") or item.get("fuel_type") or item.get("combustivel") or ""
            item["transmission"] = item.get("transmission") or item.get("caixa") or ""
            item["km"] = item.get("km") or item.get("mileage") or item.get("quilometros")
            
            url = item.get("url", "") or ""
            if url and not url.startswith("http"):
                url = base_url + url
            item["url"] = url
            
            # Generate stable ID
            item["source_id"] = hashlib.md5(str(url).encode()).hexdigest() if url else ""
            item["raw_data"] = json.dumps(item, ensure_ascii=False)
            
            try:
                # Use Pydantic to validate and coerce data
                listing_obj = VehicleListing(**item)
                
                # Only include listings with at least a title or URL
                if listing_obj.title or listing_obj.url:
                    # Rename fuel back to fuel_type for compatibility with existing code
                    dump = listing_obj.model_dump()
                    dump["fuel_type"] = dump.pop("fuel")
                    listings.append(dump)
            except Exception as e:
                logger.warning(f"[AI_EXTRACT] Failed to parse listing with Pydantic: {e}")
                continue
        
        return listings

"""
    # Fix the double backslashes in the regex patterns above since we used a normal string
    new_method = new_method.replace(r'(\[[\s\S]*?\])\s*```', r'(\[[\s\S]*?\])\s*```')
    new_method = new_method.replace(r'(\[[\s\S]*\])', r'(\[[\s\S]*\])')

    content = content[:start_idx] + new_method + content[end_idx:]

with open("scrapers/ai_extractor.py", "w", encoding="utf-8") as f:
    f.write(content)


import asyncio
import logging
import sys
import os

# Add project root to sys.path
sys.path.append(os.getcwd())

from scrapers.managed_client import get_managed_client
from config import settings

async def main():
    logging.basicConfig(level=logging.INFO)
    client = get_managed_client()
    
    # Test URL - using a simple one first to verify Playwright
    url = "https://www.google.com" 
    print(f"Testing local Playwright fetch for: {url}")
    
    html = await client.get_html(url, source="smoke_test")
    
    if html:
        print(f"SUCCESS: Retrieved {len(html)} bytes of HTML")
        if "google" in html.lower():
            print("Found 'google' in HTML - basic verify PASSED")
    else:
        print("FAILURE: No HTML retrieved")

if __name__ == "__main__":
    asyncio.run(main())

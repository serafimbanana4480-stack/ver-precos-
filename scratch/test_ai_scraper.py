import asyncio
import logging
import sys
import os

# Add project root to sys.path
sys.path.append(os.getcwd())

from scrapers.ai_scraper import get_ai_scraper
from config import settings

async def main():
    logging.basicConfig(level=logging.INFO)
    scraper = get_ai_scraper()
    
    # Verify current model
    print(f"Current model configured: {scraper.model}")
    
    # Test URL
    url = "https://www.olx.pt/carros" 
    print(f"Testing AI scrape for: {url}")
    
    try:
        listings = await scraper.scrape_listings("olx", url, max_listings=2)
        print(f"SUCCESS: Extracted {len(listings)} listings")
        for i, l in enumerate(listings):
            print(f"Listing {i+1}: {l.get('title')} - {l.get('price')}")
    except Exception as e:
        print(f"FAILURE: {e}")

if __name__ == "__main__":
    asyncio.run(main())

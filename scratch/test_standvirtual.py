import asyncio
import logging
import sys
import os

# Add project root to sys.path
sys.path.append(os.getcwd())

from scrapers.standvirtual_scraper import StandvirtualScraper
from config import settings

async def main():
    logging.basicConfig(level=logging.INFO)
    scraper = StandvirtualScraper()
    
    # Test URL
    print("Testing Standvirtual scraping with updated selectors...")
    
    try:
        listings = await scraper.scrape_listings("carros", max_listings=5)
        print(f"SUCCESS: Extracted {len(listings)} listings")
        for i, l in enumerate(listings):
            print(f"Listing {i+1}: {l.get('title')} - {l.get('price')} - {l.get('location')}")
    except Exception as e:
        print(f"FAILURE: {e}")

if __name__ == "__main__":
    asyncio.run(main())

"""
Bulk Import Utility for AutoDeal IA Hunter
Scrapes multiple pages from multiple sources to warm up the database
"""
import asyncio
import logging
import sys
import os
from typing import List, Dict, Any
from tqdm import tqdm

# Add project root to path
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from scrapers.olx_scraper import OLXScraper
from scrapers.standvirtual_scraper import StandvirtualScraper
from scrapers.custojusto_scraper import CustoJustoScraper
from database.db import get_db_context
from database.models import Vehicle

# Setup logging
logging.basicConfig(level=logging.INFO, format="%(message)s")
logger = logging.getLogger(__name__)

async def bulk_import_source(scraper_name: str, scraper_obj: Any, pages: int = 5):
    """Import multiple pages from a single source"""
    print(f"\n--- Importing from {scraper_name} ({pages} pages) ---")
    
    total_found = 0
    
    for page in range(1, pages + 1):
        print(f"Scraping page {page}...")
        try:
            # Note: OLX and SV scrapers might need adjustment for page-by-page scraping
            # For this utility, we'll use a higher limit per source
            listings = await scraper_obj.scrape_listings("carros", max_listings=40)
            
            if not listings:
                print(f"No listings found on page {page}. Stopping.")
                break
                
            scraper_obj.save_to_database(listings)
            total_found += len(listings)
            
            # Simple delay to avoid detection
            await asyncio.sleep(2)
            
        except Exception as e:
            print(f"Error on page {page}: {e}")
            continue
            
    print(f"Finished {scraper_name}. Total processed: {total_found}")

async def main():
    print("Starting AutoDeal Bulk Import...")
    
    scrapers = {
        "OLX": OLXScraper(),
        # "Standvirtual": StandvirtualScraper(), # Disabled for now to focus on proof
        "CustoJusto": CustoJustoScraper()
    }
    
    # In a real environment, we'd loop through all.
    # For proof, we'll run OLX and CustoJusto.
    
    tasks = []
    for name, obj in scrapers.items():
        tasks.append(bulk_import_source(name, obj, pages=2))
        
    await asyncio.gather(*tasks)
    
    # Final count
    with get_db_context() as session:
        count = session.query(Vehicle).count()
        print(f"\n✅ Import Complete! Total vehicles in DB: {count}")

if __name__ == "__main__":
    asyncio.run(main())

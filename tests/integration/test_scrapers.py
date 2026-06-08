"""
Integration test for scrapers.
"""
import pytest
from scrapers.olx_scraper import OLXScraper


@pytest.mark.integration
async def test_olx_scraper():
    """Test OLX scraper integration."""
    scraper = OLXScraper()
    listings = await scraper.scrape(max_listings=5)
    assert len(listings) >= 0

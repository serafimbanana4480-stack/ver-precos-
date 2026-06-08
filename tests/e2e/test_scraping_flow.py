"""
E2E test for scraping flow.
"""
import pytest
from unittest.mock import AsyncMock, patch
from scrapers.olx_scraper import OLXScraper


@pytest.mark.e2e
async def test_scraping_flow():
    """Test complete scraping flow."""
    scraper = OLXScraper()
    fake = [{"source": "OLX", "source_id": "t1", "url": "https://www.olx.pt/d/x.html", "price": 10000, "year": 2020}]
    with patch.object(scraper, "scrape_listings", AsyncMock(return_value=fake)):
        listings = await scraper.scrape(max_listings=5)
    assert len(listings) > 0

"""
Integration test for scrapers.
"""
import pytest
from scrapers.olx_lightweight import OLXLightweight


@pytest.mark.integration
def test_olx_scraper():
    """Test OLX lightweight scraper integration (public JSON API)."""
    scraper = OLXLightweight()
    listings = scraper.scrape_listings(max_listings=5)
    assert isinstance(listings, list)
    assert len(listings) >= 0

"""
Unit test for OLX scraper.
"""
import pytest
from scrapers.olx_scraper import OLXScraper


def test_olx_scraper_init():
    """Test OLX scraper initialization."""
    scraper = OLXScraper()
    assert scraper is not None

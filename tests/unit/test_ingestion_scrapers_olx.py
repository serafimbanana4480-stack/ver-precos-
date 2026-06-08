"""
Unit test for ingestion scrapers OLX.
"""
import pytest
from ingestion.scrapers.olx import OLXScraper


def test_olx_scraper_init():
    """Test OLX scraper initialization."""
    scraper = OLXScraper()
    assert scraper is not None

"""
Unit test for Standvirtual scraper.
"""
import pytest
from scrapers.standvirtual_scraper import StandvirtualScraper


def test_standvirtual_scraper_init():
    """Test Standvirtual scraper initialization."""
    scraper = StandvirtualScraper()
    assert scraper is not None

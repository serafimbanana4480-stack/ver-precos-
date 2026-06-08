"""
Unit test for Imovirtual scraper.
"""
import pytest
from scrapers.imovirtual_scraper import ImovirtualScraper


def test_imovirtual_scraper_init():
    """Test Imovirtual scraper initialization."""
    scraper = ImovirtualScraper()
    assert scraper is not None

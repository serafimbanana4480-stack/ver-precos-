"""
Unit test for CustoJusto scraper.
"""
import pytest
from scrapers.custojusto_scraper import CustoJustoScraper


def test_custojusto_scraper_init():
    """Test CustoJusto scraper initialization."""
    scraper = CustoJustoScraper()
    assert scraper is not None

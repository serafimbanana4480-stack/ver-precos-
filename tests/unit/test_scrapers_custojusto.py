"""
Unit test for CustoJusto scraper.
"""
import pytest
from scrapers.custojusto_scraper import CustoJustoScraper


def test_custojusto_scraper_init():
    """Test CustoJusto scraper initialization."""
    scraper = CustoJustoScraper()
    assert scraper is not None


def test_custojusto_does_not_invent_year_when_title_has_no_year():
    scraper = CustoJustoScraper()

    _brand, _model, year = scraper._parse_title("BMW Serie 3")

    assert year is None

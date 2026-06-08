"""
Unit test for app dependencies scrapers.
"""
import pytest
from app.dependencies.scrapers import get_scraper


def test_get_scraper():
    """Test get_scraper function."""
    scraper = get_scraper()
    assert scraper is not None

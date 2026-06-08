"""
Unit test for AutoSapo scraper.
"""
import pytest
from scrapers.autosapo_scraper import AutoSapoScraper


def test_autosapo_scraper_init():
    """Test AutoSapo scraper initialization."""
    scraper = AutoSapoScraper()
    assert scraper is not None

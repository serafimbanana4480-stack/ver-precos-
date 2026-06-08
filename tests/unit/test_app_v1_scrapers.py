"""
Unit test for app v1 scrapers.
"""
import pytest
from app.api.v1.endpoints.scrapers import run_scraper


def test_run_scraper():
    """Test run_scraper endpoint."""
    result = run_scraper()
    assert result is not None

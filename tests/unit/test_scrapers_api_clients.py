"""
Unit test for scrapers API clients.
"""
import pytest
from scrapers.api_clients import APIClient


def test_api_client_init():
    """Test API client initialization."""
    client = APIClient()
    assert client is not None

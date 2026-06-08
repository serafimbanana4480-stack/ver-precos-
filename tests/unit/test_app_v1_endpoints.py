"""
Unit test for app v1 endpoints.
"""
import pytest
from app.api.v1.endpoints.listings import get_listings


def test_get_listings():
    """Test get_listings endpoint."""
    result = get_listings()
    assert result is not None

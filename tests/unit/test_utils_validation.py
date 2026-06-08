"""
Unit test for utils validation.
"""
import pytest
from utils.data_validation import validate_listing


def test_validate_listing():
    """Test listing validation."""
    listing = {
        "price": 15000,
        "year": 2020,
        "url": "https://www.olx.pt/d/anuncio/test-123.html",
        "vehicle_type": "car",
    }
    result = validate_listing(listing)
    assert result is True

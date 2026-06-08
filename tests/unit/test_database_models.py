"""
Unit test for database models.
"""
import pytest
from database.models import Listing


def test_listing_model():
    """Test listing model."""
    listing = Listing()
    assert listing is not None

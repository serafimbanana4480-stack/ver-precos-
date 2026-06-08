"""
Unit test for app schemas.
"""
import pytest
from app.schemas.listing import ListingSchema


def test_listing_schema_init():
    """Test listing schema initialization."""
    schema = ListingSchema()
    assert schema is not None

"""
Unit test for scrapers schema.
"""
import pytest
from scrapers.schema import ListingSchema


def test_listing_schema():
    """Test listing schema."""
    schema = ListingSchema()
    assert schema is not None

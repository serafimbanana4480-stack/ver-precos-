"""
Unit test for app services listing service.
"""
import pytest
from app.services.listing_service import ListingService


def test_listing_service_init():
    """Test listing service initialization."""
    service = ListingService()
    assert service is not None

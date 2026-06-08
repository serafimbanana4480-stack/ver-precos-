"""
Unit test for app routers listings.
"""
import pytest
from app.routers.listings import ListingsRouter


def test_listings_router_init():
    """Test listings router initialization."""
    router = ListingsRouter()
    assert router is not None

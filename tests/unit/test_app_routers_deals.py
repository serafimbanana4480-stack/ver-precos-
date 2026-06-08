"""
Unit test for app routers deals.
"""
import pytest
from app.routers.deals import DealsRouter


def test_deals_router_init():
    """Test deals router initialization."""
    router = DealsRouter()
    assert router is not None

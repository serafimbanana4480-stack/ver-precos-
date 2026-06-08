"""
Unit test for app routers health.
"""
import pytest
from app.routers.health import HealthRouter


def test_health_router_init():
    """Test health router initialization."""
    router = HealthRouter()
    assert router is not None

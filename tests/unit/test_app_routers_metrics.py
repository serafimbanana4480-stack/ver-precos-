"""
Unit test for app routers metrics.
"""
import pytest
from app.routers.metrics import MetricsRouter


def test_metrics_router_init():
    """Test metrics router initialization."""
    router = MetricsRouter()
    assert router is not None

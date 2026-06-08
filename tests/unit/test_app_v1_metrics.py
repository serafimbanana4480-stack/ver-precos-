"""
Unit test for app v1 metrics.
"""
import pytest
from app.api.v1.endpoints.metrics import get_metrics


def test_get_metrics():
    """Test get_metrics endpoint."""
    result = get_metrics()
    assert result is not None

"""
Unit test for app v1 health.
"""
import pytest
from app.api.v1.endpoints.health import health_check


def test_health_check():
    """Test health_check endpoint."""
    result = health_check()
    assert result is not None

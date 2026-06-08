"""
Unit test for observability monitoring.
"""
import pytest
from observability.monitoring.health import HealthChecker


def test_health_checker_init():
    """Test health checker initialization."""
    checker = HealthChecker()
    assert checker is not None

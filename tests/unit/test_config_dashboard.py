"""
Unit test for config dashboard.
"""
import pytest
from config.dashboard_config import DashboardConfig


def test_dashboard_config_init():
    """Test dashboard config initialization."""
    config = DashboardConfig()
    assert config is not None

"""
Unit test for config monitoring.
"""
import pytest
from config.monitoring_config import MonitoringConfig


def test_monitoring_config_init():
    """Test monitoring config initialization."""
    config = MonitoringConfig()
    assert config is not None

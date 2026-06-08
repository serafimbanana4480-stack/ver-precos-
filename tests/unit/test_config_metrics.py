"""
Unit test for config metrics.
"""
import pytest
from config.metrics_config import MetricsConfig


def test_metrics_config_init():
    """Test metrics config initialization."""
    config = MetricsConfig()
    assert config is not None

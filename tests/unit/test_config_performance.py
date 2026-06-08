"""
Unit test for config performance.
"""
import pytest
from config.performance_config import PerformanceConfig


def test_performance_config_init():
    """Test performance config initialization."""
    config = PerformanceConfig()
    assert config is not None

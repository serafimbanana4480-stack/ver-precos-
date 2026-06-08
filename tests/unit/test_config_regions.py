"""
Unit test for config regions.
"""
import pytest
from config.regions_config import RegionConfig


def test_region_config_init():
    """Test region config initialization."""
    config = RegionConfig()
    assert config is not None

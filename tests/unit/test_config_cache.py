"""
Unit test for config cache.
"""
import pytest
from config.cache_config import CacheConfig


def test_cache_config_init():
    """Test cache config initialization."""
    config = CacheConfig()
    assert config is not None

"""
Unit test for config scrapers.
"""
import pytest
from config.scrapers_config import ScrapersConfig


def test_scrapers_config_init():
    """Test scrapers config initialization."""
    config = ScrapersConfig()
    assert config is not None

"""
Unit test for config API.
"""
import pytest
from config.api_config import APIConfig


def test_api_config_init():
    """Test API config initialization."""
    config = APIConfig()
    assert config is not None

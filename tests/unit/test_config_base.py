"""
Unit test for config base.
"""
import pytest
from config.base import BaseConfig


def test_base_config_init():
    """Test base config initialization."""
    config = BaseConfig()
    assert config is not None

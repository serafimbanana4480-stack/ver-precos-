"""
Unit test for config validation.
"""
import pytest
from config.validation_config import ValidationConfig


def test_validation_config_init():
    """Test validation config initialization."""
    config = ValidationConfig()
    assert config is not None

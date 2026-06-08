"""
Unit test for config ML.
"""
import pytest
from config.ml_config import MLConfig


def test_ml_config_init():
    """Test ML config initialization."""
    config = MLConfig()
    assert config is not None

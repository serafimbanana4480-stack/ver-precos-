"""
Unit test for config logging.
"""
import pytest
from config.logging_config import LoggingConfig


def test_logging_config_init():
    """Test logging config initialization."""
    config = LoggingConfig()
    assert config is not None

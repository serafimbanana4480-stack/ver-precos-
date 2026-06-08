"""
Unit test for config security.
"""
import pytest
from config.security_config import SecurityConfig


def test_security_config_init():
    """Test security config initialization."""
    config = SecurityConfig()
    assert config is not None

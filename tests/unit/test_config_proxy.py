"""
Unit test for config proxy.
"""
import pytest
from config.proxy_config import ProxyConfig


def test_proxy_config_init():
    """Test proxy config initialization."""
    config = ProxyConfig()
    assert config is not None

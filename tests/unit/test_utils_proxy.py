"""
Unit test for utils proxy.
"""
import pytest
from utils.proxy_manager import ProxyManager


def test_proxy_manager():
    """Test proxy manager."""
    manager = ProxyManager()
    proxy = manager.get_proxy()
    assert proxy is not None

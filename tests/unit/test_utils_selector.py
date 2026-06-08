"""
Unit test for utils selector.
"""
import pytest
from utils.selector_manager import SelectorManager


def test_selector_manager():
    """Test selector manager."""
    manager = SelectorManager()
    selector = manager.get_selector("olx")
    assert selector is not None

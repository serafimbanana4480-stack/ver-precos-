"""
Unit test for utils helpers.
"""
import pytest
from utils.helpers import format_price


def test_format_price():
    """Test price formatting."""
    result = format_price(15000)
    assert result == "€15,000"

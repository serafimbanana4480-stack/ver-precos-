"""
Unit test for app v1 deals.
"""
import pytest
from app.api.v1.endpoints.deals import get_deals


def test_get_deals():
    """Test get_deals endpoint."""
    result = get_deals()
    assert result is not None

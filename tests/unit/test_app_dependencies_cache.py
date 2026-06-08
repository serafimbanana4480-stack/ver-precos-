"""
Unit test for app dependencies cache.
"""
import pytest
from app.dependencies.cache import get_cache


def test_get_cache():
    """Test get_cache function."""
    cache = get_cache()
    assert cache is not None

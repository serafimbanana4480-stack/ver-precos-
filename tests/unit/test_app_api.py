"""
Unit test for app API.
"""
import pytest
from app.api.main import API


def test_api_init():
    """Test API initialization."""
    api = API()
    assert api is not None

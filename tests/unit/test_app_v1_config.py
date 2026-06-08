"""
Unit test for app v1 config.
"""
import pytest
from app.api.v1.endpoints.config import get_config


def test_get_config():
    """Test get_config endpoint."""
    result = get_config()
    assert result is not None

"""
Unit test for core settings.
"""
import pytest
from core.settings import Settings


def test_settings_init():
    """Test settings initialization."""
    settings = Settings()
    assert settings is not None

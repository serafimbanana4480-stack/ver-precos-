"""
Unit test for config storage.
"""
import pytest
from config.storage_config import StorageConfig


def test_storage_config_init():
    """Test storage config initialization."""
    config = StorageConfig()
    assert config is not None

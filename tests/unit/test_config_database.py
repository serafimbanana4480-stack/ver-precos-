"""
Unit test for config database.
"""
import pytest
from config.database_config import DatabaseConfig


def test_database_config_init():
    """Test database config initialization."""
    config = DatabaseConfig()
    assert config is not None

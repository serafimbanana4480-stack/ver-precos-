"""
Unit test for ingestion storage storage.
"""
import pytest
from ingestion.storage.storage import Storage


def test_storage_init():
    """Test storage initialization."""
    storage = Storage()
    assert storage is not None

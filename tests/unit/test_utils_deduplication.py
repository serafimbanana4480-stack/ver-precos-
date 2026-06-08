"""
Unit test for utils deduplication.
"""
import pytest
from utils.deduplication import Deduplicator


def test_deduplicator():
    """Test deduplicator."""
    dedup = Deduplicator()
    result = dedup.is_duplicate("test_key", "test_value")
    assert result is False

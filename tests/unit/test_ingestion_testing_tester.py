"""
Unit test for ingestion testing tester.
"""
import pytest
from ingestion.testing.tester import Tester


def test_tester_init():
    """Test tester initialization."""
    tester = Tester()
    assert tester is not None

"""
Unit test for app dependencies queue.
"""
import pytest
from app.dependencies.queue import get_queue


def test_get_queue():
    """Test get_queue function."""
    queue = get_queue()
    assert queue is not None

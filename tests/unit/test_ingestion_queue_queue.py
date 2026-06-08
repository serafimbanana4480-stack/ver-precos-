"""
Unit test for ingestion queue queue.
"""
import pytest
from ingestion.queue.queue import Queue


def test_queue_init():
    """Test queue initialization."""
    queue = Queue()
    assert queue is not None

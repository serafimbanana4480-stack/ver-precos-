"""
Unit test for config queue.
"""
import pytest
from config.queue_config import QueueConfig


def test_queue_config_init():
    """Test queue config initialization."""
    config = QueueConfig()
    assert config is not None

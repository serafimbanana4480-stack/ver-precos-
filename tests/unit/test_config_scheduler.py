"""
Unit test for config scheduler.
"""
import pytest
from config.scheduler_config import SchedulerConfig


def test_scheduler_config_init():
    """Test scheduler config initialization."""
    config = SchedulerConfig()
    assert config is not None

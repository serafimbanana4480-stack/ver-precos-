"""
Unit test for ingestion monitoring monitor.
"""
import pytest
from ingestion.monitoring.monitor import Monitor


def test_monitor_init():
    """Test monitor initialization."""
    monitor = Monitor()
    assert monitor is not None

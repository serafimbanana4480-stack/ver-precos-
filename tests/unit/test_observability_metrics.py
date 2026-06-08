"""
Unit test for observability metrics.
"""
import pytest
from observability.metrics.collector import MetricsCollector


def test_metrics_collector_init():
    """Test metrics collector initialization."""
    collector = MetricsCollector()
    assert collector is not None

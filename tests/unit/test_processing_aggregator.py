"""
Unit test for processing aggregator.
"""
import pytest
from processing.aggregator.aggregator import DataAggregator


def test_data_aggregator_init():
    """Test data aggregator initialization."""
    aggregator = DataAggregator()
    assert aggregator is not None

"""
Unit test for utils observability.
"""
import pytest
from utils.observability import Observability


def test_observability():
    """Test observability."""
    obs = Observability()
    result = obs.get_metrics()
    assert result is not None

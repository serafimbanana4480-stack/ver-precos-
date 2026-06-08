"""
Unit test for valuation predict.
"""
import pytest
from valuation.predict import Predictor


def test_predictor_init():
    """Test predictor initialization."""
    predictor = Predictor()
    assert predictor is not None

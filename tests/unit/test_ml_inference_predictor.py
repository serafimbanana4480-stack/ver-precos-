"""
Unit test for ML inference predictor.
"""
import pytest
from ml.inference.predictor import Predictor


def test_predictor_init():
    """Test predictor initialization."""
    predictor = Predictor()
    assert predictor is not None

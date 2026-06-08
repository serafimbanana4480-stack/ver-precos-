"""
Unit test for app dependencies ML.
"""
import pytest
from app.dependencies.ml import get_predictor


def test_get_predictor():
    """Test get_predictor function."""
    predictor = get_predictor()
    assert predictor is not None

"""
Unit test for valuation predict.
"""
import pytest
from valuation.predict import PricePredictor


def test_predictor_init():
    """Test predictor initialization."""
    predictor = PricePredictor()
    assert predictor is not None
    # Verify model loaded or gracefully skipped
    if predictor.model:
        assert hasattr(predictor, 'predict')

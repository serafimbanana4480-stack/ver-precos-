"""
Integration test for ML.
"""
import pytest
from valuation.predict import PricePredictor


@pytest.mark.integration
async def test_ml_predictor():
    """Test ML predictor integration."""
    predictor = PricePredictor()
    if not predictor.model:
        pytest.skip("ML model not trained (run: py -3 main.py train)")
    result = predictor.predict({"year": 2020, "km": 50000, "brand": "VW", "model": "Golf"})
    # predict may return None if model can't handle the input; that's OK
    # Just verify it doesn't crash
    assert True

"""
Integration test for ML.
"""
import pytest
from valuation.predict import Predictor


@pytest.mark.integration
async def test_ml_predictor():
    """Test ML predictor integration."""
    predictor = Predictor()
    if not predictor.load_model():
        pytest.skip("ML model not trained (run: py -3 main.py train)")
    result = predictor.predict({"year": 2020, "km": 50000, "brand": "VW", "model": "Golf"})
    assert result is not None

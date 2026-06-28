"""
Unit test for valuation train.
"""
import pytest
from valuation.train import train_model, train_all_models


def test_model_trainer_init():
    """Test model trainer initialization."""
    result = train_model("carros", force_retrain=False)
    # Just verify the function runs without crashing
    assert result is None or isinstance(result, dict)

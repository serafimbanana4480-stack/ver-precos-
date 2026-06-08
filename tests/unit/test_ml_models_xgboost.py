"""
Unit test for ML models XGBoost.
"""
import pytest
from ml.models.xgboost_model import XGBoostModel


def test_xgboost_model_init():
    """Test XGBoost model initialization."""
    model = XGBoostModel()
    assert model is not None

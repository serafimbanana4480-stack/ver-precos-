"""
Unit test for valuation train.
"""
import pytest
from valuation.train_model import ModelTrainer


def test_model_trainer_init():
    """Test model trainer initialization."""
    trainer = ModelTrainer()
    assert trainer is not None

"""
Unit test for ML testing evaluator.
"""
import pytest
from ml.testing.evaluator import ModelEvaluator


def test_model_evaluator_init():
    """Test model evaluator initialization."""
    evaluator = ModelEvaluator()
    assert evaluator is not None

"""
Unit test for ML testing cross validation.
"""
import pytest
from ml.testing.cross_validation import CrossValidation


def test_cross_validation_init():
    """Test cross validation initialization."""
    cv = CrossValidation()
    assert cv is not None

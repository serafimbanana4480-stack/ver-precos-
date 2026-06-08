"""
Unit test for ML utils features.
"""
import pytest
from ml.utils.features import FeatureEngineer


def test_feature_engineer_init():
    """Test feature engineer initialization."""
    engineer = FeatureEngineer()
    assert engineer is not None

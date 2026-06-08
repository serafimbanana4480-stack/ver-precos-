"""
Unit test for config feature flags.
"""
import pytest
from config.feature_flags_config import FeatureFlagsConfig


def test_feature_flags_config_init():
    """Test feature flags config initialization."""
    config = FeatureFlagsConfig()
    assert config is not None

"""
Unit test for config deal scoring.
"""
import pytest
from config.deal_scoring_config import DealScoringConfig


def test_deal_scoring_config_init():
    """Test deal scoring config initialization."""
    config = DealScoringConfig()
    assert config is not None

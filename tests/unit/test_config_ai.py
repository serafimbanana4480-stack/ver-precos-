"""
Unit test for config AI.
"""
import pytest
from config.ai_config import AIConfig


def test_ai_config_init():
    """Test AI config initialization."""
    config = AIConfig()
    assert config is not None

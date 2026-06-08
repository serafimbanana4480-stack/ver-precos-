"""
Unit test for config experiments.
"""
import pytest
from config.experiments_config import ExperimentConfig


def test_experiment_config_init():
    """Test experiment config initialization."""
    config = ExperimentConfig()
    assert config is not None

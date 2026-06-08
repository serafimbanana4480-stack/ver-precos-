"""
Unit test for ML training trainer.
"""
import pytest
from ml.training.trainer import Trainer


def test_trainer_init():
    """Test trainer initialization."""
    trainer = Trainer()
    assert trainer is not None

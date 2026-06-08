"""
Unit test for ingestion validation validator.
"""
import pytest
from ingestion.validation.validator import Validator


def test_validator_init():
    """Test validator initialization."""
    validator = Validator()
    assert validator is not None

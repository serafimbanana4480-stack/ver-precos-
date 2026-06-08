"""
Unit test for processing validator.
"""
import pytest
from processing.validator import Validator


def test_validator_init():
    """Test validator initialization."""
    validator = Validator()
    assert validator is not None

"""
Unit test for utils logging.
"""
import pytest
from utils.logging_config import setup_logging


def test_setup_logging():
    """Test logging setup."""
    logger = setup_logging()
    assert logger is not None

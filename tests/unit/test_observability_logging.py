"""
Unit test for observability logging.
"""
import pytest
from observability.logging.logger import Logger


def test_logger_init():
    """Test logger initialization."""
    logger = Logger("test")
    assert logger is not None

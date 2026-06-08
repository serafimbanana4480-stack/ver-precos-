"""
Unit test for app middleware logging.
"""
import pytest
from app.middleware.logging import LoggingMiddleware


def test_logging_middleware_init():
    """Test logging middleware initialization."""
    middleware = LoggingMiddleware()
    assert middleware is not None

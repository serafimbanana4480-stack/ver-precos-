"""
Unit test for app middleware error.
"""
import pytest
from app.middleware.error import ErrorMiddleware


def test_error_middleware_init():
    """Test error middleware initialization."""
    middleware = ErrorMiddleware()
    assert middleware is not None

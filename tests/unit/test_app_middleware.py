"""
Unit test for app middleware.
"""
import pytest
from app.middleware.auth import AuthMiddleware


def test_auth_middleware_init():
    """Test auth middleware initialization."""
    middleware = AuthMiddleware()
    assert middleware is not None

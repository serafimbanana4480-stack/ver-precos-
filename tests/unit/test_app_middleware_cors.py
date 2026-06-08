"""
Unit test for app middleware CORS.
"""
import pytest
from app.middleware.cors import CORSMiddleware


def test_cors_middleware_init():
    """Test CORS middleware initialization."""
    middleware = CORSMiddleware()
    assert middleware is not None

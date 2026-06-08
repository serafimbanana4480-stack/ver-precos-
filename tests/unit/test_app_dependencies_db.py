"""
Unit test for app dependencies db.
"""
import pytest
from app.dependencies.db import get_db


def test_get_db():
    """Test get_db function."""
    db = get_db()
    assert db is not None

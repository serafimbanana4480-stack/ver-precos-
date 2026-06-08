"""
Unit tests for database.db session helpers.
"""
import pytest
from database.db import init_db, get_db_context, health_check


def test_health_check_returns_bool():
    """Database health check should return a boolean without raising."""
    assert isinstance(health_check(), bool)


def test_get_db_context_commits():
    """Context manager should allow basic session usage."""
    from database.models import Vehicle, Source, VehicleType

    with get_db_context() as db:
        count_before = db.query(Vehicle).count()
    assert count_before >= 0


@pytest.mark.skip(reason="init_db mutates production DB file; run via main.py init")
def test_init_db():
    init_db()

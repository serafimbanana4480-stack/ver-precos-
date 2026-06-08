"""
Unit test for app dependencies scheduler.
"""
import pytest
from app.dependencies.scheduler import get_scheduler


def test_get_scheduler():
    """Test get_scheduler function."""
    scheduler = get_scheduler()
    assert scheduler is not None

"""
Unit test for app dependencies dashboard.
"""
import pytest
from app.dependencies.dashboard import get_dashboard


def test_get_dashboard():
    """Test get_dashboard function."""
    dashboard = get_dashboard()
    assert dashboard is not None

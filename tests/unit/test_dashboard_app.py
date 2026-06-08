"""
Unit test for dashboard app.
"""
import pytest
from dashboard.app import DashboardApp


def test_dashboard_app_init():
    """Test dashboard app initialization."""
    app = DashboardApp()
    assert app is not None

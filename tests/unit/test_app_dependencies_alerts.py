"""
Unit test for app dependencies alerts.
"""
import pytest
from app.dependencies.alerts import get_alert_manager


def test_get_alert_manager():
    """Test get_alert_manager function."""
    manager = get_alert_manager()
    assert manager is not None

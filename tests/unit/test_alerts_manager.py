"""
Unit test for alerts manager.
"""
import pytest
from alerts.manager import AlertManager


def test_alert_manager_init():
    """Test alert manager initialization."""
    manager = AlertManager()
    assert manager is not None

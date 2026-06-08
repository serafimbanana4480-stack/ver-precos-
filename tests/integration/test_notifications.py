"""
Integration test for notifications.
"""
import pytest
from alerts.manager import AlertManager


@pytest.mark.integration
async def test_alert_manager():
    """Test alert manager integration."""
    manager = AlertManager()
    result = manager.send_alert("Test message", "Test title")
    assert result is not None

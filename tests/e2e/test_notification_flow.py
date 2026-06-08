"""
E2E test for notification flow.
"""
import pytest
from alerts.manager import AlertManager


@pytest.mark.e2e
async def test_notification_flow():
    """Test complete notification flow."""
    manager = AlertManager()
    result = manager.send_alert("Test message", "Test title")
    assert result is not None

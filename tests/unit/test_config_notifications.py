"""
Unit test for config notifications.
"""
import pytest
from config.notification_config import NotificationConfig


def test_notification_config_init():
    """Test notification config initialization."""
    config = NotificationConfig()
    assert config is not None

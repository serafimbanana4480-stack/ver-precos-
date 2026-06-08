"""
Unit test for alerts channels.
"""
import pytest
from alerts.channels.discord import DiscordChannel


def test_discord_channel_init():
    """Test discord channel initialization."""
    channel = DiscordChannel(webhook_url="http://test.com")
    assert channel is not None

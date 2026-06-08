"""
Channel factory for alerts.
"""
from typing import Dict, Type
from .base import BaseChannel
from .discord import DiscordChannel
from .email import EmailChannel
from .telegram import TelegramChannel
from .webhook import WebhookChannel
from .slack import SlackChannel
from .pagerduty import PagerDutyChannel


class ChannelFactory:
    """Factory for creating alert channels."""
    
    channels: Dict[str, Type[BaseChannel]] = {
        "discord": DiscordChannel,
        "email": EmailChannel,
        "telegram": TelegramChannel,
        "webhook": WebhookChannel,
        "slack": SlackChannel,
        "pagerduty": PagerDutyChannel,
    }
    
    @classmethod
    def create_channel(cls, channel_type: str, **kwargs) -> BaseChannel:
        """Create channel by type."""
        channel_class = cls.channels.get(channel_type)
        if not channel_class:
            raise ValueError(f"Unknown channel type: {channel_type}")
        return channel_class(**kwargs)

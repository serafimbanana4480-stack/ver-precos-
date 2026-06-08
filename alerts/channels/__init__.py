"""
Alert channels for AutoDeal IA Hunter.
"""
from .discord import DiscordChannel
from .email import EmailChannel
from .telegram import TelegramChannel
from .webhook import WebhookChannel
from .slack import SlackChannel
from .pagerduty import PagerDutyChannel

__all__ = [
    "DiscordChannel",
    "EmailChannel",
    "TelegramChannel",
    "WebhookChannel",
    "SlackChannel",
    "PagerDutyChannel",
]

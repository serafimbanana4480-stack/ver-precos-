"""
Alerts package for AutoDeal IA Hunter.
"""
from .channels import DiscordChannel, EmailChannel, TelegramChannel
from .manager import AlertManager
from .router import AlertRouter
from .priority import AlertPriority

__all__ = [
    "DiscordChannel",
    "EmailChannel",
    "TelegramChannel",
    "AlertManager",
    "AlertRouter",
    "AlertPriority",
]

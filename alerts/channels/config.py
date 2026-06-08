"""
Channel configuration for alerts.
"""
from pydantic import BaseModel
from typing import Optional


class ChannelConfig(BaseModel):
    """Configuration for alert channels."""
    
    discord_enabled: bool = False
    discord_webhook_url: Optional[str] = None
    
    email_enabled: bool = False
    email_smtp_host: Optional[str] = None
    email_smtp_port: int = 587
    email_smtp_user: Optional[str] = None
    email_smtp_password: Optional[str] = None
    email_from: Optional[str] = None
    email_to: list = []
    
    telegram_enabled: bool = False
    telegram_bot_token: Optional[str] = None
    telegram_chat_id: Optional[str] = None
    
    webhook_enabled: bool = False
    webhook_url: Optional[str] = None
    
    slack_enabled: bool = False
    slack_webhook_url: Optional[str] = None
    
    pagerduty_enabled: bool = False
    pagerduty_integration_key: Optional[str] = None

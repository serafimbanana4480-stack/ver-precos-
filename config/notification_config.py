"""
Notification configuration for AutoDeal IA Hunter.
"""
from pydantic import BaseModel
from typing import Optional


class DiscordConfig(BaseModel):
    """Configuration for Discord notifications."""
    
    enabled: bool = False
    webhook_url: Optional[str] = None
    username: str = "AutoDeal IA Hunter"
    avatar_url: Optional[str] = None
    mention_role: Optional[str] = None


class EmailConfig(BaseModel):
    """Configuration for Email notifications."""
    
    enabled: bool = False
    smtp_host: Optional[str] = None
    smtp_port: int = 587
    smtp_user: Optional[str] = None
    smtp_password: Optional[str] = None
    smtp_use_tls: bool = True
    from_email: Optional[str] = None
    to_emails: list = []


class TelegramConfig(BaseModel):
    """Configuration for Telegram notifications."""
    
    enabled: bool = False
    bot_token: Optional[str] = None
    chat_id: Optional[str] = None
    parse_mode: str = "HTML"
    disable_web_page_preview: bool = False


class WebhookConfig(BaseModel):
    """Configuration for Webhook notifications."""
    
    enabled: bool = False
    url: Optional[str] = None
    method: str = "POST"
    headers: dict = {}
    timeout_seconds: int = 10


class NotificationConfig(BaseModel):
    """Configuration for all notification channels."""
    
    discord: DiscordConfig = DiscordConfig()
    email: EmailConfig = EmailConfig()
    telegram: TelegramConfig = TelegramConfig()
    webhook: WebhookConfig = WebhookConfig()
    
    # Global notification settings
    enabled: bool = True
    batch_notifications: bool = True
    batch_size: int = 10
    batch_interval_seconds: int = 300
    
    # Notification triggers
    notify_on_deal_found: bool = True
    notify_on_scraping_complete: bool = True
    notify_on_model_trained: bool = True
    notify_on_error: bool = True
    notify_on_system_health: bool = False
    
    # Deal notification thresholds
    min_deal_score: float = 7.0
    min_profit_euros: int = 1500


notification_config = NotificationConfig()

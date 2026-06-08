"""
Alert manager for AutoDeal IA Hunter.
"""
from typing import Dict, List, Optional
from pydantic import BaseModel
from .channels import DiscordChannel, EmailChannel, TelegramChannel


class AlertManager(BaseModel):
    """Manager for alert notifications."""
    
    discord: Optional[DiscordChannel] = None
    email: Optional[EmailChannel] = None
    telegram: Optional[TelegramChannel] = None
    
    def send_alert(self, message: str, title: Optional[str] = None, channels: Optional[List[str]] = None) -> bool:
        """Send alert to specified channels."""
        success = True
        
        if channels is None:
            channels = []
        
        if "discord" in channels and self.discord:
            success &= self.discord.send(message, title)
        
        if "email" in channels and self.email:
            success &= self.email.send(title or "Alert", message)
        
        if "telegram" in channels and self.telegram:
            success &= self.telegram.send(message)
        
        return success

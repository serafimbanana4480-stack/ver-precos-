"""
Slack channel for alerts.
"""
import requests
from typing import Optional
from pydantic import BaseModel


class SlackChannel(BaseModel):
    """Slack webhook notification channel."""
    
    webhook_url: str
    username: str = "AutoDeal IA Hunter"
    icon_emoji: Optional[str] = None
    channel: Optional[str] = None
    
    def send(self, message: str, title: Optional[str] = None) -> bool:
        """Send message to Slack webhook."""
        try:
            payload = {
                "text": message,
                "username": self.username,
            }
            
            if self.icon_emoji:
                payload["icon_emoji"] = self.icon_emoji
            
            if self.channel:
                payload["channel"] = self.channel
            
            if title:
                payload["text"] = f"*{title}*\n{message}"
            
            response = requests.post(self.webhook_url, json=payload, timeout=10)
            return response.status_code == 200
        except Exception:
            return False

"""
Discord channel for alerts.
"""
import requests
from typing import Dict, Optional
from pydantic import BaseModel


class DiscordChannel(BaseModel):
    """Discord webhook notification channel."""
    
    webhook_url: str
    username: str = "AutoDeal IA Hunter"
    avatar_url: Optional[str] = None
    mention_role: Optional[str] = None
    
    def send(self, message: str, title: Optional[str] = None, color: Optional[int] = None) -> bool:
        """Send message to Discord webhook."""
        try:
            embed = {
                "title": title,
                "description": message,
                "color": color,
            }
            
            if self.mention_role:
                embed["description"] = f"@{self.mention_role}\n{embed['description']}"
            
            payload = {
                "username": self.username,
                "avatar_url": self.avatar_url,
                "embeds": [embed],
            }
            
            response = requests.post(self.webhook_url, json=payload, timeout=10)
            return response.status_code == 204
        except Exception:
            return False

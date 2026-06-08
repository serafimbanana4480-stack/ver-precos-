"""
Telegram channel for alerts.
"""
import requests
from typing import Optional
from pydantic import BaseModel


class TelegramChannel(BaseModel):
    """Telegram bot notification channel."""
    
    bot_token: str
    chat_id: str
    parse_mode: str = "HTML"
    disable_web_page_preview: bool = False
    
    def send(self, message: str) -> bool:
        """Send message to Telegram bot."""
        try:
            url = f"https://api.telegram.org/bot{self.bot_token}/sendMessage"
            payload = {
                "chat_id": self.chat_id,
                "text": message,
                "parse_mode": self.parse_mode,
                "disable_web_page_preview": self.disable_web_page_preview,
            }
            
            response = requests.post(url, json=payload, timeout=10)
            return response.status_code == 200
        except Exception:
            return False

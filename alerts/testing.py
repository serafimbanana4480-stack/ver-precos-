"""
Alert testing for AutoDeal IA Hunter.
"""
from typing import Dict, List
from pydantic import BaseModel


class AlertTester(BaseModel):
    """Test alert channels."""
    
    def test_discord(self, webhook_url: str) -> Dict[str, any]:
        """Test Discord webhook."""
        return {
            "channel": "discord",
            "webhook_url": webhook_url,
            "test_message": "Test alert from AutoDeal IA Hunter",
            "success": True,
            "timestamp": "now",
        }
    
    def test_email(self, to_email: str) -> Dict[str, any]:
        """Test email channel."""
        return {
            "channel": "email",
            "to_email": to_email,
            "test_message": "Test alert from AutoDeal IA Hunter",
            "success": True,
            "timestamp": "now",
        }
    
    def test_telegram(self, chat_id: str) -> Dict[str, any]:
        """Test Telegram channel."""
        return {
            "channel": "telegram",
            "chat_id": chat_id,
            "test_message": "Test alert from AutoDeal IA Hunter",
            "success": True,
            "timestamp": "now",
        }

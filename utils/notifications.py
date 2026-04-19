"""
Notification services for AutoDeal IA Hunter
Supports Telegram and Discord (extensible)
"""
from __future__ import annotations
import logging
import httpx
from typing import Optional, Dict, Any
from config import settings

logger = logging.getLogger(__name__)


class TelegramNotifier:
    """Service to send notifications via Telegram Bot API"""
    
    def __init__(self) -> None:
        self.bot_token = settings.telegram_bot_token
        self.chat_id = settings.telegram_chat_id
        self.enabled = bool(self.bot_token and self.chat_id)
        
        if not self.enabled:
            logger.warning("[TELEGRAM] Telegram credentials not set. Notifications disabled.")

    async def send_message(self, text: str, parse_mode: str = "Markdown") -> bool:
        """Send a raw message to the configured Telegram chat"""
        if not self.enabled:
            return False
            
        url = f"https://api.telegram.org/bot{self.bot_token}/sendMessage"
        payload = {
            "chat_id": self.chat_id,
            "text": text,
            "parse_mode": parse_mode
        }
        
        try:
            async with httpx.AsyncClient(timeout=10) as client:
                response = await client.post(url, json=payload)
                response.raise_for_status()
                logger.info("[TELEGRAM] Notification sent successfully")
                return True
        except Exception as e:
            logger.error(f"[TELEGRAM] Failed to send notification: {e}")
            return False

    async def send_deal_alert(self, vehicle_data: Dict[str, Any]) -> bool:
        """Send a formatted alert for a high-potential deal"""
        if not self.enabled:
            return False
            
        title = vehicle_data.get("title", "Unknown Vehicle")
        price = vehicle_data.get("price", "N/A")
        year = vehicle_data.get("year", "N/A")
        km = vehicle_data.get("km", "N/A")
        source = vehicle_data.get("source", "unknown").upper()
        url = vehicle_data.get("url", "#")
        score = vehicle_data.get("deal_score", 0)
        
        # Determine emoji based on score
        emoji = "🚀" if score >= 90 else "🔥" if score >= 80 else "👀"
        
        message = (
            f"{emoji} *NOVO NEGÓCIO DETETADO!* {emoji}\n\n"
            f"*Veículo:* {title}\n"
            f"*Preço:* {price}€\n"
            f"*Ano:* {year}\n"
            f"*KM:* {km} km\n"
            f"*Fonte:* {source}\n"
            f"*Score:* {score}/100\n\n"
            f"[Ver Anúncio]({url})"
        )
        
        return await self.send_message(message)


# Singleton
_telegram_notifier: Optional[TelegramNotifier] = None


def get_telegram_notifier() -> TelegramNotifier:
    """Get or create Telegram notifier singleton"""
    global _telegram_notifier
    if _telegram_notifier is None:
        _telegram_notifier = TelegramNotifier()
    return _telegram_notifier

"""
Alert throttle logic for AutoDeal IA Hunter.
"""
import time
from typing import Dict
from datetime import datetime, timedelta


class AlertThrottle:
    """Throttle alert sends to avoid spam."""
    
    def __init__(self, cooldown_minutes: int = 5):
        self.cooldown_minutes = cooldown_minutes
        self.last_sent: Dict[str, datetime] = {}
    
    def can_send(self, alert_type: str) -> bool:
        """Check if alert can be sent based on throttle."""
        last_sent = self.last_sent.get(alert_type)
        
        if last_sent is None:
            return True
        
        cooldown_end = last_sent + timedelta(minutes=self.cooldown_minutes)
        return datetime.utcnow() >= cooldown_end
    
    def mark_sent(self, alert_type: str) -> None:
        """Mark alert as sent."""
        self.last_sent[alert_type] = datetime.utcnow()

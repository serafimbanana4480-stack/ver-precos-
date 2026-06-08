"""
Alert history for AutoDeal IA Hunter.
"""
from typing import Dict, List
from datetime import datetime
from pydantic import BaseModel


class AlertHistory(BaseModel):
    """History of sent alerts."""
    
    alerts: List[Dict[str, any]] = []
    
    def add_alert(self, alert_type: str, message: str, channels: List[str], success: bool) -> None:
        """Add alert to history."""
        self.alerts.append({
            "type": alert_type,
            "message": message,
            "channels": channels,
            "success": success,
            "timestamp": datetime.utcnow().isoformat(),
        })
    
    def get_recent_alerts(self, limit: int = 10) -> List[Dict[str, any]]:
        """Get recent alerts."""
        return self.alerts[-limit:]

"""
Alert aggregator for AutoDeal IA Hunter.
"""
from typing import List, Dict
from datetime import datetime, timedelta
from collections import defaultdict


class AlertAggregator:
    """Aggregate similar alerts to avoid spam."""
    
    def __init__(self, window_minutes: int = 10):
        self.window_minutes = window_minutes
        self.alerts: List[Dict[str, any]] = []
    
    def add_alert(self, alert_type: str, message: str, data: Dict[str, any] = None) -> None:
        """Add alert to aggregator."""
        self.alerts.append({
            "type": alert_type,
            "message": message,
            "data": data or {},
            "timestamp": datetime.utcnow(),
        })
    
    def get_aggregated_alerts(self) -> List[Dict[str, any]]:
        """Get aggregated alerts within time window."""
        now = datetime.utcnow()
        window_start = now - timedelta(minutes=self.window_minutes)
        
        recent_alerts = [
            alert for alert in self.alerts
            if alert["timestamp"] >= window_start
        ]
        
        aggregated = defaultdict(list)
        for alert in recent_alerts:
            aggregated[alert["type"]].append(alert)
        
        result = []
        for alert_type, alerts in aggregated.items():
            if len(alerts) == 1:
                result.append(alerts[0])
            else:
                result.append({
                    "type": alert_type,
                    "message": f"{len(alerts)} similar alerts",
                    "count": len(alerts),
                    "alerts": alerts,
                })
        
        return result

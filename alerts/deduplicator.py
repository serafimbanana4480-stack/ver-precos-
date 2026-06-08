"""
Alert deduplicator for AutoDeal IA Hunter.
"""
from typing import Dict, List
from datetime import datetime, timedelta
from hashlib import md5


class AlertDeduplicator:
    """Deduplicate alerts to avoid sending duplicates."""
    
    def __init__(self, ttl_minutes: int = 30):
        self.ttl_minutes = ttl_minutes
        self.seen_alerts: Dict[str, datetime] = {}
    
    def _generate_hash(self, alert_type: str, message: str) -> str:
        """Generate hash for alert."""
        content = f"{alert_type}:{message}"
        return md5(content.encode()).hexdigest()
    
    def is_duplicate(self, alert_type: str, message: str) -> bool:
        """Check if alert is duplicate."""
        alert_hash = self._generate_hash(alert_type, message)
        
        if alert_hash not in self.seen_alerts:
            return False
        
        ttl_end = self.seen_alerts[alert_hash] + timedelta(minutes=self.ttl_minutes)
        return datetime.utcnow() < ttl_end
    
    def mark_seen(self, alert_type: str, message: str) -> None:
        """Mark alert as seen."""
        alert_hash = self._generate_hash(alert_type, message)
        self.seen_alerts[alert_hash] = datetime.utcnow()
    
    def cleanup(self) -> None:
        """Clean up expired entries."""
        now = datetime.utcnow()
        expired_hashes = [
            h for h, t in self.seen_alerts.items()
            if t + timedelta(minutes=self.ttl_minutes) < now
        ]
        
        for h in expired_hashes:
            del self.seen_alerts[h]

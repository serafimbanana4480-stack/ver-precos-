"""
Alert monitoring for AutoDeal IA Hunter.
"""
from typing import Dict, List
from datetime import datetime
from pydantic import BaseModel


class AlertMonitoring(BaseModel):
    """Monitor alert system health."""
    
    sent_count: int = 0
    failed_count: int = 0
    last_sent: datetime = None
    last_failed: datetime = None
    
    def record_success(self) -> None:
        """Record successful alert send."""
        self.sent_count += 1
        self.last_sent = datetime.utcnow()
    
    def record_failure(self) -> None:
        """Record failed alert send."""
        self.failed_count += 1
        self.last_failed = datetime.utcnow()
    
    def get_success_rate(self) -> float:
        """Calculate success rate."""
        total = self.sent_count + self.failed_count
        if total == 0:
            return 0.0
        return self.sent_count / total

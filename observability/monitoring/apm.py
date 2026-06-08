"""
APM (Application Performance Monitoring) for AutoDeal IA Hunter.
"""
from typing import Dict, List
from datetime import datetime


class APM:
    """Application Performance Monitoring."""
    
    def __init__(self):
        self.transactions: List[Dict[str, any]] = []
        self.errors: List[Dict[str, any]] = []
    
    def record_transaction(self, name: str, duration_ms: float, success: bool = True) -> None:
        """Record transaction."""
        self.transactions.append({
            "name": name,
            "duration_ms": duration_ms,
            "success": success,
            "timestamp": datetime.utcnow().isoformat(),
        })
    
    def record_error(self, error_type: str, error_message: str, context: Dict[str, any] = None) -> None:
        """Record error."""
        self.errors.append({
            "type": error_type,
            "message": error_message,
            "context": context or {},
            "timestamp": datetime.utcnow().isoformat(),
        })
    
    def get_stats(self) -> Dict[str, any]:
        """Get APM statistics."""
        if not self.transactions:
            return {}
        
        durations = [t["duration_ms"] for t in self.transactions]
        
        return {
            "total_transactions": len(self.transactions),
            "successful_transactions": sum(1 for t in self.transactions if t["success"]),
            "failed_transactions": sum(1 for t in self.transactions if not t["success"]),
            "avg_duration_ms": sum(durations) / len(durations),
            "min_duration_ms": min(durations),
            "max_duration_ms": max(durations),
            "total_errors": len(self.errors),
        }

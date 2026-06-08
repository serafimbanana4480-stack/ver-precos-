"""
Metrics collector for AutoDeal IA Hunter.
"""
from typing import Dict, Any
from datetime import datetime
from collections import defaultdict


class MetricsCollector:
    """Collector for application metrics."""
    
    def __init__(self):
        self.metrics: Dict[str, Any] = defaultdict(list)
    
    def increment(self, metric_name: str, value: float = 1.0, tags: Dict[str, str] = None) -> None:
        """Increment metric."""
        self.metrics[metric_name].append({
            "value": value,
            "timestamp": datetime.utcnow().isoformat(),
            "tags": tags or {},
        })
    
    def gauge(self, metric_name: str, value: float, tags: Dict[str, str] = None) -> None:
        """Set gauge metric."""
        self.metrics[metric_name].append({
            "value": value,
            "timestamp": datetime.utcnow().isoformat(),
            "tags": tags or {},
        })
    
    def timing(self, metric_name: str, duration_seconds: float, tags: Dict[str, str] = None) -> None:
        """Record timing metric."""
        self.metrics[metric_name].append({
            "value": duration_seconds,
            "timestamp": datetime.utcnow().isoformat(),
            "tags": tags or {},
        })
    
    def get_metrics(self) -> Dict[str, Any]:
        """Get all metrics."""
        return dict(self.metrics)

"""
StatsD metrics client for AutoDeal IA Hunter.
"""
import statsd
from typing import Optional


class StatsDMetrics:
    """StatsD metrics client."""
    
    def __init__(self, host: str = "localhost", port: int = 8125, prefix: str = "autodeal"):
        self.client = statsd.StatsClient(host, port, prefix=prefix)
    
    def increment(self, metric_name: str, value: int = 1, rate: float = 1.0) -> None:
        """Increment counter."""
        self.client.incr(metric_name, value, rate)
    
    def gauge(self, metric_name: str, value: float, rate: float = 1.0) -> None:
        """Set gauge."""
        self.client.gauge(metric_name, value, rate)
    
    def timing(self, metric_name: str, duration_ms: float, rate: float = 1.0) -> None:
        """Record timing."""
        self.client.timing(metric_name, duration_ms, rate)

"""
Prometheus metrics client for AutoDeal IA Hunter.
"""
from prometheus_client import Counter, Gauge, Histogram, start_http_server
from typing import Dict, Optional


class PrometheusMetrics:
    """Prometheus metrics client."""
    
    def __init__(self, port: int = 9090):
        self.port = port
        self.counters: Dict[str, Counter] = {}
        self.gauges: Dict[str, Gauge] = {}
        self.histograms: Dict[str, Histogram] = {}
    
    def start_server(self) -> None:
        """Start Prometheus HTTP server."""
        start_http_server(self.port)
    
    def create_counter(self, name: str, description: str, labels: list = None) -> Counter:
        """Create counter metric."""
        counter = Counter(name, description, labels or [])
        self.counters[name] = counter
        return counter
    
    def create_gauge(self, name: str, description: str, labels: list = None) -> Gauge:
        """Create gauge metric."""
        gauge = Gauge(name, description, labels or [])
        self.gauges[name] = gauge
        return gauge
    
    def create_histogram(self, name: str, description: str, buckets: list = None) -> Histogram:
        """Create histogram metric."""
        histogram = Histogram(name, description, buckets or [])
        self.histograms[name] = histogram
        return histogram

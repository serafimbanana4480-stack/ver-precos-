"""
Metrics configuration for AutoDeal IA Hunter.
"""
from pydantic import BaseModel
from typing import Optional


class MetricsConfig(BaseModel):
    """Configuration for metrics collection."""
    
    enabled: bool = True
    provider: str = "prometheus"  # prometheus, statsd, graphite
    
    # Prometheus
    prometheus_port: int = 9090
    prometheus_host: str = "localhost"
    
    # StatsD
    statsd_host: Optional[str] = None
    statsd_port: Optional[int] = 8125
    
    # Graphite
    graphite_host: Optional[str] = None
    graphite_port: Optional[int] = 2003
    
    # Metrics to collect
    collect_scraping_metrics: bool = True
    collect_ai_metrics: bool = True
    collect_ml_metrics: bool = True
    collect_database_metrics: bool = True
    collect_api_metrics: bool = True
    
    # Export interval
    export_interval_seconds: int = 60


metrics_config = MetricsConfig()

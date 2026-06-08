"""
Monitoring configuration for AutoDeal IA Hunter.
"""
from pydantic import BaseModel
from typing import List, Optional


class MonitoringConfig(BaseModel):
    """Configuration for monitoring settings."""
    
    enabled: bool = True
    
    # Health checks
    health_check_enabled: bool = True
    health_check_interval_seconds: int = 60
    
    # Performance monitoring
    performance_monitoring_enabled: bool = True
    performance_threshold_ms: int = 1000
    
    # Error tracking
    error_tracking_enabled: bool = True
    error_threshold_per_hour: int = 10
    
    # Resource monitoring
    cpu_threshold_percent: int = 80
    memory_threshold_percent: int = 80
    disk_threshold_percent: int = 90
    
    # Alerting
    alerting_enabled: bool = True
    alert_channels: List[str] = ["email"]
    
    # APM
    apm_enabled: bool = False
    apm_provider: Optional[str] = None  # datadog, newrelic, etc.
    
    # Distributed tracing
    tracing_enabled: bool = False
    tracing_provider: Optional[str] = None  # jaeger, zipkin, etc.


monitoring_config = MonitoringConfig()

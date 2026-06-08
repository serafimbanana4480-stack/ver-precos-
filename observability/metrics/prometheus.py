"""
Prometheus Metrics Exporter
Production-grade metrics collection with Prometheus
"""
from __future__ import annotations
import logging
from typing import Dict, Any, Optional
from datetime import datetime, timedelta
from collections import defaultdict
import time

logger = logging.getLogger(__name__)


class PrometheusMetrics:
    """
    Prometheus metrics collector
    
    Note: This is a simplified implementation.
    For production, use prometheus_client library.
    """
    
    def __init__(self):
        self.counters: Dict[str, float] = defaultdict(float)
        self.gauges: Dict[str, float] = defaultdict(float)
        self.histograms: Dict[str, list] = defaultdict(list)
        self.start_time = datetime.utcnow()
    
    def increment(self, name: str, value: float = 1.0, labels: Optional[Dict[str, str]] = None):
        """
        Increment a counter metric
        
        Args:
            name: Metric name
            value: Value to increment by
            labels: Metric labels
        """
        key = self._make_key(name, labels)
        self.counters[key] += value
        logger.debug(f"Counter {key}: {self.counters[key]}")
    
    def set_gauge(self, name: str, value: float, labels: Optional[Dict[str, str]] = None):
        """
        Set a gauge metric
        
        Args:
            name: Metric name
            value: Value to set
            labels: Metric labels
        """
        key = self._make_key(name, labels)
        self.gauges[key] = value
        logger.debug(f"Gauge {key}: {value}")
    
    def observe(self, name: str, value: float, labels: Optional[Dict[str, str]] = None):
        """
        Observe a histogram metric
        
        Args:
            name: Metric name
            value: Value to observe
            labels: Metric labels
        """
        key = self._make_key(name, labels)
        self.histograms[key].append(value)
        logger.debug(f"Histogram {key}: observed {value}")
    
    def _make_key(self, name: str, labels: Optional[Dict[str, str]]) -> str:
        """Create a metric key from name and labels"""
        if labels:
            label_str = ",".join(f'{k}="{v}"' for k, v in labels.items())
            return f"{name}{{{label_str}}}"
        return name
    
    def get_counter(self, name: str, labels: Optional[Dict[str, str]] = None) -> float:
        """Get counter value"""
        key = self._make_key(name, labels)
        return self.counters.get(key, 0.0)
    
    def get_gauge(self, name: str, labels: Optional[Dict[str, str]] = None) -> float:
        """Get gauge value"""
        key = self._make_key(name, labels)
        return self.gauges.get(key, 0.0)
    
    def get_histogram_stats(self, name: str, labels: Optional[Dict[str, str]] = None) -> Dict[str, float]:
        """Get histogram statistics"""
        key = self._make_key(name, labels)
        values = self.histograms.get(key, [])
        
        if not values:
            return {}
        
        values_sorted = sorted(values)
        count = len(values_sorted)
        
        return {
            "count": count,
            "sum": sum(values_sorted),
            "min": values_sorted[0],
            "max": values_sorted[-1],
            "avg": sum(values_sorted) / count,
            "p50": values_sorted[int(count * 0.5)],
            "p95": values_sorted[int(count * 0.95)],
            "p99": values_sorted[int(count * 0.99)],
        }
    
    def export_metrics(self) -> str:
        """
        Export metrics in Prometheus text format
        
        Returns:
            Metrics in Prometheus format
        """
        lines = []
        
        # Counters
        for key, value in self.counters.items():
            lines.append(f"# TYPE {key} counter")
            lines.append(f"{key} {value}")
        
        # Gauges
        for key, value in self.gauges.items():
            lines.append(f"# TYPE {key} gauge")
            lines.append(f"{key} {value}")
        
        # Histograms
        for key, values in self.histograms.items():
            stats = self.get_histogram_stats(key.split("{")[0])
            if stats:
                lines.append(f"# TYPE {key.split('{')[0]} histogram")
                lines.append(f"{key}_count {stats['count']}")
                lines.append(f"{key}_sum {stats['sum']}")
                lines.append(f"{key}_bucket {{le=\"+Inf\"}} {stats['count']}")
        
        # Uptime
        uptime = (datetime.utcnow() - self.start_time).total_seconds()
        lines.append(f"# TYPE autodeal_uptime_seconds gauge")
        lines.append(f"autodeal_uptime_seconds {uptime}")
        
        return "\n".join(lines)
    
    def reset(self):
        """Reset all metrics"""
        self.counters.clear()
        self.gauges.clear()
        self.histograms.clear()
        self.start_time = datetime.utcnow()


class MetricsCollector:
    """
    High-level metrics collector for AutoDeal
    """
    
    def __init__(self):
        self.metrics = PrometheusMetrics()
    
    def record_scrape(self, source: str, success: bool, count: int, duration: float):
        """Record scrape operation"""
        self.metrics.increment("scrapes_total", labels={"source": source, "status": "success" if success else "failure"})
        self.metrics.increment("listings_scraped", count, labels={"source": source})
        self.metrics.observe("scrape_duration_seconds", duration, labels={"source": source})
    
    def record_ai_analysis(self, analysis_type: str, success: bool, duration: float):
        """Record AI analysis operation"""
        self.metrics.increment("ai_analysis_total", labels={"type": analysis_type, "status": "success" if success else "failure"})
        self.metrics.observe("ai_analysis_duration_seconds", duration, labels={"type": analysis_type})
    
    def record_pricing(self, success: bool, duration: float):
        """Record pricing operation"""
        self.metrics.increment("pricing_operations_total", labels={"status": "success" if success else "failure"})
        self.metrics.observe("pricing_duration_seconds", duration)
    
    def record_scoring(self, success: bool, duration: float):
        """Record scoring operation"""
        self.metrics.increment("scoring_operations_total", labels={"status": "success" if success else "failure"})
        self.metrics.observe("scoring_duration_seconds", duration)
    
    def record_pipeline(self, stage: str, success: bool, duration: float):
        """Record pipeline stage"""
        self.metrics.increment("pipeline_stages_total", labels={"stage": stage, "status": "success" if success else "failure"})
        self.metrics.observe("pipeline_stage_duration_seconds", duration, labels={"stage": stage})
    
    def record_deal_found(self, score: float):
        """Record a deal found"""
        self.metrics.increment("deals_found")
        self.metrics.observe("deal_score", score)
    
    def record_database_operation(self, operation: str, success: bool, duration: float):
        """Record database operation"""
        self.metrics.increment("db_operations_total", labels={"operation": operation, "status": "success" if success else "failure"})
        self.metrics.observe("db_operation_duration_seconds", duration, labels={"operation": operation})
    
    def set_active_listings(self, count: int):
        """Set gauge for active listings"""
        self.metrics.set_gauge("active_listings", count)
    
    def set_ai_coverage(self, llm_coverage: float, vision_coverage: float):
        """Set gauges for AI coverage"""
        self.metrics.set_gauge("ai_llm_coverage", llm_coverage)
        self.metrics.set_gauge("ai_vision_coverage", vision_coverage)
    
    def export(self) -> str:
        """Export all metrics"""
        return self.metrics.export_metrics()


# Singleton instance
metrics_collector = MetricsCollector()

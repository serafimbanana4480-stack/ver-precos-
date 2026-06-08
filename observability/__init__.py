"""
Observability package for AutoDeal IA Hunter.
"""

try:
    from .logging.logger import Logger
except ImportError:
    Logger = None

try:
    from .metrics.collector import MetricsCollector
except ImportError:
    MetricsCollector = None

try:
    from .monitoring.health import HealthChecker
except ImportError:
    HealthChecker = None

__all__ = [
    "Logger",
    "MetricsCollector",
    "HealthChecker",
]

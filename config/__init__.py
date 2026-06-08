"""
Configuration package for AutoDeal IA Hunter.
"""
from importlib import util as importlib_util
from pathlib import Path

from .base import BaseConfig, config
from .development import DevelopmentConfig
from .production import ProductionConfig
from .test import TestConfig
from .scrapers_config import ScrapersConfig, scrapers_config
from .ai_config import AIConfig, ai_config
from .notification_config import NotificationConfig, notification_config
from .database_config import DatabaseConfig, database_config
from .logging_config import LoggingConfig, logging_config
from .metrics_config import MetricsConfig, metrics_config
from .security_config import SecurityConfig, security_config
from .cache_config import CacheConfig, cache_config
from .queue_config import QueueConfig, queue_config
from .storage_config import StorageConfig, storage_config
from .api_config import APIConfig, api_config
from .dashboard_config import DashboardConfig, dashboard_config
from .scheduler_config import SchedulerConfig, scheduler_config
from .validation_config import ValidationConfig, validation_config
from .monitoring_config import MonitoringConfig, monitoring_config
from .performance_config import PerformanceConfig, performance_config
from .deal_scoring_config import DealScoringConfig, deal_scoring_config
from .proxy_config import ProxyConfig, proxy_config
from .captcha_config import CaptchaConfig, captcha_config
from .ml_config import MLConfig, ml_config
from .feature_flags_config import FeatureFlagsConfig, feature_flags_config
from .experiments_config import ExperimentConfig, experiments_config
from .regions_config import RegionConfig, regions_config

_root_config_path = Path(__file__).resolve().parent.parent / "config.py"
_root_config_spec = importlib_util.spec_from_file_location("autodeal_root_config", _root_config_path)

if _root_config_spec and _root_config_spec.loader:
    _root_config_module = importlib_util.module_from_spec(_root_config_spec)
    _root_config_spec.loader.exec_module(_root_config_module)
    settings = _root_config_module.settings
else:
    # Fallback to the lightweight package config if the root module cannot be loaded.
    settings = config

# Backwards-compatible alias used throughout the codebase.
config = settings


def __getattr__(name: str):
    """Forward missing attributes to the root-level config module."""
    if '_root_config_module' in globals() and hasattr(_root_config_module, name):
        return getattr(_root_config_module, name)
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")

__all__ = [
    "BaseConfig",
    "config",
    "settings",
    "DevelopmentConfig",
    "ProductionConfig",
    "TestConfig",
    "ScrapersConfig",
    "scrapers_config",
    "AIConfig",
    "ai_config",
    "NotificationConfig",
    "notification_config",
    "DatabaseConfig",
    "database_config",
    "LoggingConfig",
    "logging_config",
    "MetricsConfig",
    "metrics_config",
    "SecurityConfig",
    "security_config",
    "CacheConfig",
    "cache_config",
    "QueueConfig",
    "queue_config",
    "StorageConfig",
    "storage_config",
    "APIConfig",
    "api_config",
    "DashboardConfig",
    "dashboard_config",
    "SchedulerConfig",
    "scheduler_config",
    "ValidationConfig",
    "validation_config",
    "MonitoringConfig",
    "monitoring_config",
    "PerformanceConfig",
    "performance_config",
    "DealScoringConfig",
    "deal_scoring_config",
    "ProxyConfig",
    "proxy_config",
    "CaptchaConfig",
    "captcha_config",
    "MLConfig",
    "ml_config",
    "FeatureFlagsConfig",
    "feature_flags_config",
    "ExperimentConfig",
    "experiments_config",
    "RegionConfig",
    "regions_config",
]

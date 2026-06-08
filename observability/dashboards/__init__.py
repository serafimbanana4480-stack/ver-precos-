"""
Dashboards module for AutoDeal IA Hunter.
"""
from .grafana import GrafanaDashboard
from .telegraf import TelegrafConfig

__all__ = [
    "GrafanaDashboard",
    "TelegrafConfig",
]

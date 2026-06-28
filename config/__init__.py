"""
Configuration package for AutoDeal IA Hunter.

Single source of truth: ``core.settings.settings``.
"""
from core.settings import settings, BASE_DIR, DATA_DIR, MODELS_DIR, LOGS_DIR

__all__ = ["settings", "BASE_DIR", "DATA_DIR", "MODELS_DIR", "LOGS_DIR"]

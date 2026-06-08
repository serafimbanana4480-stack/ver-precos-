"""
Instrumentation module for AutoDeal IA Hunter.
"""
from .fastapi import FastAPIInstrumentation
from .sqlalchemy import SQLAlchemyInstrumentation
from .redis import RedisInstrumentation
from .httpx import HTTPXInstrumentation
from .playwright import PlaywrightInstrumentation

__all__ = [
    "FastAPIInstrumentation",
    "SQLAlchemyInstrumentation",
    "RedisInstrumentation",
    "HTTPXInstrumentation",
    "PlaywrightInstrumentation",
]

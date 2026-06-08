"""
Alert priority for AutoDeal IA Hunter.
"""
from enum import Enum


class AlertPriority(Enum):
    """Alert priority levels."""
    LOW = 1
    MEDIUM = 2
    HIGH = 3
    CRITICAL = 4

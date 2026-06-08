"""
Data aggregator module.
"""

from .aggregator import DataAggregator
from .price_aggregator import PriceAggregator
from .market_aggregator import MarketAggregator

__all__ = [
    'DataAggregator',
    'PriceAggregator',
    'MarketAggregator'
]

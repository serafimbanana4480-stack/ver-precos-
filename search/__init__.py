"""
Search module for Elasticsearch integration
Based on Obsidian Vault documentation for Hub - Search
"""
from .elasticsearch import ElasticsearchClient
from .optimization import SearchOptimizer
from .analytics import SearchAnalytics
from .scoring import RelevanceScorer

__all__ = [
    'ElasticsearchClient',
    'SearchOptimizer',
    'SearchAnalytics',
    'RelevanceScorer'
]

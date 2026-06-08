"""
Cache configuration for AutoDeal IA Hunter.
"""
from pydantic import BaseModel
from typing import Optional


class CacheConfig(BaseModel):
    """Configuration for cache settings."""
    
    enabled: bool = True
    backend: str = "redis"  # redis, memory, memcached
    
    # Redis
    redis_host: str = "localhost"
    redis_port: int = 6379
    redis_db: int = 0
    redis_password: Optional[str] = None
    redis_ssl: bool = False
    
    # Cache settings
    default_ttl_seconds: int = 3600
    max_size: int = 1000
    key_prefix: str = "autodeal:"
    
    # Cache policies
    cache_scraping_results: bool = True
    cache_ai_results: bool = True
    cache_ml_predictions: bool = True
    cache_api_responses: bool = True
    
    # Cache TTLs
    scraping_ttl_seconds: int = 1800
    ai_ttl_seconds: int = 3600
    ml_ttl_seconds: int = 7200
    api_ttl_seconds: int = 300


cache_config = CacheConfig()

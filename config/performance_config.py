"""
Performance configuration for AutoDeal IA Hunter.
"""
from pydantic import BaseModel


class PerformanceConfig(BaseModel):
    """Configuration for performance settings."""
    
    # Scraping performance
    max_concurrent_scrapers: int = 3
    scraper_timeout_seconds: int = 30
    scraper_retry_attempts: int = 3
    
    # AI performance
    max_concurrent_ai_requests: int = 2
    ai_timeout_seconds: int = 60
    ai_batch_size: int = 10
    
    # ML performance
    ml_batch_size: int = 100
    ml_cache_enabled: bool = True
    ml_model_caching: bool = True
    
    # Database performance
    db_pool_size: int = 5
    db_max_overflow: int = 10
    db_statement_timeout: int = 30
    
    # Cache performance
    cache_max_size: int = 1000
    cache_ttl_seconds: int = 3600
    
    # API performance
    api_timeout_seconds: int = 30
    api_rate_limit_per_minute: int = 60
    
    # General performance
    enable_profiling: bool = False
    profiling_sample_rate: float = 0.01


performance_config = PerformanceConfig()

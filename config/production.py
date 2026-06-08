"""
Production configuration for AutoDeal IA Hunter.
"""
from .base import BaseConfig


class ProductionConfig(BaseConfig):
    """Production configuration class."""
    
    DEBUG: bool = False
    ENVIRONMENT: str = "production"
    
    # Database
    DATABASE_URL: str = "postgresql://user:password@localhost:5432/autodeal"
    
    # Scraping
    SCRAPING_INTERVAL_HOURS: int = 6
    MAX_LISTINGS_PER_SOURCE: int = 100
    
    # Cache
    CACHE_TTL_SECONDS: int = 3600
    
    # Logging
    LOG_LEVEL: str = "INFO"


config = ProductionConfig()

"""
Development configuration for AutoDeal IA Hunter.
"""
from .base import BaseConfig


class DevelopmentConfig(BaseConfig):
    """Development configuration class."""
    
    DEBUG: bool = True
    ENVIRONMENT: str = "development"
    
    # Database
    DATABASE_URL: str = "sqlite:///./autodeal_dev.db"
    
    # Scraping
    SCRAPING_INTERVAL_HOURS: int = 1
    MAX_LISTINGS_PER_SOURCE: int = 20
    
    # Cache
    CACHE_TTL_SECONDS: int = 1800
    
    # Logging
    LOG_LEVEL: str = "DEBUG"


config = DevelopmentConfig()

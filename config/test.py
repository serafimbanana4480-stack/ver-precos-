"""
Test configuration for AutoDeal IA Hunter.
"""
from .base import BaseConfig


class TestConfig(BaseConfig):
    """Test configuration class."""
    
    DEBUG: bool = True
    ENVIRONMENT: str = "test"
    
    # Database
    DATABASE_URL: str = "sqlite:///./autodeal_test.db"
    
    # Scraping
    SCRAPING_INTERVAL_HOURS: int = 24
    MAX_LISTINGS_PER_SOURCE: int = 5
    
    # Cache
    CACHE_TTL_SECONDS: int = 60
    
    # Logging
    LOG_LEVEL: str = "DEBUG"


config = TestConfig()

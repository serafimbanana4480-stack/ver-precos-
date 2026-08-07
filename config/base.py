"""
Base configuration settings for AutoDeal IA Hunter.
"""
from pydantic_settings import BaseSettings
from pydantic_settings import SettingsConfigDict
from typing import Optional


class BaseConfig(BaseSettings):
    """Base configuration class."""

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )
    
    # Application
    APP_NAME: str = "AutoDeal IA Hunter"
    APP_VERSION: str = "1.0.0"
    DEBUG: bool = False
    ENVIRONMENT: str = "production"
    
    # Database
    DATABASE_URL: str = "sqlite:///data/autodeal.db"
    
    # Scraping
    SCRAPING_INTERVAL_HOURS: int = 6
    MAX_LISTINGS_PER_SOURCE: int = 50
    SCRAPING_TIMEOUT_SECONDS: int = 30
    USER_AGENT_ROTATION: bool = True
    
    # AI
    USE_OLLAMA: bool = False
    OLLAMA_URL: str = "http://localhost:11434"
    GROK_API_KEY: Optional[str] = None
    AI_TIMEOUT_SECONDS: int = 60
    
    # Notifications
    DISCORD_WEBHOOK_URL: Optional[str] = None
    EMAIL_SMTP_HOST: Optional[str] = None
    EMAIL_SMTP_PORT: int = 587
    EMAIL_SMTP_USER: Optional[str] = None
    EMAIL_SMTP_PASSWORD: Optional[str] = None
    TELEGRAM_BOT_TOKEN: Optional[str] = None
    TELEGRAM_CHAT_ID: Optional[str] = None
    
    # Deal Scoring
    DEAL_SCORE_THRESHOLD: float = 7.0
    MIN_PROFIT_EUROS: int = 1500
    
    # Cache
    CACHE_TTL_SECONDS: int = 3600
    CACHE_MAX_SIZE: int = 1000
    
config = BaseConfig()

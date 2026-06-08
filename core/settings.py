"""
Core Configuration Management
Production-grade settings with validation and environment-specific configs
"""
from __future__ import annotations
import os
from pathlib import Path
from typing import Optional, List
from pydantic_settings import BaseSettings, SettingsConfigDict
from pydantic import Field, validator
import logging

logger = logging.getLogger(__name__)


class Settings(BaseSettings):
    """Production-grade configuration management"""
    
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore"
    )
    
    # ==================== DATABASE ====================
    database_url: str = Field(
        default="sqlite:///autodeal.db",
        description="Database connection string"
    )
    
    # ==================== AI CONFIGURATION ====================
    use_ollama: bool = Field(
        default=True,
        description="Use local Ollama for AI"
    )
    
    ollama_url: str = Field(
        default="http://localhost:11434",
        description="Ollama API URL"
    )
    
    ai_model: str = Field(
        default="qwen2.5:7b",
        description="AI model name for Ollama"
    )
    
    vision_model: str = Field(
        default="qwen2.5:7b",
        description="Vision AI model name"
    )
    
    grok_api_key: str = Field(
        default="",
        description="Grok API key for fallback"
    )
    
    # ==================== SCRAPING CONFIGURATION ====================
    max_listings: int = Field(
        default=50,
        ge=1,
        le=500,
        description="Maximum listings to scrape per source"
    )
    
    request_timeout: int = Field(
        default=30,
        ge=5,
        le=120,
        description="HTTP request timeout in seconds"
    )
    
    request_delay: float = Field(
        default=2.0,
        ge=0.5,
        le=10.0,
        description="Base delay between requests in seconds"
    )
    
    request_delay_jitter: float = Field(
        default=1.0,
        ge=0.0,
        le=5.0,
        description="Random jitter for request delay"
    )
    
    max_retries: int = Field(
        default=3,
        ge=0,
        le=10,
        description="Maximum retry attempts for failed requests"
    )
    
    user_agents: List[str] = Field(
        default=[
            "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
            "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
            "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
        ],
        description="List of user agents to rotate through"
    )
    
    # ==================== PROXY CONFIGURATION ====================
    use_proxy: bool = Field(
        default=False,
        description="Enable proxy rotation"
    )
    
    proxy_list: str = Field(
        default="",
        description="Comma-separated list of proxy URLs"
    )
    
    proxy_strategy: str = Field(
        default="round_robin",
        description="Proxy rotation strategy: round_robin, random, least_used, health_score"
    )
    
    # ==================== CAPTCHA SOLVER ====================
    captcha_solver_enabled: bool = Field(
        default=True,
        description="Enable CAPTCHA solving"
    )
    
    captcha_solver_service: str = Field(
        default="2captcha",
        description="CAPTCHA solving service: 2captcha, anticaptcha"
    )
    
    captcha_solver_api_key: str = Field(
        default="",
        description="CAPTCHA solver API key"
    )
    
    # ==================== COMMERCIAL SCRAPING APIs ====================
    zenrows_api_key: str = Field(
        default="",
        description="ZenRows API key for commercial scraping"
    )
    
    scraperapi_key: str = Field(
        default="",
        description="ScraperAPI key for commercial scraping"
    )
    
    # ==================== REDIS CONFIGURATION ====================
    redis_url: str = Field(
        default="redis://localhost:6379/0",
        description="Redis connection URL for caching"
    )
    
    redis_ttl: int = Field(
        default=86400,
        ge=3600,
        le=604800,
        description="Redis TTL in seconds (default 24h)"
    )
    
    # ==================== LOGGING CONFIGURATION ====================
    log_level: str = Field(
        default="INFO",
        description="Logging level: DEBUG, INFO, WARNING, ERROR, CRITICAL"
    )
    
    log_format: str = Field(
        default="json",
        description="Log format: json, text"
    )
    
    log_file: str = Field(
        default="logs/autodeal.log",
        description="Log file path"
    )
    
    # ==================== NOTIFICATION CONFIGURATION ====================
    discord_webhook: str = Field(
        default="",
        description="Discord webhook URL for alerts"
    )
    
    telegram_bot_token: str = Field(
        default="",
        description="Telegram bot token"
    )
    
    telegram_chat_id: str = Field(
        default="",
        description="Telegram chat ID for notifications"
    )
    
    email_smtp_server: str = Field(
        default="",
        description="SMTP server for email notifications"
    )
    
    email_smtp_port: int = Field(
        default=587,
        description="SMTP port"
    )
    
    email_smtp_username: str = Field(
        default="",
        description="SMTP username"
    )
    
    email_smtp_password: str = Field(
        default="",
        description="SMTP password"
    )
    
    email_from: str = Field(
        default="",
        description="From email address"
    )
    
    email_to: List[str] = Field(
        default=[],
        description="List of recipient email addresses"
    )
    
    # ==================== SENTRY CONFIGURATION ====================
    sentry_dsn: str = Field(
        default="",
        description="Sentry DSN for error tracking"
    )
    
    sentry_environment: str = Field(
        default="development",
        description="Sentry environment name"
    )
    
    sentry_sample_rate: float = Field(
        default=0.1,
        ge=0.0,
        le=1.0,
        description="Sentry error sampling rate"
    )
    
    # ==================== DASHBOARD CONFIGURATION ====================
    dashboard_port: int = Field(
        default=8501,
        ge=8000,
        le=9000,
        description="Streamlit dashboard port"
    )
    
    # ==================== ML TRAINING CONFIGURATION ====================
    ml_min_samples: int = Field(
        default=500,
        ge=100,
        le=10000,
        description="Minimum samples required for ML training"
    )
    
    ml_min_r2: float = Field(
        default=0.6,
        ge=0.0,
        le=1.0,
        description="Minimum R² score for ML model acceptance"
    )
    
    ml_train_test_split: float = Field(
        default=0.2,
        ge=0.1,
        le=0.5,
        description="Train/test split ratio"
    )
    
    # ==================== DEAL SCORING CONFIGURATION ====================
    deal_score_threshold: float = Field(
        default=7.0,
        ge=0.0,
        le=10.0,
        description="Minimum deal score to alert"
    )
    
    top_deals_count: int = Field(
        default=20,
        ge=5,
        le=100,
        description="Number of top deals to return"
    )
    
    # ==================== SCRAPING INTERVALS ====================
    scrape_interval_hours: int = Field(
        default=6,
        ge=1,
        le=24,
        description="Hours between scraping runs"
    )
    
    ai_analysis_interval_hours: int = Field(
        default=24,
        ge=1,
        le=168,
        description="Hours between AI analysis runs"
    )
    
    # ==================== DATA DIRECTORIES ====================
    data_dir: str = Field(
        default="data",
        description="Data directory"
    )
    
    models_dir: str = Field(
        default="models",
        description="Models directory"
    )
    
    logs_dir: str = Field(
        default="logs",
        description="Logs directory"
    )
    
    # ==================== VALIDATION ====================
    @validator('log_level')
    def validate_log_level(cls, v):
        valid_levels = ['DEBUG', 'INFO', 'WARNING', 'ERROR', 'CRITICAL']
        if v.upper() not in valid_levels:
            raise ValueError(f'log_level must be one of {valid_levels}')
        return v.upper()
    
    @validator('proxy_strategy')
    def validate_proxy_strategy(cls, v):
        valid_strategies = ['round_robin', 'random', 'least_used', 'health_score']
        if v not in valid_strategies:
            raise ValueError(f'proxy_strategy must be one of {valid_strategies}')
        return v
    
    def validate_config(self) -> bool:
        """
        Validate configuration before starting
        
        Returns:
            True if configuration is valid
        """
        errors = []
        
        # Check if Ollama is configured and running
        if self.use_ollama:
            try:
                import requests
                response = requests.get(f"{self.ollama_url}/api/tags", timeout=2)
                if response.status_code != 200:
                    errors.append(f"Ollama not accessible at {self.ollama_url}")
            except Exception as e:
                errors.append(f"Ollama connection failed: {e}")
        
        # Check if database is accessible
        try:
            if self.database_url.startswith('sqlite'):
                db_path = self.database_url.replace('sqlite:///', '')
                Path(db_path).parent.mkdir(parents=True, exist_ok=True)
            elif self.database_url.startswith('postgresql'):
                # Would check PostgreSQL connection here
                pass
        except Exception as e:
            errors.append(f"Database configuration error: {e}")
        
        if errors:
            logger.error("Configuration validation failed:")
            for error in errors:
                logger.error(f"  - {error}")
            return False
        
        logger.info("Configuration validation passed")
        return True


# Singleton instance
settings = Settings()

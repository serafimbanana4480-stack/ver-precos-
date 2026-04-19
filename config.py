"""
Simplified Configuration file for AutoDeal IA Hunter
Essential configuration only - ~100 lines
"""
from __future__ import annotations
import os
from pathlib import Path
from typing import List, Dict, Optional
from dotenv import load_dotenv
from pydantic_settings import BaseSettings, SettingsConfigDict

# Load environment variables
load_dotenv()

# Base paths
BASE_DIR = Path(__file__).parent.absolute()
DATA_DIR = BASE_DIR / "data"
MODELS_DIR = BASE_DIR / "models"
LOGS_DIR = BASE_DIR / "logs"

# Create directories if they don't exist
DATA_DIR.mkdir(exist_ok=True)
MODELS_DIR.mkdir(exist_ok=True)
LOGS_DIR.mkdir(exist_ok=True)


class Settings(BaseSettings):
    """Simplified configuration class with essential settings only"""
    
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore"
    )
    
    # Database Configuration
    use_sqlite: bool = True
    database_url: str = "sqlite:///autodeal.db"
    
    # Scraping URLs
    olx_base_url: str = "https://www.olx.pt"
    standvirtual_base_url: str = "https://www.standvirtual.com"
    autosapo_base_url: str = "https://autos.sapo.pt"
    
    # AI Configuration (100% free local with Ollama)
    use_ollama: bool = True
    ollama_url: str = "http://localhost:11434"
    grok_api_key: str = ""  # Optional: for Grok API fallback
    ai_model: str = "glm-5:latest"
    ai_scraper_model: str = "glm-5:latest"
    ai_scraping_enabled: bool = True
    ai_scraper_fallback_enabled: bool = True
    ai_scraper_priority: str = "primary"  # "fallback" or "primary"
    
    # Scraping Configuration
    max_listings: int = 50
    scraper_timeout: int = 30
    request_delay_seconds: float = 2.0
    max_retries: int = 3
    user_agents: list = [
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
        "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
        "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
    ]
    apify_enabled: bool = False
    scraperapi_enabled: bool = False
    zenrows_enabled: bool = False
    watchlist_file: str = "data/watchlist.json"
    model_features: list = ["brand", "model", "year", "mileage", "fuel_type", "transmission"]
    playwright_timeout: int = 30000
    playwright_headless: bool = True
    
    # Optional Paid API Fallback
    zenrows_api_key: str = ""
    scraperapi_key: str = ""
    
    # Proxy Configuration for Anti-Blocking
    use_proxy: bool = False
    proxy_list: str = ""  # Comma-separated list of proxies (host:port or user:pass@host:port)
    proxy_host: str = ""
    proxy_port: int = 8080
    proxy_username: str = ""
    proxy_password: str = ""
    proxy_rotation_strategy: str = "health_score"  # round_robin, random, least_used, health_score
    
    # CAPTCHA Solving
    twocaptcha_api_key: str = ""
    anticaptcha_api_key: str = ""
    captcha_solver_enabled: bool = True
    
    # Enhanced Rate Limiting
    max_requests_per_minute: int = 30
    request_delay_jitter: float = 1.0  # Random delay variation
    
    # Redis Configuration
    use_redis: bool = False
    redis_url: str = "redis://localhost:6379"
    deduplication_window: int = 3600  # 1 hour in seconds
    
    # Rust OLX Tracker
    olx_tracker_path: str = "./olx-tracker/target/release/olx-tracker"
    
    # Basic logging
    log_level: str = "INFO"
    log_format: str = "%(asctime)s - %(name)s - %(levelname)s - %(message)s"
    log_max_bytes: int = 10485760  # 10MB
    log_backup_count: int = 5
    log_file: str = "logs/autodeal.log"
    
    # Notifications (optional)
    discord_webhook: str = ""
    telegram_bot_token: str = ""
    telegram_chat_id: str = ""
    email_to: str = ""
    email_smtp_server: str = ""
    email_smtp_port: int = 587
    email_smtp_user: str = ""
    email_smtp_password: str = ""
    
    # Sentry Configuration (optional)
    sentry_dsn: str = ""
    sentry_environment: str = "development"
    sentry_sample_rate: float = 1.0
    
    # Dashboard
    dashboard_port: int = 8501
    
    # ML Configuration
    min_training_samples: int = 10
    
    @property
    def models_dir(self) -> Path:
        return MODELS_DIR
    
    # AI Agent Settings
    top_deals_count: int = 20
    
    # Logging patterns for sensitive data filtering
    sensitive_patterns: List[str] = [
        "password", "token", "api_key", "secret", "authorization"
    ]
    
    @property
    def model_path(self) -> Path:
        return MODELS_DIR / "xgboost_model.json"
    
    @property
    def export_dir(self) -> Path:
        return DATA_DIR / "exports"
    
    @property
    def vehicle_types(self) -> List[str]:
        return ["carros", "motos"]
    
    def validate_config(self) -> bool:
        """Validate essential configuration"""
        if not self.database_url:
            print("ERROR: database_url cannot be empty")
            return False
        return True


# Create settings instance
settings = Settings()

# Create directories that depend on settings
settings.export_dir.mkdir(exist_ok=True)

# Backward compatibility aliases
use_sqlite = "sqlite" in settings.database_url
postgres_user = "autodeal"
postgres_password = "autodeal_password"
postgres_db = "autodeal"
postgres_host = "localhost"
postgres_port = 5432

# AI aliases
grok_api_key = ""
grok_api_url = "https://api.x.ai/v1"
llm_model = settings.ai_model
vision_model = settings.ai_model
ai_scraper_model = settings.ai_model
ai_scraper_fallback_enabled = True
use_ollama = True

# Scraping aliases
scraping_interval_hours = 6
max_listings_per_source = settings.max_listings

# API aliases
scraperapi_key = ""
apify_api_key = ""
zenrows_key = settings.zenrows_api_key
use_hybrid_scraper = True

# Dashboard aliases
streamlit_port = settings.dashboard_port

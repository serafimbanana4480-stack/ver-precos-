"""
Configuration file for AutoDeal IA Hunter
Centralized configuration management using pydantic-settings
"""
import os
from pathlib import Path
from typing import List
from dotenv import load_dotenv
from pydantic_settings import BaseSettings, SettingsConfigDict
from pydantic import field_validator, EmailStr

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
    """Main configuration class using pydantic-settings"""
    
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore"
    )
    
    # Database Configuration
    use_sqlite: bool = True
    database_url: str = "sqlite:///autodeal.db"
    postgres_user: str = "autodeal"
    postgres_password: str = "autodeal_password"
    postgres_db: str = "autodeal"
    postgres_host: str = "localhost"
    postgres_port: int = 5432
    
    # AI Configuration
    grok_api_key: str = ""
    grok_api_url: str = "https://api.x.ai/v1"
    ollama_url: str = "http://localhost:11434"
    use_ollama: bool = False
    llm_model: str = "grok-2-vision"
    vision_model: str = "grok-2-vision"
    
    # Scraping Configuration
    scraping_interval_hours: int = 6
    max_listings_per_source: int = 100
    request_delay_seconds: float = 2.0
    max_retries: int = 3
    
    # Deal Scoring Configuration
    min_profit_margin_eur: float = 1500.0
    max_profit_margin_percent: float = 25.0
    deal_score_threshold: float = 7.0
    top_deals_count: int = 20
    ai_review_count: int = 50
    
    # ML Model Configuration
    min_training_samples: int = 10
    
    # Notification Configuration
    discord_webhook_url: str = ""
    email_smtp_host: str = "smtp.gmail.com"
    email_smtp_port: int = 587
    email_smtp_user: str = ""
    email_smtp_password: str = ""
    email_from: str = ""
    email_to: str = ""
    telegram_bot_token: str = ""
    telegram_chat_id: str = ""
    
    # Dashboard Configuration
    dashboard_port: int = 8501
    dashboard_host: str = "0.0.0.0"
    
    # Logging Configuration
    log_level: str = "INFO"
    log_format: str = "%(asctime)s - %(name)s - %(levelname)s - %(message)s"
    
    # Scheduler Configuration
    scheduler_timezone: str = "Europe/Lisbon"
    daily_scraping_time: str = "08:00"
    
    # Rust OLX Tracker Configuration
    olx_tracker_path: str = "./olx-tracker/target/release/olx-tracker"
    
    # Playwright Configuration
    playwright_headless: bool = True
    playwright_timeout: int = 30000
    
    # Redis Configuration (for caching, optional)
    redis_url: str = "redis://localhost:6379/0"
    use_redis: bool = False
    
    # Proxy Configuration (optional)
    use_proxy: bool = False
    proxy_url: str = ""
    
    # Rate Limiting
    max_requests_per_minute: int = 30
    
    # Validation Configuration
    validation_strict_mode: bool = False
    validation_failure_threshold: int = 10
    validation_alert_enabled: bool = True
    
    # Validation Override Rules (JSON format)
    # Example: {"year": {"min": 1980}, "price": {"min": 100}}
    # This allows overriding validation rules for specific fields
    validation_override_rules: str = "{}"  # JSON string of override rules
    
    # Sentry Configuration
    sentry_dsn: str = ""
    sentry_environment: str = "development"
    sentry_sample_rate: float = 0.1
    
    # Health Check Configuration
    health_check_timeout: int = 5
    
    # Alert Configuration
    alert_enabled: bool = True
    alert_min_level: str = "ERROR"
    alert_aggregation_window: int = 300
    alert_aggregation_enabled: bool = True
    
    # Metrics Configuration
    scraping_metrics_enabled: bool = True
    scraping_success_threshold: float = 0.8
    ai_metrics_enabled: bool = True
    ai_latency_threshold_ms: int = 5000
    ai_failure_alert_threshold: float = 0.2
    scheduler_metrics_enabled: bool = True
    scheduler_duration_threshold_seconds: int = 3600
    
    # Logging Configuration
    log_max_bytes: int = 10485760
    log_backup_count: int = 5
    log_format_type: str = "text"  # text or json
    sensitive_patterns: str = "api_key|password|token|secret"
    
    # Deduplication Configuration
    deduplication_window: int = 3600  # 1 hour in seconds
    
    @field_validator('email_to', mode='before')
    @classmethod
    def parse_email_to(cls, v):
        if isinstance(v, str):
            return v
        if isinstance(v, list):
            return ",".join(v)
        return ""
    
    @field_validator('database_url')
    @classmethod
    def validate_database_url(cls, v):
        if not v:
            raise ValueError('database_url cannot be empty')
        return v
    
    @field_validator('dashboard_port', 'email_smtp_port', 'postgres_port')
    @classmethod
    def validate_port(cls, v):
        if not (1 <= v <= 65535):
            raise ValueError('port must be between 1 and 65535')
        return v
    
    @field_validator('min_profit_margin_eur', 'max_profit_margin_percent', 'deal_score_threshold')
    @classmethod
    def validate_positive_float(cls, v):
        if v < 0:
            raise ValueError('value must be positive')
        return v
    
    @property
    def model_path(self) -> Path:
        return MODELS_DIR / "xgboost_model.json"
    
    @property
    def log_file(self) -> Path:
        return LOGS_DIR / "autodeal.log"
    
    @property
    def export_dir(self) -> Path:
        return DATA_DIR / "exports"
    
    @property
    def watchlist_file(self) -> Path:
        return DATA_DIR / "watchlist.json"
    
    @property
    def user_agents(self) -> List[str]:
        return [
            "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
            "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
            "Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:121.0) Gecko/20100101 Firefox/121.0",
            "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/17.1 Safari/605.1.15",
        ]
    
    @property
    def olx_base_url(self) -> str:
        return "https://www.olx.pt"
    
    @property
    def standvirtual_base_url(self) -> str:
        return "https://www.standvirtual.com"
    
    @property
    def autosapo_base_url(self) -> str:
        return "https://autos.sapo.pt"
    
    @property
    def vehicle_types(self) -> List[str]:
        return ["carros", "motos"]
    
    @property
    def model_features(self) -> List[str]:
        return [
            "year", "km", "price", "horsepower", "engine_size",
            "brand_encoded", "model_encoded", "fuel_type_encoded",
            "transmission_encoded", "location_encoded"
        ]
    
    def validate(self) -> bool:
        """Validate required configuration"""
        errors = []
        
        # AI API is optional for basic operations
        # if not self.use_ollama and not self.grok_api_key:
        #     errors.append("GROK_API_KEY is required when not using Ollama")
            
        if errors:
            print("Configuration errors:")
            for error in errors:
                print(f"  - {error}")
            return False
            
        return True


# Create settings instance
settings = Settings()

# Create directories that depend on settings
settings.export_dir.mkdir(exist_ok=True)

# Backward compatibility aliases
config = settings

from __future__ import annotations
import os
import re
import secrets
from pathlib import Path
from typing import List, Optional
from pydantic_settings import BaseSettings, SettingsConfigDict
from pydantic import Field, field_validator
import logging

logger = logging.getLogger(__name__)

BASE_DIR = Path(__file__).parent.parent.absolute()
DATA_DIR = BASE_DIR / "data"
MODELS_DIR = BASE_DIR / "models"
LOGS_DIR = BASE_DIR / "logs"

DATA_DIR.mkdir(exist_ok=True)
MODELS_DIR.mkdir(exist_ok=True)
LOGS_DIR.mkdir(exist_ok=True)


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=str(BASE_DIR / ".env"),
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",
    )

    # ==================== ENVIRONMENT ====================
    env: str = Field(default="development", description="Environment: development, staging, production")

    @property
    def is_production(self) -> bool:
        return self.env.lower() == "production"

    @property
    def is_development(self) -> bool:
        return self.env.lower() == "development"

    # ==================== DATABASE ====================
    database_url: str = Field(
        default="sqlite:///autodeal.db",
        description="Database connection string (SQLite or PostgreSQL)",
    )

    @property
    def use_sqlite(self) -> bool:
        return self.database_url.startswith("sqlite")

    @property
    def use_postgresql(self) -> bool:
        return self.database_url.startswith("postgresql")

    @property
    def resolved_db_url(self) -> str:
        """Return absolute database URL, resolving relative SQLite paths."""
        url = self.database_url
        if url.startswith("sqlite:///"):
            path = url[10:]
            if not os.path.isabs(path):
                path = str(BASE_DIR / path)
                return f"sqlite:///{path}"
        return url

    # ==================== SCRAPING URLS ====================
    olx_base_url: str = Field(default="https://www.olx.pt")
    standvirtual_base_url: str = Field(default="https://www.standvirtual.com")
    autosapo_base_url: str = Field(default="https://www.autosapo.pt")
    autoscout24_base_url: str = Field(default="https://www.autoscout24.pt")

    # ==================== PLAYWRIGHT ====================
    playwright_headless: bool = Field(default=True)
    playwright_timeout: int = Field(default=30000, ge=5000, le=120000)

    # ==================== OLX TRACKER ====================
    olx_tracker_path: str = Field(
        default=str(MODELS_DIR / "olx-tracker" / "target" / "release" / "olx-tracker"),
        description="Path to the rust olx-tracker binary",
    )

    # ==================== AI CONFIGURATION ====================
    use_ollama: bool = Field(default=True)
    ollama_url: str = Field(default="http://localhost:11434")
    grok_api_key: str = Field(default="")
    ai_model: str = Field(default="qwen2.5:7b")
    ai_scraper_model: str = Field(default="qwen2.5:7b")
    ai_scraping_enabled: bool = Field(default=True)
    ai_scraper_fallback_enabled: bool = Field(default=True)
    ai_scraper_priority: str = Field(default="primary")
    enable_pipeline_llm: bool = Field(default=True)
    enable_pipeline_vision: bool = Field(default=True)
    fast_scrape_mode: bool = Field(default=False)
    vision_model: str = Field(default="qwen2.5:7b")

    # ==================== APIFY ====================
    apify_enabled: bool = Field(default=False)
    apify_api_key: str = Field(default="")

    # ==================== SCRAPING BEHAVIOR ====================
    max_listings: int = Field(default=50, ge=1, le=500)
    scraper_timeout: int = Field(default=30, ge=5, le=120)
    request_timeout: int = Field(default=30, ge=5, le=120)
    scraping_interval_hours: int = Field(default=6, ge=1, le=24, alias="scrape_interval_hours")
    daily_scraping_time: str = Field(default="08:00")
    request_delay_seconds: float = Field(default=2.0, ge=0.5, le=10.0)
    request_delay_jitter: float = Field(default=1.0, ge=0.0, le=5.0)
    max_retries: int = Field(default=3, ge=0, le=10)
    max_requests_per_minute: int = Field(default=30, ge=1, le=300)

    user_agents: List[str] = Field(default=[
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
        "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
        "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:120.0) Gecko/20100101 Firefox/120.0",
        "Mozilla/5.0 (Macintosh; Intel Mac OS X 10.15; rv:120.0) Gecko/20100101 Firefox/120.0",
        "Mozilla/5.0 (X11; Ubuntu; Linux x86_64; rv:120.0) Gecko/20100101 Firefox/120.0",
    ])

    # ==================== SCRAPING COMMERCIAL APIS ====================
    scraperapi_enabled: bool = Field(default=False)
    zenrows_enabled: bool = Field(default=False)
    zenrows_api_key: str = Field(default="")
    scraperapi_key: str = Field(default="")

    # ==================== PROXY ====================
    use_proxy: bool = Field(default=False)
    proxy_list: str = Field(default="")
    proxy_host: str = Field(default="")
    proxy_port: int = Field(default=8080, ge=1, le=65535)
    proxy_username: str = Field(default="")
    proxy_password: str = Field(default="")
    proxy_rotation_strategy: str = Field(default="health_score")

    # ==================== CAPTCHA ====================
    captcha_solver_enabled: bool = Field(default=True)
    twocaptcha_api_key: str = Field(default="")
    anticaptcha_api_key: str = Field(default="")

    # ==================== REDIS ====================
    use_redis: bool = Field(default=False)
    redis_url: str = Field(default="redis://localhost:6379")
    redis_ttl: int = Field(default=86400, ge=3600, le=604800)
    deduplication_window: int = Field(default=3600, ge=60, le=86400)

    # ==================== LOGGING ====================
    log_level: str = Field(default="INFO")
    log_format: str = Field(default="json")
    log_max_bytes: int = Field(default=10485760)
    log_backup_count: int = Field(default=5)
    log_file: str = Field(default="logs/autodeal.log")

    @field_validator("log_level")
    @classmethod
    def validate_log_level(cls, v: str) -> str:
        valid = {"DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"}
        upper = v.upper()
        if upper not in valid:
            raise ValueError(f"log_level must be one of {valid}")
        return upper

    # ==================== NOTIFICATIONS ====================
    discord_webhook: str = Field(default="")
    telegram_bot_token: str = Field(default="")
    telegram_chat_id: str = Field(default="")
    email_to: str = Field(default="")
    email_smtp_server: str = Field(default="")
    email_smtp_port: int = Field(default=587, ge=1, le=65535)
    email_smtp_user: str = Field(default="")
    email_smtp_password: str = Field(default="")

    # ==================== API / SECURITY ====================
    jwt_secret: str = Field(default="")
    jwt_algorithm: str = Field(default="HS256")
    cors_origins: str = Field(default="http://localhost:8501,http://127.0.0.1:8501")

    @property
    def cors_origins_list(self) -> List[str]:
        if not self.cors_origins.strip():
            return ["http://localhost:8501"]
        return [o.strip() for o in self.cors_origins.split(",") if o.strip()]

    def resolve_jwt_secret(self) -> str:
        secret = (self.jwt_secret or os.getenv("JWT_SECRET", "")).strip()
        if secret:
            return secret
        if self.is_production:
            raise RuntimeError("JWT_SECRET must be set when env=production")
        return "dev-" + secrets.token_urlsafe(32)

    # ==================== SENTRY ====================
    sentry_dsn: str = Field(default="")
    sentry_environment: str = Field(default="development")
    sentry_sample_rate: float = Field(default=0.1, ge=0.0, le=1.0)

    # ==================== DASHBOARD ====================
    dashboard_port: int = Field(default=8501, ge=8000, le=9000)

    # ==================== ML ====================
    ml_min_samples: int = Field(default=500, ge=100, le=10000)
    ml_min_r2: float = Field(default=0.6, ge=0.0, le=1.0)
    ml_train_test_split: float = Field(default=0.2, ge=0.1, le=0.5)
    model_features: List[str] = Field(default=[
        "brand", "model", "year", "mileage", "fuel_type", "transmission",
    ])

    # ==================== DEAL SCORING ====================
    deal_score_threshold: float = Field(default=7.0, ge=0.0, le=10.0)
    top_deals_count: int = Field(default=20, ge=5, le=100)
    ai_review_count: int = Field(default=50)

    # ==================== VALIDATION ====================
    validation_strict_mode: bool = Field(default=False)
    validation_failure_threshold: int = Field(default=100)
    validation_alert_enabled: bool = Field(default=False)

    # ==================== WATCHLIST ====================
    watchlist_file: str = Field(default="data/watchlist.json")

    # ==================== SENSITIVE PATTERNS ====================
    sensitive_patterns: List[str] = Field(default=[
        "password", "token", "api_key", "secret", "authorization",
    ])

    # ==================== VEHICLE TYPES ====================
    vehicle_types: List[str] = Field(default=["carros", "motos"])

    # ==================== DATA DIRECTORIES ====================
    data_dir: str = Field(default="data")
    models_dir: str = Field(default="models")
    logs_dir: str = Field(default="logs")

    # ==================== PROPERTIES ====================
    @property
    def model_path(self) -> Path:
        return Path(self.models_dir) / "xgboost_model.json"

    @property
    def log_file_path(self) -> str:
        return str(Path(self.logs_dir) / "autodeal.log")

    @property
    def export_dir(self) -> Path:
        return Path(self.data_dir) / "exports"

    # ==================== VALIDATORS ====================
    @field_validator("proxy_rotation_strategy")
    @classmethod
    def validate_proxy_strategy(cls, v: str) -> str:
        valid = {"round_robin", "random", "least_used", "health_score"}
        if v not in valid:
            raise ValueError(f"proxy_rotation_strategy must be one of {valid}")
        return v

    @field_validator("daily_scraping_time")
    @classmethod
    def validate_scraping_time(cls, v: str) -> str:
        if not re.match(r"^([01]?[0-9]|2[0-3]):[0-5][0-9]$", v):
            raise ValueError(f"daily_scraping_time must be HH:MM format, got {v!r}")
        return v

    @field_validator("ai_scraper_priority")
    @classmethod
    def validate_ai_priority(cls, v: str) -> str:
        valid = {"primary", "fallback"}
        if v not in valid:
            raise ValueError(f"ai_scraper_priority must be one of {valid}")
        return v

    def model_post_init(self, __context):
        """Resolve relative paths to absolute."""
        # Make relative directory paths absolute using BASE_DIR
        for attr in ('models_dir', 'data_dir', 'logs_dir'):
            val = getattr(self, attr, None)
            if val and not os.path.isabs(val):
                setattr(self, attr, str(BASE_DIR / val))

    # ==================== METHODS ====================
    def validate_config(self) -> bool:
        errors = []
        if not self.database_url:
            errors.append("database_url cannot be empty")
        if self.env not in ("development", "staging", "production"):
            errors.append(f"Invalid env: {self.env!r}")
        if errors:
            logger.error("Configuration validation failed:")
            for e in errors:
                logger.error(f"  - {e}")
            return False
        return True

    def check_ollama_available(self) -> bool:
        if not self.use_ollama:
            logger.info("Ollama disabled, skipping check")
            return False
        try:
            import requests
            resp = requests.get(f"{self.ollama_url}/api/tags", timeout=5)
            return resp.status_code == 200
        except Exception as e:
            logger.warning(f"Ollama check failed: {e}")
            return False


settings = Settings()
settings.export_dir.mkdir(exist_ok=True)

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
    database_url: str = "sqlite:///autodeal.db"
    
    # Scraping URLs
    olx_base_url: str = "https://www.olx.pt"
    standvirtual_base_url: str = "https://www.standvirtual.com"
    autosapo_base_url: str = "https://autos.sapo.pt"
    
    # AI Configuration (100% free local with Ollama)
    ollama_url: str = "http://localhost:11434"
    ai_model: str = "glm-5:latest"
    ai_scraping_enabled: bool = True
    ai_scraping_priority: str = "primary"  # "fallback" or "primary"
    
    # Scraping Configuration
    max_listings: int = 50
    scraper_timeout: int = 30
    request_delay_seconds: float = 2.0
    max_retries: int = 3
    
    # Optional Paid API Fallback
    zenrows_api_key: str = ""
    
    # Basic logging
    log_level: str = "INFO"
    
    # Dashboard
    dashboard_port: int = 8501
    
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

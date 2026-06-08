"""
Logging configuration for AutoDeal IA Hunter.
"""
from pydantic import BaseModel
from typing import Dict, List


class LoggingConfig(BaseModel):
    """Configuration for logging settings."""
    
    level: str = "INFO"
    format: str = "%(asctime)s - %(name)s - %(levelname)s - %(message)s"
    date_format: str = "%Y-%m-%d %H:%M:%S"
    
    # File logging
    log_file: str = "logs/autodeal.log"
    log_file_max_bytes: int = 10485760  # 10MB
    log_file_backup_count: int = 5
    
    # Console logging
    console_enabled: bool = True
    console_level: str = "INFO"
    
    # Structured logging
    structured: bool = False
    json_format: bool = False
    
    # Loggers
    loggers: Dict[str, str] = {
        "": "INFO",
        "scrapers": "DEBUG",
        "ai_agent": "DEBUG",
        "valuation": "INFO",
        "database": "INFO",
        "scheduler": "INFO",
    }
    
    # Sensitive data filtering
    filter_sensitive_data: bool = True
    sensitive_fields: List[str] = ["api_key", "password", "token", "webhook"]


logging_config = LoggingConfig()

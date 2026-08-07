"""
Database configuration for AutoDeal IA Hunter.
"""
from pydantic import BaseModel
from typing import Optional


class DatabaseConfig(BaseModel):
    """Configuration for database settings."""
    
    url: str = "sqlite:///./data/autodeal.db"
    pool_size: int = 5
    max_overflow: int = 10
    pool_timeout: int = 30
    pool_recycle: int = 3600
    echo: bool = False
    
    # Connection settings
    connect_timeout: int = 10
    statement_timeout: int = 30
    
    # Migration settings
    auto_migrate: bool = True
    migration_dir: str = "alembic"
    
    # Backup settings
    auto_backup: bool = True
    backup_interval_hours: int = 24
    backup_retention_days: int = 7
    
    # Performance settings
    enable_query_logging: bool = False
    enable_slow_query_log: bool = True
    slow_query_threshold_ms: int = 1000


database_config = DatabaseConfig()

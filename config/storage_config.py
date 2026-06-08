"""
Storage configuration for AutoDeal IA Hunter.
"""
from pydantic import BaseModel
from typing import Optional


class StorageConfig(BaseModel):
    """Configuration for storage settings."""
    
    # Local storage
    local_enabled: bool = True
    local_data_dir: str = "data"
    local_models_dir: str = "models"
    local_exports_dir: str = "exports"
    local_logs_dir: str = "logs"
    
    # S3 storage
    s3_enabled: bool = False
    s3_bucket: Optional[str] = None
    s3_region: str = "eu-west-1"
    s3_access_key: Optional[str] = None
    s3_secret_key: Optional[str] = None
    
    # Storage policies
    auto_cleanup: bool = True
    cleanup_days: int = 30
    max_storage_gb: int = 100


storage_config = StorageConfig()

"""
API configuration for AutoDeal IA Hunter.
"""
from pydantic import BaseModel
from typing import List


class APIConfig(BaseModel):
    """Configuration for API settings."""
    
    enabled: bool = True
    host: str = "0.0.0.0"
    port: int = 8000
    workers: int = 4
    reload: bool = False
    
    # API versioning
    api_version: str = "v1"
    api_prefix: str = "/api"
    
    # Documentation
    docs_enabled: bool = True
    redoc_enabled: bool = True
    openapi_url: str = "/openapi.json"
    
    # Pagination
    default_page_size: int = 20
    max_page_size: int = 100
    
    # Rate limiting
    rate_limit_enabled: bool = True
    rate_limit_per_minute: int = 60
    
    # CORS
    cors_origins: List[str] = ["http://localhost:8501"]
    cors_methods: List[str] = ["GET", "POST", "PUT", "DELETE"]
    cors_headers: List[str] = ["Content-Type", "Authorization"]


api_config = APIConfig()

"""
Security configuration for AutoDeal IA Hunter.
"""
from pydantic import BaseModel
from typing import List, Optional


class SecurityConfig(BaseModel):
    """Configuration for security settings."""
    
    # API Security
    api_key_required: bool = False
    api_key_header: str = "X-API-Key"
    rate_limit_enabled: bool = True
    rate_limit_per_minute: int = 60
    
    # CORS
    cors_enabled: bool = True
    cors_origins: List[str] = ["http://localhost:8501"]
    cors_methods: List[str] = ["GET", "POST", "PUT", "DELETE"]
    cors_headers: List[str] = ["Content-Type", "Authorization"]
    
    # OWASP Headers
    enable_security_headers: bool = True
    hsts_enabled: bool = True
    hsts_max_age: int = 31536000
    frame_options: str = "DENY"
    content_type_options: bool = True
    xss_protection: bool = True
    
    # Secrets
    secret_key: Optional[str] = None
    encryption_key: Optional[str] = None
    
    # Authentication
    jwt_enabled: bool = False
    jwt_secret: Optional[str] = None
    jwt_algorithm: str = "HS256"
    jwt_expiration_hours: int = 24
    
    # RBAC
    rbac_enabled: bool = False
    default_role: str = "user"


security_config = SecurityConfig()

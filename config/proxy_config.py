"""
Proxy configuration for AutoDeal IA Hunter.
"""
from pydantic import BaseModel
from typing import List, Optional


class ProxyConfig(BaseModel):
    """Configuration for proxy settings."""
    
    enabled: bool = False
    rotation_enabled: bool = True
    
    # Proxy list
    proxy_list: List[str] = []
    
    # Proxy settings
    proxy_timeout_seconds: int = 10
    proxy_max_retries: int = 3
    
    # Proxy authentication
    proxy_auth_enabled: bool = False
    proxy_username: Optional[str] = None
    proxy_password: Optional[str] = None
    
    # Proxy rotation
    rotation_strategy: str = "round_robin"  # round_robin, random, least_used
    rotation_interval_minutes: int = 30
    
    # Proxy health check
    health_check_enabled: bool = True
    health_check_interval_minutes: int = 5
    health_check_timeout_seconds: int = 5
    
    # Proxy fallback
    fallback_to_direct: bool = True
    fallback_after_failures: int = 3


proxy_config = ProxyConfig()

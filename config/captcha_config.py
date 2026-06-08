"""
Captcha configuration for AutoDeal IA Hunter.
"""
from pydantic import BaseModel
from typing import Optional


class CaptchaConfig(BaseModel):
    """Configuration for CAPTCHA solving."""
    
    enabled: bool = True
    provider: str = "manual"  # manual, 2captcha, anticaptcha, deathbycaptcha
    
    # 2Captcha
    two_captcha_api_key: Optional[str] = None
    two_captcha_timeout_seconds: int = 120
    
    # AntiCaptcha
    anti_captcha_api_key: Optional[str] = None
    anti_captcha_timeout_seconds: int = 120
    
    # DeathByCaptcha
    deathbycaptcha_api_key: Optional[str] = None
    deathbycaptcha_timeout_seconds: int = 120
    
    # CAPTCHA detection
    auto_detect: bool = True
    detection_threshold: float = 0.8
    
    # CAPTCHA solving
    max_attempts: int = 3
    retry_delay_seconds: int = 10
    
    # Rate limiting after CAPTCHA
    cooldown_minutes: int = 30


captcha_config = CaptchaConfig()

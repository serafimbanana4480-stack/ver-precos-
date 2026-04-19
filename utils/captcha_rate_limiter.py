"""
CAPTCHA Rate Limiter and Alerting
Prevents excessive CAPTCHA solving attempts and alerts on high CAPTCHA rates
"""
from __future__ import annotations
import logging
from typing import Dict, Any, Optional
from datetime import datetime, timezone, timedelta
from collections import deque

from config import settings

logger = logging.getLogger(__name__)


class CaptchaRateLimiter:
    """Rate limiter for CAPTCHA solving attempts"""
    
    def __init__(self) -> None:
        self.captcha_events: deque[Dict[str, Any]] = deque()
        self.max_captchas_per_hour = 10  # Maximum CAPTCHAs per hour
        self.alert_threshold = 5  # Alert after this many CAPTCHAs in hour
        self.cooldown_period = timedelta(minutes=5)  # Cooldown after CAPTCHA detection
    
    def record_captcha(self, source: str, captcha_type: str) -> Dict[str, Any]:
        """
        Record a CAPTCHA detection
        
        Args:
            source: Source where CAPTCHA was detected (e.g., 'olx', 'standvirtual')
            captcha_type: Type of CAPTCHA (e.g., 'recaptcha_v2', 'hcaptcha')
            
        Returns:
            Dictionary with rate limiting decision
        """
        now = datetime.now(timezone.utc)
        
        # Remove events older than 1 hour
        while self.captcha_events and (now - self.captcha_events[0]['timestamp']) > timedelta(hours=1):
            self.captcha_events.popleft()
        
        event = {
            'timestamp': now,
            'source': source,
            'captcha_type': captcha_type
        }
        
        self.captcha_events.append(event)
        
        # Check if we should alert
        should_alert = len(self.captcha_events) >= self.alert_threshold
        
        if should_alert:
            logger.warning(
                f"[CAPTCHA RATE] High CAPTCHA rate detected: {len(self.captcha_events)} in last hour. "
                f"Sources: {[e['source'] for e in self.captcha_events]}"
            )
        
        # Check if we're over the limit
        over_limit = len(self.captcha_events) >= self.max_captchas_per_hour
        
        if over_limit:
            logger.error(
                f"[CAPTCHA RATE] CAPTCHA limit exceeded: {len(self.captcha_events)} in last hour. "
                f"Stopping CAPTCHA solving attempts."
            )
        
        return {
            'allowed': not over_limit,
            'alert_triggered': should_alert,
            'count_last_hour': len(self.captcha_events),
            'max_per_hour': self.max_captchas_per_hour
        }
    
    def get_stats(self) -> Dict[str, Any]:
        """Get rate limiter statistics"""
        now = datetime.now(timezone.utc)
        
        # Count CAPTCHAs by source in last hour
        source_counts: Dict[str, int] = {}
        for event in self.captcha_events:
            if (now - event['timestamp']) <= timedelta(hours=1):
                source_counts[event['source']] = source_counts.get(event['source'], 0) + 1
        
        return {
            'total_last_hour': len(self.captcha_events),
            'by_source': source_counts,
            'max_per_hour': self.max_captchas_per_hour,
            'alert_threshold': self.alert_threshold
        }
    
    def should_solve(self) -> bool:
        """Check if we should attempt to solve a CAPTCHA"""
        stats = self.get_stats()
        return stats['total_last_hour'] < self.max_captchas_per_hour


class CaptchaDelayEscalator:
    """Escalates delays between attempts when CAPTCHAs are detected"""
    
    def __init__(self):
        self.captcha_count = 0
        self.last_captcha_time: Optional[datetime] = None
        self.base_delay = 60  # Base delay in seconds
        self.max_delay = 3600  # Maximum delay (1 hour)
    
    def record_captcha(self) -> None:
        """Record a CAPTCHA detection"""
        self.captcha_count += 1
        self.last_captcha_time = datetime.now(timezone.utc)
        logger.warning(f"[CAPTCHA DELAY] CAPTCHA detected (count: {self.captcha_count})")
    
    def get_delay(self) -> int:
        """
        Get recommended delay before next attempt
        
        Returns:
            Delay in seconds
        """
        if self.captcha_count == 0:
            return 0
        
        # Exponential backoff: base_delay * 2^(count-1)
        delay = min(self.base_delay * (2 ** (self.captcha_count - 1)), self.max_delay)
        
        logger.info(f"[CAPTCHA DELAY] Recommended delay: {delay}s (count: {self.captcha_count})")
        return delay
    
    def reset(self) -> None:
        """Reset counter after successful attempt"""
        if self.captcha_count > 0:
            logger.info(f"[CAPTCHA DELAY] Resetting counter (was {self.captcha_count})")
            self.captcha_count = 0


# Global instances
_captcha_rate_limiter: CaptchaRateLimiter = None
_captcha_delay_escalator: CaptchaDelayEscalator = None


def get_captcha_rate_limiter() -> CaptchaRateLimiter:
    """Get the global CAPTCHA rate limiter"""
    global _captcha_rate_limiter
    if _captcha_rate_limiter is None:
        _captcha_rate_limiter = CaptchaRateLimiter()
    return _captcha_rate_limiter


def get_captcha_delay_escalator() -> CaptchaDelayEscalator:
    """Get the global CAPTCHA delay escalator"""
    global _captcha_delay_escalator
    if _captcha_delay_escalator is None:
        _captcha_delay_escalator = CaptchaDelayEscalator()
    return _captcha_delay_escalator

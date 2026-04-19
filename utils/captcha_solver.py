"""
CAPTCHA Solver Service Integration
Supports 2Captcha and Anti-Captcha services for solving CAPTCHAs
"""
from __future__ import annotations
import logging
import httpx
import base64
from typing import Optional, Dict, Any
from datetime import datetime, timezone
from dataclasses import dataclass, field
from enum import Enum

from config import settings

logger = logging.getLogger(__name__)


class CaptchaService(Enum):
    """Available CAPTCHA solving services"""
    TWO_CAPTCHA = "2captcha"
    ANTI_CAPTCHA = "anticaptcha"


class CaptchaType(Enum):
    """Types of CAPTCHAs"""
    RECAPTCHA_V2 = "recaptcha_v2"
    RECAPTCHA_V3 = "recaptcha_v3"
    HCAPTCHA = "hcaptcha"
    IMAGE_TO_TEXT = "image_to_text"
    CUSTOM = "custom"


@dataclass
class CaptchaTask:
    """A CAPTCHA solving task"""
    id: str
    captcha_type: CaptchaType
    site_key: Optional[str] = None
    page_url: Optional[str] = None
    image_data: Optional[str] = None  # Base64 encoded
    created_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    solved_at: Optional[datetime] = None
    solution: Optional[str] = None
    status: str = "pending"  # pending, processing, solved, failed
    cost: float = 0.0


class CaptchaSolver:
    """CAPTCHA solver using external services"""
    
    def __init__(self, service: CaptchaService = CaptchaService.TWO_CAPTCHA):
        self.service = service
        self.api_key = self._get_api_key()
        self.solved_count = 0
        self.failed_count = 0
        self.total_cost = 0.0
        
        # Service-specific endpoints
        if service == CaptchaService.TWO_CAPTCHA:
            self.base_url = "http://2captcha.com"
            self.create_task_url = f"{self.base_url}/in.php"
            self.get_result_url = f"{self.base_url}/res.php"
        elif service == CaptchaService.ANTI_CAPTCHA:
            self.base_url = "https://api.anti-captcha.com"
            self.create_task_url = f"{self.base_url}/createTask"
            self.get_result_url = f"{self.base_url}/getTaskResult"
        
        if not self.api_key:
            logger.warning(f"{service.value} API key not configured, CAPTCHA solving disabled")
    
    def _get_api_key(self) -> Optional[str]:
        """Get API key for the selected service"""
        if self.service == CaptchaService.TWO_CAPTCHA:
            return getattr(settings, 'twocaptcha_api_key', None)
        elif self.service == CaptchaService.ANTI_CAPTCHA:
            return getattr(settings, 'anticaptcha_api_key', None)
        return None
    
    def is_available(self) -> bool:
        """Check if CAPTCHA solver is available"""
        return self.api_key is not None
    
    async def solve_recaptcha_v2(
        self,
        site_key: str,
        page_url: str,
        timeout: int = 120
    ) -> Optional[str]:
        """
        Solve reCAPTCHA v2
        
        Args:
            site_key: The site key for reCAPTCHA
            page_url: The URL of the page with CAPTCHA
            timeout: Maximum time to wait for solution (seconds)
            
        Returns:
            Solution token or None if failed
        """
        if not self.is_available():
            logger.warning("CAPTCHA solver not available")
            return None
        
        logger.info(f"Attempting to solve reCAPTCHA v2 for {page_url}")
        
        try:
            # Create task
            task_id = await self._create_recaptcha_task(site_key, page_url)
            if not task_id:
                logger.error("Failed to create CAPTCHA task")
                return None
            
            # Wait for solution
            solution = await self._wait_for_solution(task_id, timeout)
            
            if solution:
                self.solved_count += 1
                logger.info(f"CAPTCHA solved successfully (task: {task_id})")
                return solution
            else:
                self.failed_count += 1
                logger.warning(f"CAPTCHA solve failed (task: {task_id})")
                return None
                
        except Exception as e:
            logger.error(f"Error solving CAPTCHA: {e}")
            self.failed_count += 1
            return None
    
    async def _create_recaptcha_task(self, site_key: str, page_url: str) -> Optional[str]:
        """Create a reCAPTCHA solving task"""
        if self.service == CaptchaService.TWO_CAPTCHA:
            return await self._create_2captcha_recaptcha_task(site_key, page_url)
        elif self.service == CaptchaService.ANTI_CAPTCHA:
            return await self._create_anticaptcha_recaptcha_task(site_key, page_url)
        return None
    
    async def _create_2captcha_recaptcha_task(self, site_key: str, page_url: str) -> Optional[str]:
        """Create task with 2Captcha"""
        params = {
            'key': self.api_key,
            'method': 'userrecaptcha',
            'googlekey': site_key,
            'pageurl': page_url,
            'json': 1
        }
        
        async with httpx.AsyncClient() as client:
            response = await client.get(self.create_task_url, params=params)
            response.raise_for_status()
            data = response.json()
            
            if data.get('status') == 1:
                return str(data.get('request'))
            else:
                logger.error(f"2Captcha error: {data.get('request')}")
                return None
    
    async def _create_anticaptcha_recaptcha_task(self, site_key: str, page_url: str) -> Optional[str]:
        """Create task with Anti-Captcha"""
        payload = {
            "clientKey": self.api_key,
            "task": {
                "type": "RecaptchaV2TaskProxyless",
                "websiteURL": page_url,
                "websiteKey": site_key
            }
        }
        
        async with httpx.AsyncClient() as client:
            response = await client.post(self.create_task_url, json=payload)
            response.raise_for_status()
            data = response.json()
            
            if data.get('errorId') == 0:
                return str(data.get('taskId'))
            else:
                logger.error(f"Anti-Captcha error: {data.get('errorDescription')}")
                return None
    
    async def _wait_for_solution(self, task_id: str, timeout: int) -> Optional[str]:
        """Wait for CAPTCHA solution"""
        import asyncio
        
        start_time = datetime.now(timezone.utc)
        
        while (datetime.now(timezone.utc) - start_time).total_seconds() < timeout:
            await asyncio.sleep(3)  # Check every 3 seconds
            
            if self.service == CaptchaService.TWO_CAPTCHA:
                solution = await self._get_2captcha_result(task_id)
            elif self.service == CaptchaService.ANTI_CAPTCHA:
                solution = await self._get_anticaptcha_result(task_id)
            else:
                return None
            
            if solution:
                return solution
        
        logger.warning(f"CAPTCHA solve timeout after {timeout}s")
        return None
    
    async def _get_2captcha_result(self, task_id: str) -> Optional[str]:
        """Get result from 2Captcha"""
        params = {
            'key': self.api_key,
            'action': 'get',
            'id': task_id,
            'json': 1
        }
        
        async with httpx.AsyncClient() as client:
            response = await client.get(self.get_result_url, params=params)
            response.raise_for_status()
            data = response.json()
            
            if data.get('status') == 1:
                return data.get('request')
            elif data.get('request') == 'CAPCHA_NOT_READY':
                return None
            else:
                logger.error(f"2Captcha result error: {data.get('request')}")
                return None
    
    async def _get_anticaptcha_result(self, task_id: str) -> Optional[str]:
        """Get result from Anti-Captcha"""
        payload = {
            "clientKey": self.api_key,
            "taskId": int(task_id)
        }
        
        async with httpx.AsyncClient() as client:
            response = await client.post(self.get_result_url, json=payload)
            response.raise_for_status()
            data = response.json()
            
            if data.get('status') == 'ready':
                return data.get('solution', {}).get('gRecaptchaResponse')
            elif data.get('status') == 'processing':
                return None
            else:
                logger.error(f"Anti-Captcha result error: {data.get('errorDescription')}")
                return None
    
    def get_stats(self) -> Dict[str, Any]:
        """Get solver statistics"""
        return {
            'service': self.service.value,
            'available': self.is_available(),
            'solved_count': self.solved_count,
            'failed_count': self.failed_count,
            'success_rate': (self.solved_count / (self.solved_count + self.failed_count) * 100) if (self.solved_count + self.failed_count) > 0 else 0,
            'total_cost': self.total_cost
        }


class CaptchaDetector:
    """Detects CAPTCHAs in HTML content"""
    
    CAPTCHA_INDICATORS = [
        'recaptcha',
        'hcaptcha',
        'captcha',
        'challenge-platform',
        'cf-challenge',
        'turnstile'
    ]
    
    @classmethod
    def detect_captcha(cls, html: str) -> Optional[Dict[str, Any]]:
        """
        Detect if CAPTCHA is present in HTML
        
        Args:
            html: HTML content to check
            
        Returns:
            Dictionary with CAPTCHA info or None if not detected
        """
        html_lower = html.lower()
        
        for indicator in cls.CAPTCHA_INDICATORS:
            if indicator in html_lower:
                captcha_type = cls._classify_captcha(indicator, html_lower)
                logger.warning(f"CAPTCHA detected: {captcha_type}")
                
                return {
                    'detected': True,
                    'type': captcha_type,
                    'indicator': indicator,
                    'timestamp': datetime.now(timezone.utc).isoformat()
                }
        
        return None
    
    @classmethod
    def _classify_captcha(cls, indicator: str, html: str) -> str:
        """Classify the type of CAPTCHA"""
        if 'recaptcha' in html:
            if 'v3' in html:
                return 'recaptcha_v3'
            return 'recaptcha_v2'
        elif 'hcaptcha' in html:
            return 'hcaptcha'
        elif 'cf-challenge' in html or 'turnstile' in html:
            return 'cloudflare_turnstile'
        else:
            return 'custom'
    
    @classmethod
    def extract_site_key(cls, html: str, captcha_type: str) -> Optional[str]:
        """
        Extract site key from HTML
        
        Args:
            html: HTML content
            captcha_type: Type of CAPTCHA
            
        Returns:
            Site key or None
        """
        import re
        
        if captcha_type in ['recaptcha_v2', 'recaptcha_v3']:
            # Look for data-sitekey attribute
            pattern = r'data-sitekey=["\']([^"\']+)["\']'
            match = re.search(pattern, html)
            if match:
                return match.group(1)
        
        elif captcha_type == 'hcaptcha':
            # Look for data-sitekey attribute for hCaptcha
            pattern = r'data-sitekey=["\']([^"\']+)["\']'
            match = re.search(pattern, html)
            if match:
                return match.group(1)
        
        return None


# Global CAPTCHA solver instance
_captcha_solver: Optional[CaptchaSolver] = None


def get_captcha_solver() -> Optional[CaptchaSolver]:
    """Get the global CAPTCHA solver instance"""
    global _captcha_solver
    
    if _captcha_solver is None:
        # Try 2Captcha first, then Anti-Captcha
        solver = CaptchaSolver(CaptchaService.TWO_CAPTCHA)
        if solver.is_available():
            _captcha_solver = solver
        else:
            solver = CaptchaSolver(CaptchaService.ANTI_CAPTCHA)
            if solver.is_available():
                _captcha_solver = solver
    
    return _captcha_solver

"""
Managed Client for Enhanced Scraping with Anti-Blocking Measures
Provides proxy rotation, captcha solving, and commercial API integration
"""
from __future__ import annotations
import logging
import asyncio
import random
import time
from typing import Optional, Dict, Any, List
from datetime import datetime, timezone

from seleniumbase import SB
from config import settings
from utils.proxy_manager import get_proxy_pool, ProxyRotationStrategy
from utils.captcha_solver import get_captcha_solver, CaptchaDetector
from utils.production_safeguards import with_circuit_breaker
from utils.error_classifier import ErrorClassifier

logger = logging.getLogger(__name__)


class ManagedClient:
    """Enhanced web client with anti-blocking capabilities"""
    
    def __init__(self):
        self.proxy_pool = get_proxy_pool()
        self.captcha_solver = get_captcha_solver()
        self.session_stats = {
            'requests_count': 0,
            'success_count': 0,
            'blocked_count': 0,
            'captcha_detected': 0
        }
        
    async def get_html(self, url: str, source: str = "generic") -> Optional[str]:
        """
        Get HTML content with anti-blocking measures
        
        Args:
            url: URL to fetch
            source: Source identifier for logging
            
        Returns:
            HTML content or None if failed
        """
        self.session_stats['requests_count'] += 1
        
        # Try proxy rotation first if available
        proxy = None
        if settings.use_proxy and not self.proxy_pool.is_empty():
            proxy = self.proxy_pool.get_proxy()
            logger.info(f"[PROXY] Using proxy: {proxy.proxy_url if proxy else 'None'}")
        
        try:
            # Use SeleniumBase UC mode for advanced Cloudflare bypass
            max_retries = 3
            for attempt in range(max_retries):
                try:
                    logger.info(f"[FETCH] Attempt {attempt + 1}/{max_retries} for {source}: {url}")
                    
                    # Add random delay to avoid rate limiting
                    if attempt > 0:
                        delay = settings.request_delay_seconds + random.uniform(0, settings.request_delay_jitter)
                        logger.info(f"[DELAY] Waiting {delay:.1f}s before retry")
                        time.sleep(delay)
                    
                    # Use SeleniumBase with UC (Undetected Chrome) mode
                    with SB(uc=True, 
                           headless=settings.playwright_headless,
                           proxy=proxy.proxy_url if proxy else None) as sb:
                        
                        # Set realistic browser configuration
                        sb.driver.set_window_size(1920, 1080)
                        sb.driver.set_page_load_timeout(settings.playwright_timeout)
                        
                        # Navigate with UC mode which handles Cloudflare automatically
                        sb.uc_open_with_reconnect(url, reconnect_time=4)
                        
                        # Wait for Cloudflare challenge resolution
                        time.sleep(random.uniform(3, 6))
                        
                        # Check if still on Cloudflare challenge page
                        if "cloudflare" in sb.get_page_source().lower() or "ray id" in sb.get_page_source().lower():
                            logger.info(f"[CLOUDFLARE] Challenge detected, attempting auto-solve...")
                            time.sleep(random.uniform(8, 12))
                            
                            # Try to click CAPTCHA if present
                            try:
                                sb.uc_gui_click_captcha()
                                logger.info(f"[CAPTCHA] Auto-clicked Cloudflare checkbox")
                                time.sleep(random.uniform(5, 8))
                            except Exception as captcha_error:
                                logger.warning(f"[CAPTCHA] Auto-click failed: {captcha_error}")
                        
                        # Additional wait for dynamic content
                        time.sleep(random.uniform(2, 4))
                        html = sb.get_page_source()
                        
                        # Check for blocking
                        if ErrorClassifier.detect_blocking_in_html(html):
                            self.session_stats['blocked_count'] += 1
                            logger.warning(f"[BLOCK] Blocking detected for {source} on attempt {attempt + 1}")
                            
                            # Check for CAPTCHA
                            captcha_info = CaptchaDetector.detect_captcha(html)
                            if captcha_info:
                                self.session_stats['captcha_detected'] += 1
                                logger.warning(f"[CAPTCHA] CAPTCHA detected: {captcha_info['type']}")
                                
                                # Try to solve CAPTCHA if solver is available
                                if self.captcha_solver and settings.captcha_solver_enabled:
                                    site_key = CaptchaDetector.extract_site_key(html, captcha_info['type'])
                                    if site_key:
                                        logger.info(f"[CAPTCHA] Attempting to solve {captcha_info['type']}")
                                        solution = await self.captcha_solver.solve_recaptcha_v2(
                                            site_key, url, timeout=60
                                        )
                                        if solution:
                                            logger.info(f"[CAPTCHA] Solved successfully, retrying...")
                                            continue
                        
                            if attempt == max_retries - 1:
                                # Last attempt failed, record proxy failure if used
                                if proxy:
                                    self.proxy_pool.record_proxy_result(proxy, False)
                                return None
                            continue
                        
                        # Success!
                        self.session_stats['success_count'] += 1
                        if proxy:
                            self.proxy_pool.record_proxy_result(proxy, True, latency_ms=1000)
                        
                        logger.info(f"[SUCCESS] Retrieved {len(html)} characters from {source}")
                        return html
                
                except Exception as e:
                    logger.error(f"[ERROR] Attempt {attempt + 1} failed for {source}: {e}")
                    if attempt == max_retries - 1:
                        if proxy:
                            self.proxy_pool.record_proxy_result(proxy, False)
                        return None
                    continue
                
        except Exception as e:
            logger.error(f"[CRITICAL] Managed client failed for {source}: {e}")
            if proxy:
                self.proxy_pool.record_proxy_result(proxy, False)
            return None
    
    async def scrape_with_zenrows(self, url: str) -> Optional[str]:
        """Scrape using ZenRows commercial API"""
        if not settings.zenrows_api_key:
            return None
            
        try:
            import httpx
            
            params = {
                'api_key': settings.zenrows_api_key,
                'url': url,
                'js_render': 'true',
                'custom_headers': 'true',
                'premium_proxy': 'true'
            }
            
            async with httpx.AsyncClient(timeout=60) as client:
                response = await client.get('https://api.zenrows.com/v1/', params=params)
                response.raise_for_status()
                return response.text
                
        except Exception as e:
            logger.error(f"[ZENROWS] API request failed: {e}")
            return None
    
    async def scrape_with_scraperapi(self, url: str, params: Optional[Dict[str, Any]] = None) -> Optional[str]:
        """Scrape using ScraperAPI commercial API"""
        if not settings.scraperapi_key:
            return None
            
        try:
            import httpx
            
            api_params = {
                'api_key': settings.scraperapi_key,
                'url': url
            }
            if params:
                api_params.update(params)
            
            async with httpx.AsyncClient(timeout=60) as client:
                response = await client.get('http://api.scraperapi.com', params=api_params)
                response.raise_for_status()
                return response.text
                
        except Exception as e:
            logger.error(f"[SCRAPERAPI] API request failed: {e}")
            return None
    
    def get_stats(self) -> Dict[str, Any]:
        """Get session statistics"""
        stats = self.session_stats.copy()
        stats['success_rate'] = (
            (stats['success_count'] / stats['requests_count'] * 100)
            if stats['requests_count'] > 0 else 0
        )
        stats['blocking_rate'] = (
            (stats['blocked_count'] / stats['requests_count'] * 100)
            if stats['requests_count'] > 0 else 0
        )
        
        # Add proxy stats
        if not self.proxy_pool.is_empty():
            stats['proxy_stats'] = self.proxy_pool.get_stats()
        
        # Add CAPTCHA solver stats
        if self.captcha_solver:
            stats['captcha_stats'] = self.captcha_solver.get_stats()
        
        return stats


# Global managed client instance
_managed_client: Optional[ManagedClient] = None


def get_managed_client() -> Optional[ManagedClient]:
    """Get the global managed client instance"""
    global _managed_client
    
    if _managed_client is None:
        _managed_client = ManagedClient()
        logger.info("Managed client initialized with anti-blocking capabilities")
    
    return _managed_client


def initialize_managed_client() -> ManagedClient:
    """Initialize the managed client"""
    global _managed_client
    _managed_client = ManagedClient()
    return _managed_client

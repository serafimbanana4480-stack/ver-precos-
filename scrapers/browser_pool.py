"""
Browser Pool for AutoDeal IA Hunter
Provides singleton browser/context reuse to eliminate 15-30s overhead per scrape.
"""
from __future__ import annotations
import logging
import asyncio
from typing import Optional, Dict, Any
from dataclasses import dataclass

logger = logging.getLogger(__name__)


@dataclass
class BrowserPoolConfig:
    """Configuration for the browser pool."""
    headless: bool = True
    timeout: int = 30000
    max_contexts: int = 5
    user_agent: Optional[str] = None


class BrowserPool:
    """
    Singleton browser pool that reuses Playwright browser instances.
    
    Each scraper gets its own persistent BrowserContext to maintain
    cookies/session state, eliminating the 15-30s launch overhead.
    """
    
    _instance: Optional["BrowserPool"] = None
    _lock = asyncio.Lock()
    
    def __new__(cls, config: Optional[BrowserPoolConfig] = None) -> "BrowserPool":
        if cls._instance is None:
            cls._instance = super().__new__(cls)
            cls._instance._initialized = False
            cls._instance._pending_config = config
        return cls._instance
    
    def __init__(self, config: Optional[BrowserPoolConfig] = None):
        if self._initialized:
            return
        # Use pending config from __new__ if available, otherwise passed config
        effective_config = getattr(self, '_pending_config', None) or config
        self.config = effective_config or BrowserPoolConfig()
        self._playwright = None
        self._browser = None
        self._contexts: Dict[str, Any] = {}
        self._initialized = True
    
    async def _ensure_browser(self):
        """Lazy-initialize the shared browser instance."""
        if self._browser is not None:
            return
        
        try:
            from playwright.async_api import async_playwright
        except ImportError:
            logger.error("Playwright not installed. Run: pip install playwright")
            raise
        
        self._playwright = await async_playwright().start()
        
        launch_args = {
            "headless": self.config.headless,
            "args": [
                '--disable-blink-features=AutomationControlled',
                '--disable-web-security',
                '--disable-features=IsolateOrigins,site-per-process',
                '--disable-dev-shm-usage',
                '--no-sandbox',
            ]
        }
        
        try:
            self._browser = await self._playwright.chromium.launch(**launch_args)
            logger.info("[BROWSER_POOL] Browser launched successfully")
        except Exception as e:
            logger.error(f"[BROWSER_POOL] Failed to launch browser: {e}")
            raise
    
    async def get_context(self, name: str, extra_http_headers: Optional[Dict[str, str]] = None) -> Any:
        """
        Get or create a named browser context.
        
        Args:
            name: Unique name for this context (e.g., 'olx', 'standvirtual')
            extra_http_headers: Additional HTTP headers for this context
            
        Returns:
            Playwright BrowserContext
        """
        async with self._lock:
            await self._ensure_browser()
            
            if name in self._contexts:
                ctx = self._contexts[name]
                # Check if context is still usable
                try:
                    # Simple health check
                    _ = await ctx.pages
                    logger.debug(f"[BROWSER_POOL] Reusing context '{name}'")
                    return ctx
                except Exception:
                    logger.warning(f"[BROWSER_POOL] Context '{name}' stale, recreating")
                    del self._contexts[name]
            
            # Create new context
            context_options: Dict[str, Any] = {
                "viewport": {"width": 1920, "height": 1080},
                "locale": "pt-PT",
                "timezone_id": "Europe/Lisbon",
                "permissions": ["geolocation"],
            }
            
            if self.config.user_agent:
                context_options["user_agent"] = self.config.user_agent
            
            if extra_http_headers:
                context_options["extra_http_headers"] = extra_http_headers
            
            ctx = await self._browser.new_context(**context_options)
            
            # Apply stealth
            try:
                from utils.playwright_stealth import apply_stealth_async
                page = await ctx.new_page()
                await apply_stealth_async(page)
                await page.close()
            except Exception as e:
                logger.warning(f"[BROWSER_POOL] Stealth apply failed: {e}")
            
            self._contexts[name] = ctx
            logger.info(f"[BROWSER_POOL] Created new context '{name}'")
            return ctx
    
    async def new_page(self, context_name: str, extra_http_headers: Optional[Dict[str, str]] = None) -> Any:
        """Get a new page from a named context."""
        ctx = await self.get_context(context_name, extra_http_headers)
        page = await ctx.new_page()
        page.set_default_timeout(self.config.timeout)
        page.set_default_navigation_timeout(self.config.timeout)
        return page
    
    async def close_context(self, name: str):
        """Close a specific context."""
        async with self._lock:
            if name in self._contexts:
                try:
                    await self._contexts[name].close()
                except Exception as e:
                    logger.warning(f"[BROWSER_POOL] Error closing context '{name}': {e}")
                del self._contexts[name]
                logger.info(f"[BROWSER_POOL] Closed context '{name}'")
    
    async def close_all(self):
        """Close all contexts and the browser."""
        async with self._lock:
            for name, ctx in list(self._contexts.items()):
                try:
                    await ctx.close()
                except Exception:
                    pass
            self._contexts.clear()
            
            if self._browser:
                try:
                    await self._browser.close()
                except Exception:
                    pass
                self._browser = None
            
            if self._playwright:
                try:
                    await self._playwright.stop()
                except Exception:
                    pass
                self._playwright = None
            
            logger.info("[BROWSER_POOL] All contexts and browser closed")
    
    def get_stats(self) -> Dict[str, Any]:
        """Get pool statistics."""
        return {
            "browser_ready": self._browser is not None,
            "active_contexts": list(self._contexts.keys()),
            "context_count": len(self._contexts),
            "max_contexts": self.config.max_contexts,
        }


# Convenience function
def get_browser_pool(config: Optional[BrowserPoolConfig] = None) -> BrowserPool:
    """Get the singleton browser pool instance."""
    return BrowserPool(config)


# Backward compatibility alias
BrowserPoolSingleton = BrowserPool

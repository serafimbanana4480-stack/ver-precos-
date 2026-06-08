"""
Fallback Selector Manager for Web Scraping
Handles multiple CSS selectors with automatic fallback and performance tracking
"""
from __future__ import annotations
import logging
import hashlib
import re
from typing import Optional, List, Dict, Any, Tuple
from datetime import datetime, timezone
from dataclasses import dataclass, field
from enum import Enum
from utils.parsers import parse_price, parse_km, extract_year_km_from_string

logger = logging.getLogger(__name__)


class SelectorStatus(Enum):
    """Status of a selector"""
    ACTIVE = "active"
    DEGRADED = "degraded"
    FAILED = "failed"
    TESTING = "testing"


@dataclass
class SelectorConfig:
    """Configuration for a single selector"""
    selector: str
    priority: int  # Lower number = higher priority
    source: str  # 'olx', 'standvirtual', 'autosapo'
    field: str  # 'title', 'price', 'url', etc.
    extraction_type: str = 'text'  # 'text', 'attribute', 'href'
    attribute_name: Optional[str] = None  # For attribute extraction
    status: SelectorStatus = SelectorStatus.ACTIVE
    success_count: int = 0
    failure_count: int = 0
    last_used: Optional[datetime] = None
    last_success: Optional[datetime] = None
    last_failure: Optional[datetime] = None
    
    @property
    def success_rate(self) -> float:
        """Calculate success rate"""
        total = self.success_count + self.failure_count
        if total == 0:
            return 1.0
        return self.success_count / total
    
    def record_success(self) -> None:
        """Record a successful extraction"""
        self.success_count += 1
        self.last_success = datetime.now(timezone.utc)
        self.last_used = datetime.now(timezone.utc)
        if self.status == SelectorStatus.FAILED:
            self.status = SelectorStatus.TESTING
    
    def record_failure(self) -> None:
        """Record a failed extraction"""
        self.failure_count += 1
        self.last_failure = datetime.now(timezone.utc)
        self.last_used = datetime.now(timezone.utc)
        if self.failure_count > 3 and self.success_rate < 0.3:
            self.status = SelectorStatus.FAILED
        elif self.success_rate < 0.5:
            self.status = SelectorStatus.DEGRADED


def _send_discord_notification(message: str) -> None:
    """Send a notification to Discord webhook if configured. Fails silently."""
    from config import settings
    if not settings.discord_webhook:
        return
    try:
        import httpx
        httpx.post(
            settings.discord_webhook,
            json={"content": message},
            timeout=5.0
        )
    except Exception as exc:
        logger.debug(f"Discord notification failed (non-critical): {exc}")


class SelectorManager:
    """Manages fallback selectors with automatic testing and performance tracking"""
    
    def __init__(self):
        self.selectors: Dict[str, List[SelectorConfig]] = {}  # key: f"{source}_{field}"
        self.html_cache: Dict[str, str] = {}  # Cache HTML samples for testing
        self.alert_threshold = 3  # Number of consecutive failures before alert
    
    def add_selector(
        self,
        source: str,
        field: str,
        selector: str,
        priority: int = 1,
        extraction_type: str = 'text',
        attribute_name: Optional[str] = None
    ) -> None:
        """Add a selector configuration"""
        key = f"{source}_{field}"
        if key not in self.selectors:
            self.selectors[key] = []
        
        selector_config = SelectorConfig(
            selector=selector,
            priority=priority,
            source=source,
            field=field,
            extraction_type=extraction_type,
            attribute_name=attribute_name
        )
        
        self.selectors[key].append(selector_config)
        # Sort by priority
        self.selectors[key].sort(key=lambda x: x.priority)
        
        logger.info(f"Added selector for {key}: {selector} (priority {priority})")
    
    def get_selectors(self, source: str, field: str) -> List[SelectorConfig]:
        """Get all selectors for a source and field, sorted by priority"""
        key = f"{source}_{field}"
        return self.selectors.get(key, [])

    def get_selector(self, source: str, field: str = "title") -> Optional[str]:
        """Return highest-priority selector string (legacy/test API)."""
        selectors = self.get_selectors(source, field)
        if selectors:
            return selectors[0].selector
        defaults = {
            "olx": "a[data-cy='listing-ad-title']",
            "standvirtual": "article.offer-item",
            "autosapo": ".list-item",
        }
        return defaults.get(source)
    
    def extract_with_fallback(
        self,
        element: Any,
        source: str,
        field: str,
        default: Any = None
    ) -> Tuple[Any, Optional[str]]:
        """
        Extract data using selectors with automatic fallback
        
        Args:
            element: BeautifulSoup element or similar
            source: Source name ('olx', 'standvirtual', 'autosapo')
            field: Field name ('title', 'price', 'url', etc.)
            default: Default value if all selectors fail
            
        Returns:
            Tuple of (extracted_value, selector_used)
        """
        selectors = self.get_selectors(source, field)
        
        if not selectors:
            logger.warning(f"No selectors configured for {source}_{field}")
            return default, None
        
        last_error = None
        
        for selector_config in selectors:
            # Skip failed selectors
            if selector_config.status == SelectorStatus.FAILED:
                continue
            
            try:
                value = self._extract_with_selector(element, selector_config)
                
                # Clean data based on field name
                if value is not None and value != '':
                    if field == 'price':
                        value = parse_price(value)
                    elif field == 'km':
                        value = parse_km(value)
                    elif field == 'year':
                        if len(str(value)) > 4:
                            year, _ = extract_year_km_from_string(str(value))
                            value = year
                        else:
                            try:
                                value = int(re.sub(r'\D', '', str(value)))
                            except:
                                value = None
                
                if value is not None and value != '':
                    selector_config.record_success()
                    logger.debug(
                        f"Extracted {field} from {source} using selector: {selector_config.selector}"
                    )
                    return value, selector_config.selector
                else:
                    selector_config.record_failure()
                    logger.debug(
                        f"Selector {selector_config.selector} returned empty for {source}_{field}"
                    )
            except Exception as e:
                selector_config.record_failure()
                last_error = str(e)
                logger.debug(
                    f"Selector {selector_config.selector} failed for {source}_{field}: {e}"
                )
        
        # All selectors failed
        logger.warning(
            f"All selectors failed for {source}_{field}. Last error: {last_error}"
        )
        
        # Check if we should alert
        active_selectors = [s for s in selectors if s.status == SelectorStatus.ACTIVE]
        if len(active_selectors) == 0:
            self._send_alert(source, field, selectors)
        
        return default, None
    
    def _extract_with_selector(self, element: Any, config: SelectorConfig) -> Any:
        """Extract data using a specific selector configuration"""
        try:
            from bs4 import BeautifulSoup, Tag
        except ImportError:
            raise ImportError("BeautifulSoup is required for selector extraction")
        
        if not isinstance(element, Tag):
            raise ValueError("Element must be a BeautifulSoup Tag")
        
        found = element.select_one(config.selector)
        
        if not found:
            return None
        
        if config.extraction_type == 'text':
            return found.get_text(strip=True)
        elif config.extraction_type == 'attribute':
            if config.attribute_name:
                return found.get(config.attribute_name)
            return None
        elif config.extraction_type == 'href':
            return found.get('href')
        else:
            return found.get_text(strip=True)
    
    def _send_alert(self, source: str, field: str, selectors: List[SelectorConfig]) -> None:
        """Send alert when all selectors fail"""
        logger.error(
            f"ALERT: All selectors failed for {source}_{field}. "
            f"Total selectors: {len(selectors)}, "
            f"Active: {len([s for s in selectors if s.status == SelectorStatus.ACTIVE])}, "
            f"Degraded: {len([s for s in selectors if s.status == SelectorStatus.DEGRADED])}, "
            f"Failed: {len([s for s in selectors if s.status == SelectorStatus.FAILED])}"
        )
        
        # Notify via Discord/Telegram if configured
        _send_discord_notification(
            f"🚨 **Selector Alert** — Todos os selectors falharam para `{source}_{field}`\n"
            f"Selectors: {len(selectors)} total, "
            f"{len([s for s in selectors if s.status == SelectorStatus.FAILED])} falhados."
        )
    
    def test_selector(
        self,
        html: str,
        source: str,
        field: str,
        selector: str
    ) -> bool:
        """Test a selector against HTML sample"""
        try:
            from bs4 import BeautifulSoup
        except ImportError:
            logger.error("BeautifulSoup is required for selector testing")
            return False
        
        try:
            soup = BeautifulSoup(html, 'lxml')
            results = soup.select(selector)
            success = len(results) > 0
            
            if success:
                logger.info(f"Selector test passed for {source}_{field}: {selector}")
            else:
                logger.warning(f"Selector test failed for {source}_{field}: {selector}")
            
            return success
        except Exception as e:
            logger.error(f"Selector test error: {e}")
            return False
    
    def auto_test_selectors(
        self,
        html: str,
        source: str,
        field: str
    ) -> Dict[str, bool]:
        """Test all selectors for a source and field"""
        selectors = self.get_selectors(source, field)
        results = {}
        
        for selector_config in selectors:
            results[selector_config.selector] = self.test_selector(
                html, source, field, selector_config.selector
            )
        
        return results
    
    def get_selector_stats(self, source: str, field: str) -> Dict[str, Any]:
        """Get statistics for selectors"""
        selectors = self.get_selectors(source, field)
        
        stats = {
            'total_selectors': len(selectors),
            'active': len([s for s in selectors if s.status == SelectorStatus.ACTIVE]),
            'degraded': len([s for s in selectors if s.status == SelectorStatus.DEGRADED]),
            'failed': len([s for s in selectors if s.status == SelectorStatus.FAILED]),
            'selectors': [
                {
                    'selector': s.selector,
                    'priority': s.priority,
                    'status': s.status.value,
                    'success_rate': f"{s.success_rate:.2%}",
                    'success_count': s.success_count,
                    'failure_count': s.failure_count,
                    'last_used': s.last_used.isoformat() if s.last_used else None
                }
                for s in selectors
            ]
        }
        
        return stats
    
    def cache_html_sample(self, source: str, field: str, html: str) -> str:
        """Cache HTML sample for later testing"""
        hash_key = hashlib.md5(html.encode()).hexdigest()
        cache_key = f"{source}_{field}_{hash_key}"
        self.html_cache[cache_key] = html
        return cache_key
    
    def get_cached_html(self, cache_key: str) -> Optional[str]:
        """Get cached HTML sample"""
        return self.html_cache.get(cache_key)


# Global selector manager instance
_selector_manager = SelectorManager()


def get_selector_manager() -> SelectorManager:
    """Get the global selector manager instance"""
    return _selector_manager


def initialize_default_selectors() -> None:
    """Initialize default selectors for all sources and fields"""
    manager = get_selector_manager()
    
    # OLX Selectors
    manager.add_selector('olx', 'title', 'h6[data-cy="listing-title"]', priority=1)
    manager.add_selector('olx', 'title', 'h6.css-1s3qyv', priority=2)
    manager.add_selector('olx', 'title', 'h6', priority=3)
    
    manager.add_selector('olx', 'price', 'span[data-cy="ad-price"]', priority=1)
    manager.add_selector('olx', 'price', 'p.css-okabnv', priority=2)
    manager.add_selector('olx', 'price', 'p.price', priority=3)
    
    manager.add_selector('olx', 'url', 'a[data-cy="listing-ad-url"]', priority=1, extraction_type='href')
    manager.add_selector('olx', 'url', 'a.css-1bbgabe', priority=2, extraction_type='href')
    manager.add_selector('olx', 'url', 'a[href*="/anuncio-"]', priority=3, extraction_type='href')
    
    manager.add_selector('olx', 'location', 'p[data-cy="listing-location"]', priority=1)
    manager.add_selector('olx', 'location', 'p.css-r632y7', priority=2)
    manager.add_selector('olx', 'location', 'p.location', priority=3)
    
    manager.add_selector('olx', 'year', 'dd[data-cy="listing-year"]', priority=1)
    manager.add_selector('olx', 'year', 'dd', priority=2)
    
    manager.add_selector('olx', 'km', 'dd[data-cy="listing-km"]', priority=1)
    manager.add_selector('olx', 'km', 'dd', priority=2)
    
    # Standvirtual Selectors (Updated for 2026 site structure)
    manager.add_selector('standvirtual', 'title', 'h2[class*="ooa-ezpr21"]', priority=1)
    manager.add_selector('standvirtual', 'title', 'h2', priority=2)
    manager.add_selector('standvirtual', 'title', 'a[href*="/anuncio/"]', priority=3)
    
    manager.add_selector('standvirtual', 'price', 'h3[class*="ooa-3ewd90"]', priority=1)
    manager.add_selector('standvirtual', 'price', 'h3', priority=2)
    manager.add_selector('standvirtual', 'price', 'div[class*="eg88ra80"]', priority=3)
    
    manager.add_selector('standvirtual', 'url', 'h2 a', priority=1, extraction_type='href')
    manager.add_selector('standvirtual', 'url', 'a[href*="/anuncio/"]', priority=2, extraction_type='href')
    
    manager.add_selector('standvirtual', 'location', 'p[class*="ooa-nxfgg7"]', priority=1)
    
    manager.add_selector('standvirtual', 'year', 'dd[data-parameter="first_registration_year"]', priority=1)
    manager.add_selector('standvirtual', 'year', 'dd:-soup-contains("20")', priority=2) # Fallback for year-like text
    
    manager.add_selector('standvirtual', 'km', 'dd[data-parameter="mileage"]', priority=1)
    manager.add_selector('standvirtual', 'km', 'dd:-soup-contains("km")', priority=2)
    
    # AutoSapo Selectors (Updated for 2026 site structure - more generic)
    manager.add_selector('autosapo', 'title', 'h2', priority=1)
    manager.add_selector('autosapo', 'title', 'h3', priority=2)
    manager.add_selector('autosapo', 'title', 'a[href*="/anuncio"]', priority=3)
    
    manager.add_selector('autosapo', 'price', 'span[class*="price"]', priority=1)
    manager.add_selector('autosapo', 'price', 'div[class*="price"]', priority=2)
    manager.add_selector('autosapo', 'price', 'span', priority=3)
    
    manager.add_selector('autosapo', 'url', 'a[href*="/anuncio"]', priority=1, extraction_type='href')
    manager.add_selector('autosapo', 'url', 'a', priority=2, extraction_type='href')
    
    manager.add_selector('autosapo', 'location', 'span[class*="location"]', priority=1)
    manager.add_selector('autosapo', 'location', 'div[class*="location"]', priority=2)
    manager.add_selector('autosapo', 'location', 'p', priority=3)
    
    manager.add_selector('autosapo', 'year', 'span[class*="year"]', priority=1)
    manager.add_selector('autosapo', 'year', 'span:-soup-contains("202")', priority=2)
    
    manager.add_selector('autosapo', 'km', 'span[class*="km"]', priority=1)
    manager.add_selector('autosapo', 'km', 'span:-soup-contains("km")', priority=2)
    
    logger.info("Initialized default selectors for all sources and fields")

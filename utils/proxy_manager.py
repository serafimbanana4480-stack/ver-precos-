"""
Proxy Pool Manager for Web Scraping
Manages proxy rotation, health checking, and blacklisting
"""
from __future__ import annotations
import logging
import random
import time
from typing import Optional, List, Dict, Any
from datetime import datetime, timezone, timedelta
from dataclasses import dataclass, field
from enum import Enum
from collections import deque
import threading
import httpx

from config import settings

logger = logging.getLogger(__name__)


class ProxyRotationStrategy(Enum):
    """Proxy rotation strategies"""
    ROUND_ROBIN = "round_robin"
    RANDOM = "random"
    LEAST_USED = "least_used"
    HEALTH_SCORE = "health_score"


class ProxyStatus(Enum):
    """Proxy status"""
    ACTIVE = "active"
    DEGRADED = "degraded"
    BLACKLISTED = "blacklisted"
    TESTING = "testing"


@dataclass
class ProxyConfig:
    """Configuration for a proxy"""
    host: str
    port: int
    username: Optional[str] = None
    password: Optional[str] = None
    protocol: str = "http"  # http, https, socks5
    country: Optional[str] = None  # ISO country code
    status: ProxyStatus = ProxyStatus.ACTIVE
    success_count: int = 0
    failure_count: int = 0
    last_used: Optional[datetime] = None
    last_health_check: Optional[datetime] = None
    health_score: float = 100.0  # 0-100
    latency_ms: float = 0.0
    blacklist_until: Optional[datetime] = None
    request_count: int = 0
    
    @property
    def is_available(self) -> bool:
        """Check if proxy is available for use"""
        if self.status == ProxyStatus.BLACKLISTED:
            if self.blacklist_until and datetime.now(timezone.utc) < self.blacklist_until:
                return False
            # Blacklist period expired, reset status
            self.status = ProxyStatus.ACTIVE
            self.blacklist_until = None
            logger.info(f"Proxy {self.host}:{self.port} removed from blacklist")
        
        return self.status in [ProxyStatus.ACTIVE, ProxyStatus.DEGRADED]
    
    @property
    def success_rate(self) -> float:
        """Calculate success rate"""
        total = self.success_count + self.failure_count
        if total == 0:
            return 100.0
        return (self.success_count / total) * 100
    
    @property
    def proxy_url(self) -> str:
        """Get proxy URL for HTTP requests"""
        if self.username and self.password:
            return f"{self.protocol}://{self.username}:{self.password}@{self.host}:{self.port}"
        return f"{self.protocol}://{self.host}:{self.port}"
    
    def record_success(self, latency_ms: float = 0.0) -> None:
        """Record a successful request"""
        self.success_count += 1
        self.request_count += 1
        self.last_used = datetime.now(timezone.utc)
        if latency_ms > 0:
            self.latency_ms = latency_ms
        self._update_health_score()
    
    def record_failure(self) -> None:
        """Record a failed request"""
        self.failure_count += 1
        self.request_count += 1
        self.last_used = datetime.now(timezone.utc)
        self._update_health_score()
        
        # Auto-blacklist if failure rate is too high
        if self.success_rate < 50 and self.request_count >= 10:
            self.blacklist()
    
    def blacklist(self, duration_hours: int = 24) -> None:
        """Blacklist this proxy"""
        self.status = ProxyStatus.BLACKLISTED
        self.blacklist_until = datetime.now(timezone.utc) + timedelta(hours=duration_hours)
        logger.warning(f"Proxy {self.host}:{self.port} blacklisted for {duration_hours} hours")
    
    def _update_health_score(self) -> None:
        """Update health score based on performance"""
        # Success rate weight: 60%
        success_weight = 0.6 * self.success_rate
        
        # Latency weight: 40% (lower is better, normalize to 0-100)
        latency_score = max(0, 100 - (self.latency_ms / 10))  # 1000ms = 0 score
        latency_weight = 0.4 * latency_score
        
        self.health_score = success_weight + latency_weight
        
        # Update status based on health score
        if self.health_score < 50:
            self.status = ProxyStatus.DEGRADED
        elif self.health_score >= 70:
            self.status = ProxyStatus.ACTIVE


class ProxyPool:
    """Manages a pool of proxies with rotation and health checking"""
    
    def __init__(self, rotation_strategy: ProxyRotationStrategy = ProxyRotationStrategy.HEALTH_SCORE):
        self.rotation_strategy = rotation_strategy
        self.proxies: List[ProxyConfig] = []
        self.lock = threading.Lock()
        self.current_index = 0  # For round-robin
        
        # Health check settings
        self.health_check_interval = timedelta(minutes=5)
        self.last_health_check: Optional[datetime] = None
        
        # Load proxies from environment or configuration
        self._load_proxies()
    
    def _load_proxies(self) -> None:
        """Load proxies from configuration"""
        # Load from comma-separated list in environment
        proxy_list = getattr(settings, 'proxy_list', '')
        if proxy_list:
            for proxy_str in proxy_list.split(','):
                proxy_str = proxy_str.strip()
                if proxy_str:
                    self.add_proxy_from_string(proxy_str)
        
        # Load individual proxy settings
        if hasattr(settings, 'proxy_host') and settings.proxy_host:
            self.add_proxy(
                host=settings.proxy_host,
                port=getattr(settings, 'proxy_port', 8080),
                username=getattr(settings, 'proxy_username', None),
                password=getattr(settings, 'proxy_password', None)
            )
        
        logger.info(f"Loaded {len(self.proxies)} proxies into pool")
    
    def add_proxy_from_string(self, proxy_str: str) -> None:
        """Add proxy from string format (host:port or username:password@host:port)"""
        try:
            # Parse proxy string
            if '@' in proxy_str:
                auth_part, addr_part = proxy_str.split('@', 1)
                username, password = auth_part.split(':', 1)
                host, port = addr_part.split(':', 1)
            else:
                host, port = proxy_str.split(':', 1)
                username = None
                password = None
            
            self.add_proxy(
                host=host,
                port=int(port),
                username=username,
                password=password
            )
        except Exception as e:
            logger.error(f"Failed to parse proxy string '{proxy_str}': {e}")
    
    def add_proxy(
        self,
        host: str,
        port: int,
        username: Optional[str] = None,
        password: Optional[str] = None,
        protocol: str = "http",
        country: Optional[str] = None
    ) -> None:
        """Add a proxy to the pool"""
        proxy = ProxyConfig(
            host=host,
            port=port,
            username=username,
            password=password,
            protocol=protocol,
            country=country
        )
        
        with self.lock:
            self.proxies.append(proxy)
            logger.info(f"Added proxy: {host}:{port}")
    
    def get_proxy(self) -> Optional[ProxyConfig]:
        """Get a proxy based on rotation strategy"""
        with self.lock:
            available_proxies = [p for p in self.proxies if p.is_available]
            
            if not available_proxies:
                logger.debug("No configured proxies; using direct connection")
                return ProxyConfig(host="direct", port=0, protocol="direct")
            
            if self.rotation_strategy == ProxyRotationStrategy.ROUND_ROBIN:
                proxy = self._get_round_robin(available_proxies)
            elif self.rotation_strategy == ProxyRotationStrategy.RANDOM:
                proxy = random.choice(available_proxies)
            elif self.rotation_strategy == ProxyRotationStrategy.LEAST_USED:
                proxy = min(available_proxies, key=lambda p: p.request_count)
            elif self.rotation_strategy == ProxyRotationStrategy.HEALTH_SCORE:
                proxy = max(available_proxies, key=lambda p: p.health_score)
            else:
                proxy = available_proxies[0]
            
            return proxy
    
    def _get_round_robin(self, proxies: List[ProxyConfig]) -> ProxyConfig:
        """Get proxy using round-robin strategy"""
        proxy = proxies[self.current_index % len(proxies)]
        self.current_index += 1
        return proxy
    
    def record_proxy_result(self, proxy: ProxyConfig, success: bool, latency_ms: float = 0.0) -> None:
        """Record the result of a proxy request"""
        with self.lock:
            if success:
                proxy.record_success(latency_ms)
            else:
                proxy.record_failure()
    
    def blacklist_proxy(self, proxy: ProxyConfig, duration_hours: int = 24) -> None:
        """Blacklist a proxy"""
        with self.lock:
            proxy.blacklist(duration_hours)
    
    async def health_check(self) -> Dict[str, Any]:
        """Perform health check on all proxies"""
        results = {}
        
        for proxy in self.proxies:
            if proxy.status == ProxyStatus.BLACKLISTED:
                continue
            
            try:
                start_time = time.time()
                
                # Test proxy with a simple HTTP request
                async with httpx.AsyncClient(timeout=10) as client:
                    response = await client.get(
                        "http://httpbin.org/ip",
                        proxy=proxy.proxy_url
                    )
                    
                    latency_ms = (time.time() - start_time) * 1000
                    
                    if response.status_code == 200:
                        proxy.record_success(latency_ms)
                        proxy.last_health_check = datetime.now(timezone.utc)
                        results[proxy.proxy_url] = {
                            'status': 'healthy',
                            'latency_ms': latency_ms,
                            'health_score': proxy.health_score
                        }
                    else:
                        proxy.record_failure()
                        results[proxy.proxy_url] = {
                            'status': 'unhealthy',
                            'error': f'HTTP {response.status_code}'
                        }
            except Exception as e:
                proxy.record_failure()
                results[proxy.proxy_url] = {
                    'status': 'error',
                    'error': str(e)
                }
        
        self.last_health_check = datetime.now(timezone.utc)
        return results
    
    def get_stats(self) -> Dict[str, Any]:
        """Get pool statistics"""
        with self.lock:
            available = [p for p in self.proxies if p.is_available]
            blacklisted = [p for p in self.proxies if p.status == ProxyStatus.BLACKLISTED]
            
            return {
                'total_proxies': len(self.proxies),
                'available_proxies': len(available),
                'blacklisted_proxies': len(blacklisted),
                'rotation_strategy': self.rotation_strategy.value,
                'last_health_check': self.last_health_check.isoformat() if self.last_health_check else None,
                'proxy_details': [
                    {
                        'host': p.host,
                        'port': p.port,
                        'status': p.status.value,
                        'health_score': p.health_score,
                        'success_rate': p.success_rate,
                        'latency_ms': p.latency_ms,
                        'request_count': p.request_count
                    }
                    for p in self.proxies
                ]
            }
    
    def is_empty(self) -> bool:
        """Check if proxy pool is empty"""
        with self.lock:
            return len(self.proxies) == 0


# Global proxy pool instance
_proxy_pool: Optional[ProxyPool] = None


def get_proxy_pool() -> ProxyPool:
    """Get the global proxy pool instance"""
    global _proxy_pool
    
    if _proxy_pool is None:
        _proxy_pool = ProxyPool()
    
    return _proxy_pool


def initialize_proxy_pool(rotation_strategy: ProxyRotationStrategy = ProxyRotationStrategy.HEALTH_SCORE) -> ProxyPool:
    """Initialize the proxy pool with specified strategy"""
    global _proxy_pool
    _proxy_pool = ProxyPool(rotation_strategy)
    return _proxy_pool


class ProxyManager(ProxyPool):
    """Legacy compatibility alias for ProxyPool."""
    pass

"""
Scraping Orchestrator with Circuit Breakers
Production-grade scraping orchestration with fault tolerance
"""
from __future__ import annotations
import logging
import asyncio
from typing import List, Dict, Any, Optional
from datetime import datetime, timedelta
from enum import Enum
import time

logger = logging.getLogger(__name__)


class CircuitState(Enum):
    """Circuit breaker states"""
    CLOSED = "closed"      # Normal operation
    OPEN = "open"          # Circuit is open, requests blocked
    HALF_OPEN = "half_open"  # Testing if service recovered


class CircuitBreaker:
    """
    Circuit breaker pattern implementation
    
    Opens circuit after N consecutive failures
    Closes circuit after cooldown period
    """
    
    def __init__(
        self,
        failure_threshold: int = 5,
        recovery_timeout: int = 60,
        half_open_max_calls: int = 3
    ):
        self.failure_threshold = failure_threshold
        self.recovery_timeout = recovery_timeout  # seconds
        self.half_open_max_calls = half_open_max_calls
        
        self.state = CircuitState.CLOSED
        self.failure_count = 0
        self.last_failure_time = None
        self.half_open_calls = 0
        self.success_count = 0
    
    def record_success(self):
        """Record a successful call"""
        self.failure_count = 0
        self.success_count += 1
        
        if self.state == CircuitState.HALF_OPEN:
            self.half_open_calls += 1
            if self.half_open_calls >= self.half_open_max_calls:
                self.state = CircuitState.CLOSED
                self.half_open_calls = 0
                logger.info("Circuit breaker: CLOSED - service recovered")
    
    def record_failure(self):
        """Record a failed call"""
        self.failure_count += 1
        self.last_failure_time = datetime.utcnow()
        
        if self.state == CircuitState.HALF_OPEN:
            self.state = CircuitState.OPEN
            self.half_open_calls = 0
            logger.warning("Circuit breaker: OPEN - service failed during half-open")
        
        elif self.failure_count >= self.failure_threshold:
            self.state = CircuitState.OPEN
            logger.warning(f"Circuit breaker: OPEN - {self.failure_count} consecutive failures")
    
    def can_execute(self) -> bool:
        """Check if request can execute"""
        if self.state == CircuitState.CLOSED:
            return True
        
        if self.state == CircuitState.OPEN:
            # Check if recovery timeout has passed
            if self.last_failure_time and \
               (datetime.utcnow() - self.last_failure_time).total_seconds() >= self.recovery_timeout:
                self.state = CircuitState.HALF_OPEN
                self.half_open_calls = 0
                logger.info("Circuit breaker: HALF_OPEN - testing recovery")
                return True
            return False
        
        if self.state == CircuitState.HALF_OPEN:
            return self.half_open_calls < self.half_open_max_calls
        
        return False
    
    def get_state(self) -> Dict[str, Any]:
        """Get circuit breaker state"""
        return {
            "state": self.state.value,
            "failure_count": self.failure_count,
            "success_count": self.success_count,
            "last_failure_time": self.last_failure_time.isoformat() if self.last_failure_time else None
        }


class ScrapingOrchestrator:
    """
    Orchestrates scraping operations with circuit breakers and retry logic
    
    Features:
    - Circuit breakers per source
    - Retry with exponential backoff
    - Rate limiting
    - Source health monitoring
    """
    
    def __init__(self):
        self.circuit_breakers = {
            "olx": CircuitBreaker(failure_threshold=5, recovery_timeout=300),
            "standvirtual": CircuitBreaker(failure_threshold=5, recovery_timeout=300),
            "autosapo": CircuitBreaker(failure_threshold=3, recovery_timeout=180),
            "custojusto": CircuitBreaker(failure_threshold=3, recovery_timeout=180),
            "piscapisca": CircuitBreaker(failure_threshold=3, recovery_timeout=180),
            "carplus": CircuitBreaker(failure_threshold=3, recovery_timeout=180),
        }
        
        self.source_stats = {
            "olx": {"success": 0, "failure": 0, "last_success": None},
            "standvirtual": {"success": 0, "failure": 0, "last_success": None},
            "autosapo": {"success": 0, "failure": 0, "last_success": None},
            "custojusto": {"success": 0, "failure": 0, "last_success": None},
            "piscapisca": {"success": 0, "failure": 0, "last_success": None},
            "carplus": {"success": 0, "failure": 0, "last_success": None},
        }
    
    async def scrape_with_circuit_breaker(
        self,
        source: str,
        scraper_func,
        *args,
        max_retries: int = 3,
        **kwargs
    ) -> Optional[List[Dict[str, Any]]]:
        """
        Execute scraping with circuit breaker and retry logic
        
        Args:
            source: Source name (olx, standvirtual, autosapo, custojusto)
            scraper_func: Async scraper function to call
            max_retries: Maximum retry attempts
            
        Returns:
            List of scraped listings or None if failed
        """
        circuit_breaker = self.circuit_breakers.get(source)
        
        if not circuit_breaker:
            logger.error(f"No circuit breaker for source: {source}")
            return None
        
        if not circuit_breaker.can_execute():
            logger.warning(f"Circuit breaker OPEN for {source}, skipping")
            return None
        
        # Execute with retry logic
        for attempt in range(max_retries):
            try:
                logger.info(f"[{source.upper()}] Attempt {attempt + 1}/{max_retries}")
                
                result = await scraper_func(*args, **kwargs)
                
                if result:
                    circuit_breaker.record_success()
                    self.source_stats[source]["success"] += 1
                    self.source_stats[source]["last_success"] = datetime.utcnow()
                    logger.info(f"[{source.upper()}] Success: {len(result)} listings")
                    return result
                else:
                    logger.warning(f"[{source.upper()}] No results returned")
                    circuit_breaker.record_failure()
                    self.source_stats[source]["failure"] += 1
                    
            except Exception as e:
                logger.error(f"[{source.upper()}] Attempt {attempt + 1} failed: {e}")
                circuit_breaker.record_failure()
                self.source_stats[source]["failure"] += 1
                
                if attempt < max_retries - 1:
                    # Exponential backoff
                    backoff = 2 ** attempt
                    logger.info(f"[{source.upper()}] Retrying in {backoff}s...")
                    await asyncio.sleep(backoff)
        
        logger.error(f"[{source.upper()}] All {max_retries} attempts failed")
        return None
    
    def get_circuit_breaker_states(self) -> Dict[str, Dict[str, Any]]:
        """Get all circuit breaker states"""
        return {
            source: breaker.get_state()
            for source, breaker in self.circuit_breakers.items()
        }
    
    def get_source_stats(self) -> Dict[str, Any]:
        """Get source statistics"""
        return self.source_stats
    
    def reset_circuit_breaker(self, source: str):
        """Manually reset a circuit breaker"""
        if source in self.circuit_breakers:
            self.circuit_breakers[source] = CircuitBreaker(
                failure_threshold=5,
                recovery_timeout=300
            )
            logger.info(f"Circuit breaker reset for {source}")


# Singleton instance
scraping_orchestrator = ScrapingOrchestrator()


# Legacy compatibility alias.
Orchestrator = ScrapingOrchestrator

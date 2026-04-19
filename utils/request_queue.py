"""
Request Queue with Rate Limiting for Scraping Operations
"""
from __future__ import annotations
import logging
import time
import asyncio
from typing import Optional, Dict, Any, Callable, List, Tuple
from datetime import datetime, timezone, timedelta
from dataclasses import dataclass, field
from enum import Enum
from collections import deque, defaultdict
import threading

from config import settings

logger = logging.getLogger(__name__)


class RequestPriority(Enum):
    """Priority levels for requests"""
    CRITICAL = 0  # Highest priority
    HIGH = 1
    NORMAL = 2
    LOW = 3


@dataclass
class QueuedRequest:
    """A queued request with metadata"""
    id: str
    func: Callable
    args: tuple = ()
    kwargs: dict = field(default_factory=dict)
    priority: RequestPriority = RequestPriority.NORMAL
    source: str = "unknown"
    created_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    retries: int = 0
    max_retries: int = 3
    
    @property
    def can_retry(self) -> bool:
        return self.retries < self.max_retries


class RateLimiter:
    """Rate limiter for requests per minute"""
    
    def __init__(self, requests_per_minute: int = 10):
        self.requests_per_minute = requests_per_minute
        self.requests = deque()
        self.lock = threading.Lock()
    
    def can_request(self) -> bool:
        """Check if a request can be made"""
        with self.lock:
            now = datetime.now(timezone.utc)
            # Remove requests older than 1 minute
            while self.requests and (now - self.requests[0]).total_seconds() > 60:
                self.requests.popleft()
            
            return len(self.requests) < self.requests_per_minute
    
    def record_request(self) -> None:
        """Record a request"""
        with self.lock:
            self.requests.append(datetime.now(timezone.utc))
    
    def wait_time(self) -> float:
        """Get time to wait before next request"""
        with self.lock:
            now = datetime.now(timezone.utc)
            # Remove requests older than 1 minute
            while self.requests and (now - self.requests[0]).total_seconds() > 60:
                self.requests.popleft()
            
            if len(self.requests) < self.requests_per_minute:
                return 0.0
            
            # Calculate wait time until oldest request is 60 seconds old
            oldest = self.requests[0]
            wait_time = 60.0 - (now - oldest).total_seconds()
            return max(0.0, wait_time)


class RequestQueue:
    """Thread-safe request queue with priority and rate limiting"""
    
    def __init__(self):
        self.queue: List[QueuedRequest] = []
        self.lock = threading.Lock()
        self.condition = threading.Condition(self.lock)
        self.dead_letter_queue: List[QueuedRequest] = []
        
        # Rate limiters per source
        self.rate_limiters: Dict[str, RateLimiter] = {
            'olx': RateLimiter(requests_per_minute=10),
            'standvirtual': RateLimiter(requests_per_minute=8),
            'autosapo': RateLimiter(requests_per_minute=8)
        }
        
        # Metrics
        self.total_enqueued = 0
        self.total_processed = 0
        self.total_failed = 0
        self.total_retried = 0
        
        self.running = False
        self.worker_thread: Optional[threading.Thread] = None
    
    def enqueue(
        self,
        func: Callable,
        args: tuple = (),
        kwargs: Optional[Dict[str, Any]] = None,
        priority: RequestPriority = RequestPriority.NORMAL,
        source: str = "unknown",
        max_retries: int = 3
    ) -> str:
        """
        Enqueue a request
        
        Args:
            func: Function to execute
            args: Positional arguments
            kwargs: Keyword arguments
            priority: Request priority
            source: Source identifier for rate limiting
            max_retries: Maximum retry attempts
            
        Returns:
            Request ID
        """
        request_id = f"req_{int(time.time() * 1000000)}"
        
        request = QueuedRequest(
            id=request_id,
            func=func,
            args=args,
            kwargs=kwargs or {},
            priority=priority,
            source=source,
            max_retries=max_retries
        )
        
        with self.lock:
            self.queue.append(request)
            # Sort by priority (lower number = higher priority)
            self.queue.sort(key=lambda r: r.priority.value)
            self.total_enqueued += 1
            self.condition.notify()
        
        logger.debug(f"Enqueued request {request_id} with priority {priority.value}")
        return request_id
    
    def dequeue(self) -> Optional[QueuedRequest]:
        """Dequeue the next request"""
        with self.lock:
            if not self.queue:
                return None
            
            return self.queue.pop(0)
    
    def start(self, workers: int = 1) -> None:
        """Start the queue worker thread"""
        if self.running:
            logger.warning("Queue already running")
            return
        
        self.running = True
        self.worker_thread = threading.Thread(target=self._worker, daemon=True)
        self.worker_thread.start()
        logger.info(f"Request queue started with {workers} worker(s)")
    
    def stop(self) -> None:
        """Stop the queue worker thread"""
        self.running = False
        if self.worker_thread:
            self.condition.notify_all()
            self.worker_thread.join(timeout=5)
        logger.info("Request queue stopped")
    
    def _worker(self) -> None:
        """Worker thread to process requests"""
        while self.running:
            request = self.dequeue()
            
            if request is None:
                # Wait for new requests
                with self.condition:
                    self.condition.wait(timeout=1.0)
                continue
            
            # Check rate limiter for source
            rate_limiter = self.rate_limiters.get(request.source)
            if rate_limiter:
                wait_time = rate_limiter.wait_time()
                if wait_time > 0:
                    logger.debug(f"Rate limited for {request.source}, waiting {wait_time:.2f}s")
                    time.sleep(wait_time)
            
            # Execute request
            try:
                logger.debug(f"Processing request {request.id}")
                result = request.func(*request.args, **request.kwargs)
                
                with self.lock:
                    self.total_processed += 1
                
                logger.debug(f"Request {request.id} completed successfully")
                
                # Record request in rate limiter
                if rate_limiter:
                    rate_limiter.record_request()
                
            except Exception as e:
                logger.error(f"Request {request.id} failed: {e}")
                
                with self.lock:
                    self.total_failed += 1
                
                # Retry if possible
                if request.can_retry:
                    request.retries += 1
                    self.total_retried += 1
                    logger.info(f"Retrying request {request.id} (attempt {request.retries}/{request.max_retries})")
                    
                    with self.lock:
                        self.queue.append(request)
                        self.queue.sort(key=lambda r: r.priority.value)
                else:
                    # Move to dead letter queue
                    logger.warning(f"Request {request.id} moved to dead letter queue after {request.max_retries} failures")
                    with self.lock:
                        self.dead_letter_queue.append(request)
    
    def get_stats(self) -> Dict[str, Any]:
        """Get queue statistics"""
        with self.lock:
            return {
                'queue_size': len(self.queue),
                'dead_letter_queue_size': len(self.dead_letter_queue),
                'total_enqueued': self.total_enqueued,
                'total_processed': self.total_processed,
                'total_failed': self.total_failed,
                'total_retried': self.total_retried,
                'success_rate': (self.total_processed / self.total_enqueued * 100) if self.total_enqueued > 0 else 0,
                'rate_limiters': {
                    source: {
                        'requests_in_last_minute': len(limiter.requests),
                        'requests_per_minute': limiter.requests_per_minute
                    }
                    for source, limiter in self.rate_limiters.items()
                }
            }
    
    def clear_dead_letter_queue(self) -> List[QueuedRequest]:
        """Clear and return dead letter queue"""
        with self.lock:
            dead_letters = self.dead_letter_queue.copy()
            self.dead_letter_queue.clear()
            return dead_letters


# Global request queue instance
_request_queue = RequestQueue()


def get_request_queue() -> RequestQueue:
    """Get the global request queue instance"""
    return _request_queue


def initialize_queue() -> None:
    """Initialize and start the request queue"""
    queue = get_request_queue()
    if not queue.running:
        queue.start(workers=1)
        logger.info("Request queue initialized")


def shutdown_queue() -> None:
    """Shutdown the request queue"""
    queue = get_request_queue()
    if queue.running:
        queue.stop()

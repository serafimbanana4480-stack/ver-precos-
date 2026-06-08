"""
Rate limiting middleware for API.
"""
import time
from typing import Dict, Any, Optional, List
from fastapi import Request, HTTPException, status
from starlette.middleware.base import BaseHTTPMiddleware
import logging
import json
from collections import defaultdict, deque
from datetime import datetime, timedelta

logger = logging.getLogger(__name__)


class RateLimitMiddleware(BaseHTTPMiddleware):
    """Rate limiting middleware for API requests."""
    
    def __init__(self, app, default_limits: Dict[str, int] = None):
        """Initialize rate limiting middleware."""
        super().__init__(app)
        
        # Default rate limits (requests per window)
        self.default_limits = default_limits or {
            "default": 100,      # 100 requests per minute
            "authenticated": 500,  # 500 requests per minute
            "admin": 1000,       # 1000 requests per minute
            "api_key": 1000      # 1000 requests per minute
        }
        
        # Rate limit storage (in production, use Redis)
        self.request_counts = defaultdict(lambda: defaultdict(deque))
        self.blocked_ips = {}
        self.window_size = 60  # 1 minute window
        
        # Rate limit configurations
        self.rate_limit_configs = {
            "per_minute": 60,
            "per_hour": 3600,
            "per_day": 86400
        }
        
        # Block duration (in seconds)
        self.block_duration = 300  # 5 minutes
        
        logger.info("Rate limiting middleware initialized")
    
    async def dispatch(self, request: Request, call_next):
        """Process request with rate limiting."""
        
        try:
            # Get client identifier
            client_id = self._get_client_identifier(request)
            
            # Check if IP is blocked
            if self._is_ip_blocked(client_id):
                raise HTTPException(
                    status_code=status.HTTP_429_TOO_MANY_REQUESTS,
                    detail="IP address is temporarily blocked due to excessive requests"
                )
            
            # Check rate limit
            await self._check_rate_limit(request, client_id)
            
            # Process request
            response = await call_next(request)
            
            # Add rate limit headers
            self._add_rate_limit_headers(response, client_id)
            
            return response
            
        except HTTPException:
            raise
        except Exception as e:
            logger.error(f"Error in rate limiting middleware: {e}")
            # Don't block requests due to rate limiting errors
            return await call_next(request)
    
    def _get_client_identifier(self, request: Request) -> str:
        """Get client identifier for rate limiting."""
        
        # Try to get user ID first
        if hasattr(request.state, 'user'):
            return f"user:{request.state.user.get('id', 'unknown')}"
        
        # Try to get API key
        if hasattr(request.state, 'api_key'):
            return f"api_key:{request.state.api_key.get('id', 'unknown')}"
        
        # Fall back to IP address
        return f"ip:{self._get_client_ip(request)}"
    
    def _get_client_ip(self, request: Request) -> str:
        """Get client IP address."""
        
        # Check for forwarded IP
        forwarded_for = request.headers.get("X-Forwarded-For")
        if forwarded_for:
            return forwarded_for.split(",")[0].strip()
        
        # Check for real IP
        real_ip = request.headers.get("X-Real-IP")
        if real_ip:
            return real_ip
        
        # Fall back to client IP
        return request.client.host if request.client else "unknown"
    
    async def _check_rate_limit(self, request: Request, client_id: str):
        """Check if client has exceeded rate limit."""
        
        current_time = time.time()
        
        # Determine rate limit based on client type
        rate_limit = self._get_rate_limit_for_client(request, client_id)
        
        # Get request count for this window
        window_key = int(current_time // self.window_size)
        request_queue = self.request_counts[client_id][window_key]
        
        # Clean old requests from queue
        while request_queue and request_queue[0] < current_time - self.window_size:
            request_queue.popleft()
        
        # Check if rate limit exceeded
        if len(request_queue) >= rate_limit:
            logger.warning(f"Rate limit exceeded for {client_id}: {len(request_queue)}/{rate_limit}")
            
            # Block IP if excessive requests
            if len(request_queue) > rate_limit * 2:
                self._block_client(client_id)
            
            raise HTTPException(
                status_code=status.HTTP_429_TOO_MANY_REQUESTS,
                detail=f"Rate limit exceeded. Maximum {rate_limit} requests per {self.window_size} seconds."
            )
        
        # Add current request to queue
        request_queue.append(current_time)
    
    def _get_rate_limit_for_client(self, request: Request, client_id: str) -> int:
        """Get rate limit based on client type."""
        
        # Check for admin user
        if hasattr(request.state, 'user'):
            user = request.state.user
            if user.get('role') == 'admin':
                return self.default_limits.get('admin', 1000)
            elif user.get('role') in ['moderator', 'premium']:
                return self.default_limits.get('authenticated', 500)
            else:
                return self.default_limits.get('authenticated', 500)
        
        # Check for API key
        if hasattr(request.state, 'api_key'):
            return self.default_limits.get('api_key', 1000)
        
        # Default rate limit
        return self.default_limits.get('default', 100)
    
    def _is_ip_blocked(self, client_id: str) -> bool:
        """Check if client IP is blocked."""
        
        if client_id in self.blocked_ips:
            block_until = self.blocked_ips[client_id]
            if time.time() < block_until:
                return True
            else:
                # Unblock if block duration expired
                del self.blocked_ips[client_id]
        
        return False
    
    def _block_client(self, client_id: str):
        """Block client IP for specified duration."""
        
        block_until = time.time() + self.block_duration
        self.blocked_ips[client_id] = block_until
        
        logger.warning(f"Blocked client {client_id} until {datetime.fromtimestamp(block_until)}")
    
    def _add_rate_limit_headers(self, response, client_id: str):
        """Add rate limit headers to response."""
        
        current_time = time.time()
        window_key = int(current_time // self.window_size)
        
        # Get current request count
        request_queue = self.request_counts[client_id][window_key]
        current_requests = len(request_queue)
        
        # Get rate limit for client
        rate_limit = self.default_limits.get('default', 100)
        
        # Add headers
        response.headers["X-RateLimit-Limit"] = str(rate_limit)
        response.headers["X-RateLimit-Remaining"] = str(max(0, rate_limit - current_requests))
        response.headers["X-RateLimit-Reset"] = str(int((window_key + 1) * self.window_size))
        response.headers["X-RateLimit-Window"] = str(self.window_size)
    
    def set_rate_limit(self, client_type: str, limit: int):
        """Set rate limit for client type."""
        
        self.default_limits[client_type] = limit
        logger.info(f"Rate limit set for {client_type}: {limit} requests per {self.window_size} seconds")
    
    def set_window_size(self, window_size: int):
        """Set rate limit window size."""
        
        self.window_size = window_size
        logger.info(f"Rate limit window size set to {window_size} seconds")
    
    def set_block_duration(self, duration: int):
        """Set block duration for excessive requests."""
        
        self.block_duration = duration
        logger.info(f"Block duration set to {duration} seconds")
    
    def unblock_client(self, client_id: str) -> bool:
        """Unblock a client IP."""
        
        if client_id in self.blocked_ips:
            del self.blocked_ips[client_id]
            logger.info(f"Unblocked client {client_id}")
            return True
        
        return False
    
    def get_client_stats(self, client_id: str) -> Dict[str, Any]:
        """Get statistics for a specific client."""
        
        current_time = time.time()
        window_key = int(current_time // self.window_size)
        
        # Get current request count
        request_queue = self.request_counts[client_id][window_key]
        current_requests = len(request_queue)
        
        # Get rate limit
        rate_limit = self._get_rate_limit_for_client(None, client_id)
        
        return {
            "client_id": client_id,
            "current_requests": current_requests,
            "rate_limit": rate_limit,
            "remaining": max(0, rate_limit - current_requests),
            "is_blocked": self._is_ip_blocked(client_id),
            "blocked_until": self.blocked_ips.get(client_id, 0) if client_id in self.blocked_ips else None
        }
    
    def get_all_stats(self) -> Dict[str, Any]:
        """Get overall rate limiting statistics."""
        
        current_time = time.time()
        window_key = int(current_time // self.window_size)
        
        total_requests = 0
        active_clients = 0
        blocked_clients = len(self.blocked_ips)
        
        for client_id, windows in self.request_counts.items():
            if window_key in windows:
                total_requests += len(windows[window_key])
                if len(windows[window_key]) > 0:
                    active_clients += 1
        
        return {
            "total_requests": total_requests,
            "active_clients": active_clients,
            "blocked_clients": blocked_clients,
            "window_size": self.window_size,
            "current_window": window_key,
            "rate_limits": self.default_limits
        }
    
    def cleanup_old_data(self):
        """Clean up old rate limiting data."""
        
        current_time = time.time()
        cutoff_time = current_time - self.window_size * 2  # Keep 2 windows of data
        
        cleaned_clients = 0
        
        for client_id in list(self.request_counts.keys()):
            for window_key in list(self.request_counts[client_id].keys()):
                window_time = window_key * self.window_size
                
                if window_time < cutoff_time:
                    del self.request_counts[client_id][window_key]
                    cleaned_clients += 1
            
            # Remove client if no windows left
            if not self.request_counts[client_id]:
                del self.request_counts[client_id]
        
        # Clean up expired blocks
        expired_blocks = []
        for client_id, block_until in self.blocked_ips.items():
            if current_time >= block_until:
                expired_blocks.append(client_id)
        
        for client_id in expired_blocks:
            del self.blocked_ips[client_id]
        
        logger.info(f"Cleaned up {cleaned_clients} old rate limiting entries and {len(expired_blocks)} expired blocks")
    
    def export_rate_limit_config(self) -> Dict[str, Any]:
        """Export rate limiting configuration."""
        
        return {
            "default_limits": self.default_limits,
            "window_size": self.window_size,
            "block_duration": self.block_duration,
            "rate_limit_configs": self.rate_limit_configs,
            "statistics": self.get_all_stats()
        }
    
    def import_rate_limit_config(self, config: Dict[str, Any]):
        """Import rate limiting configuration."""
        
        if "default_limits" in config:
            self.default_limits.update(config["default_limits"])
        
        if "window_size" in config:
            self.window_size = config["window_size"]
        
        if "block_duration" in config:
            self.block_duration = config["block_duration"]
        
        if "rate_limit_configs" in config:
            self.rate_limit_configs.update(config["rate_limit_configs"])
        
        logger.info("Rate limiting configuration imported")


class AdvancedRateLimitMiddleware(RateLimitMiddleware):
    """Advanced rate limiting with multiple windows and strategies."""
    
    def __init__(self, app, config: Dict[str, Any] = None):
        """Initialize advanced rate limiting middleware."""
        
        super().__init__(app)
        
        self.config = config or {}
        
        # Multiple rate limit windows
        self.rate_limits = {
            "per_second": self.config.get("per_second", 10),
            "per_minute": self.config.get("per_minute", 100),
            "per_hour": self.config.get("per_hour", 1000),
            "per_day": self.config.get("per_day", 10000)
        }
        
        # Rate limiting strategies
        self.strategies = {
            "sliding_window": self.config.get("sliding_window", True),
            "fixed_window": self.config.get("fixed_window", False),
            "token_bucket": self.config.get("token_bucket", False)
        }
        
        # Token bucket configuration
        self.token_bucket_size = self.config.get("token_bucket_size", 100)
        self.token_refill_rate = self.config.get("token_refill_rate", 10)
        
        # Token buckets for each client
        self.token_buckets = defaultdict(lambda: {
            "tokens": self.token_bucket_size,
            "last_refill": time.time()
        })
        
        logger.info("Advanced rate limiting middleware initialized")
    
    async def _check_rate_limit(self, request: Request, client_id: str):
        """Check rate limit using configured strategy."""
        
        if self.strategies.get("token_bucket"):
            await self._check_token_bucket_rate_limit(request, client_id)
        elif self.strategies.get("sliding_window"):
            await self._check_sliding_window_rate_limit(request, client_id)
        else:
            await super()._check_rate_limit(request, client_id)
    
    async def _check_token_bucket_rate_limit(self, request: Request, client_id: str):
        """Check rate limit using token bucket algorithm."""
        
        current_time = time.time()
        bucket = self.token_buckets[client_id]
        
        # Refill tokens
        time_passed = current_time - bucket["last_refill"]
        tokens_to_add = time_passed * self.token_refill_rate
        
        bucket["tokens"] = min(self.token_bucket_size, bucket["tokens"] + tokens_to_add)
        bucket["last_refill"] = current_time
        
        # Check if token available
        if bucket["tokens"] < 1:
            logger.warning(f"Token bucket empty for {client_id}")
            raise HTTPException(
                status_code=status.HTTP_429_TOO_MANY_REQUESTS,
                detail="Rate limit exceeded. No tokens available."
            )
        
        # Consume token
        bucket["tokens"] -= 1
    
    async def _check_sliding_window_rate_limit(self, request: Request, client_id: str):
        """Check rate limit using sliding window algorithm."""
        
        current_time = time.time()
        
        # Get rate limit for client
        rate_limit = self._get_rate_limit_for_client(request, client_id)
        
        # Use sliding window for minute-level rate limiting
        window_size = 60
        request_queue = self.request_counts[client_id]["sliding"]
        
        # Clean old requests outside the sliding window
        while request_queue and request_queue[0] < current_time - window_size:
            request_queue.popleft()
        
        # Check if rate limit exceeded
        if len(request_queue) >= rate_limit:
            logger.warning(f"Sliding window rate limit exceeded for {client_id}")
            raise HTTPException(
                status_code=status.HTTP_429_TOO_MANY_REQUESTS,
                detail=f"Rate limit exceeded. Maximum {rate_limit} requests per {window_size} seconds."
            )
        
        # Add current request
        request_queue.append(current_time)
    
    def get_token_bucket_stats(self, client_id: str) -> Dict[str, Any]:
        """Get token bucket statistics for client."""
        
        if client_id not in self.token_buckets:
            return {
                "client_id": client_id,
                "tokens": self.token_bucket_size,
                "max_tokens": self.token_bucket_size,
                "refill_rate": self.token_refill_rate,
                "last_refill": time.time()
            }
        
        bucket = self.token_buckets[client_id]
        
        return {
            "client_id": client_id,
            "tokens": bucket["tokens"],
            "max_tokens": self.token_bucket_size,
            "refill_rate": self.token_refill_rate,
            "last_refill": bucket["last_refill"],
            "tokens_available": bucket["tokens"],
            "tokens_used": self.token_bucket_size - bucket["tokens"]
        }
    
    def refill_token_bucket(self, client_id: str, tokens: int) -> bool:
        """Manually refill token bucket for client."""
        
        if client_id not in self.token_buckets:
            self.token_buckets[client_id] = {
                "tokens": self.token_bucket_size,
                "last_refill": time.time()
            }
        
        bucket = self.token_buckets[client_id]
        bucket["tokens"] = min(self.token_bucket_size, bucket["tokens"] + tokens)
        
        logger.info(f"Refilled {tokens} tokens for client {client_id}")
        return True
    
    def set_token_bucket_size(self, size: int):
        """Set token bucket size."""
        
        self.token_bucket_size = size
        
        # Update existing buckets
        for bucket in self.token_buckets.values():
            bucket["tokens"] = min(size, bucket["tokens"])
        
        logger.info(f"Token bucket size set to {size}")
    
    def set_token_refill_rate(self, rate: int):
        """Set token refill rate."""
        
        self.token_refill_rate = rate
        logger.info(f"Token refill rate set to {rate} tokens per second")
    
    def get_advanced_stats(self) -> Dict[str, Any]:
        """Get advanced rate limiting statistics."""
        
        stats = super().get_all_stats()
        
        # Add token bucket stats
        total_tokens = sum(bucket["tokens"] for bucket in self.token_buckets.values())
        max_total_tokens = len(self.token_buckets) * self.token_bucket_size
        
        stats.update({
            "rate_limits": self.rate_limits,
            "strategies": self.strategies,
            "token_buckets": {
                "total_clients": len(self.token_buckets),
                "total_tokens": total_tokens,
                "max_total_tokens": max_total_tokens,
                "bucket_size": self.token_bucket_size,
                "refill_rate": self.token_refill_rate
            }
        })
        
        return stats

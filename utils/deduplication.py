"""
Deduplication utility for preventing duplicate operations
Supports both in-memory (fallback) and Redis-based deduplication
"""
from __future__ import annotations
from typing import Set, Optional
from datetime import datetime, timezone, timedelta
from config import settings
import logging

logger = logging.getLogger(__name__)

# In-memory deduplication tracking (fallback when Redis not available)
_processed_urls: Set[str] = set()
_processed_vehicle_ids: Set[int] = set()
_last_reset: Optional[datetime] = None

_redis_client = None


def _get_redis_client():
    """Get Redis client if configured"""
    global _redis_client
    if _redis_client is None and settings.use_redis:
        try:
            import redis
            _redis_client = redis.from_url(settings.redis_url, decode_responses=True)
            logger.info("Redis deduplication enabled")
        except ImportError:
            logger.warning("redis-py not installed, using in-memory deduplication")
        except Exception as e:
            logger.warning(f"Redis connection failed: {e}, using in-memory deduplication")
    return _redis_client


def is_url_processed(url: str) -> bool:
    """Check if URL has already been processed"""
    redis = _get_redis_client()
    if redis:
        try:
            key = f"dedup:url:{url}"
            return redis.exists(key)
        except Exception as e:
            logger.warning(f"Redis check failed: {e}, falling back to in-memory")
    
    # Fallback to in-memory
    check_and_reset_if_needed()
    return url in _processed_urls


def mark_url_processed(url: str) -> None:
    """Mark URL as processed"""
    redis = _get_redis_client()
    if redis:
        try:
            key = f"dedup:url:{url}"
            redis.setex(key, settings.deduplication_window, "1")
            return
        except Exception as e:
            logger.warning(f"Redis set failed: {e}, falling back to in-memory")
    
    # Fallback to in-memory
    check_and_reset_if_needed()
    _processed_urls.add(url)


def is_vehicle_processed(vehicle_id: int) -> bool:
    """Check if vehicle has already been processed"""
    redis = _get_redis_client()
    if redis:
        try:
            key = f"dedup:vehicle:{vehicle_id}"
            return redis.exists(key)
        except Exception as e:
            logger.warning(f"Redis check failed: {e}, falling back to in-memory")
    
    # Fallback to in-memory
    check_and_reset_if_needed()
    return vehicle_id in _processed_vehicle_ids


def mark_vehicle_processed(vehicle_id: int) -> None:
    """Mark vehicle as processed"""
    redis = _get_redis_client()
    if redis:
        try:
            key = f"dedup:vehicle:{vehicle_id}"
            redis.setex(key, settings.deduplication_window, "1")
            return
        except Exception as e:
            logger.warning(f"Redis set failed: {e}, falling back to in-memory")
    
    # Fallback to in-memory
    check_and_reset_if_needed()
    _processed_vehicle_ids.add(vehicle_id)


def check_and_reset_if_needed() -> None:
    """Reset deduplication tracking if window has expired (in-memory only)"""
    global _last_reset, _processed_urls, _processed_vehicle_ids
    
    if _last_reset is None:
        _last_reset = datetime.now(timezone.utc)
        return
    
    elapsed = (datetime.now(timezone.utc) - _last_reset).total_seconds()
    if elapsed > settings.deduplication_window:
        # Reset tracking after window expires
        _processed_urls.clear()
        _processed_vehicle_ids.clear()
        _last_reset = datetime.now(timezone.utc)


def reset_deduplication() -> None:
    """Manually reset deduplication tracking"""
    redis = _get_redis_client()
    if redis:
        try:
            # Clear all deduplication keys
            for pattern in ["dedup:url:*", "dedup:vehicle:*"]:
                keys = redis.keys(pattern)
                if keys:
                    redis.delete(*keys)
            logger.info("Cleared Redis deduplication keys")
        except Exception as e:
            logger.warning(f"Redis reset failed: {e}")
    
    # Reset in-memory tracking
    global _processed_urls, _processed_vehicle_ids, _last_reset
    _processed_urls.clear()
    _processed_vehicle_ids.clear()
    _last_reset = datetime.now(timezone.utc)


def get_deduplication_stats() -> dict[str, object]:
    """Get deduplication statistics"""
    redis = _get_redis_client()
    redis_stats = {}
    if redis:
        try:
            url_keys = len(redis.keys("dedup:url:*"))
            vehicle_keys = len(redis.keys("dedup:vehicle:*"))
            redis_stats = {
                "redis_enabled": True,
                "redis_url_count": url_keys,
                "redis_vehicle_count": vehicle_keys
            }
        except Exception as e:
            logger.warning(f"Redis stats failed: {e}")
            redis_stats = {"redis_enabled": True, "error": str(e)}
    else:
        redis_stats = {"redis_enabled": False}
    
    return {
        "processed_urls_count": len(_processed_urls),
        "processed_vehicle_ids_count": len(_processed_vehicle_ids),
        "deduplication_window_seconds": settings.deduplication_window,
        "last_reset": _last_reset.isoformat() if _last_reset else None,
        **redis_stats
    }


class Deduplicator:
    """Legacy compatibility wrapper for deduplication helpers."""

    def __init__(self) -> None:
        self._seen: set[str] = set()

    def is_duplicate(self, key: str, value: str) -> bool:
        token = f"{key}:{value}"
        if token in self._seen:
            return True
        self._seen.add(token)
        return False

    def is_url_processed(self, url: str) -> bool:
        return is_url_processed(url)

    def mark_url_processed(self, url: str) -> None:
        mark_url_processed(url)

    def is_vehicle_processed(self, vehicle_id: int) -> bool:
        return is_vehicle_processed(vehicle_id)

    def mark_vehicle_processed(self, vehicle_id: int) -> None:
        mark_vehicle_processed(vehicle_id)

"""
Deduplication utility for preventing duplicate operations
"""
from typing import Set, Optional
from datetime import datetime, timedelta
from config import settings

# In-memory deduplication tracking (for single-run deduplication)
_processed_urls: Set[str] = set()
_processed_vehicle_ids: Set[int] = set()
_last_reset: Optional[datetime] = None


def is_url_processed(url: str) -> bool:
    """Check if URL has already been processed"""
    check_and_reset_if_needed()
    return url in _processed_urls


def mark_url_processed(url: str) -> None:
    """Mark URL as processed"""
    check_and_reset_if_needed()
    _processed_urls.add(url)


def is_vehicle_processed(vehicle_id: int) -> bool:
    """Check if vehicle has already been processed"""
    check_and_reset_if_needed()
    return vehicle_id in _processed_vehicle_ids


def mark_vehicle_processed(vehicle_id: int) -> None:
    """Mark vehicle as processed"""
    check_and_reset_if_needed()
    _processed_vehicle_ids.add(vehicle_id)


def check_and_reset_if_needed() -> None:
    """Reset deduplication tracking if window has expired"""
    global _last_reset, _processed_urls, _processed_vehicle_ids
    
    if _last_reset is None:
        _last_reset = datetime.utcnow()
        return
    
    elapsed = (datetime.utcnow() - _last_reset).total_seconds()
    if elapsed > settings.deduplication_window:
        # Reset tracking after window expires
        _processed_urls.clear()
        _processed_vehicle_ids.clear()
        _last_reset = datetime.utcnow()


def reset_deduplication() -> None:
    """Manually reset deduplication tracking"""
    global _processed_urls, _processed_vehicle_ids, _last_reset
    _processed_urls.clear()
    _processed_vehicle_ids.clear()
    _last_reset = datetime.utcnow()


def get_deduplication_stats() -> dict:
    """Get deduplication statistics"""
    return {
        "processed_urls_count": len(_processed_urls),
        "processed_vehicle_ids_count": len(_processed_vehicle_ids),
        "deduplication_window_seconds": settings.deduplication_window,
        "last_reset": _last_reset.isoformat() if _last_reset else None
    }

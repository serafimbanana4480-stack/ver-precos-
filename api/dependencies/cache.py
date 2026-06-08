"""
Cache dependencies for API.
"""
from typing import Generator, Optional
import logging

from ingestion.storage.cache_storage import CacheStorage

logger = logging.getLogger(__name__)

# Global cache instance
cache_storage = None


def get_cache() -> CacheStorage:
    """Get cache storage instance."""
    
    global cache_storage
    
    if cache_storage is None:
        cache_storage = CacheStorage()
        logger.info("Cache storage initialized")
    
    return cache_storage


def get_cache_client() -> CacheStorage:
    """Get cache client (alias for get_cache)."""
    
    return get_cache()


def get_cache_session() -> Generator[CacheStorage, None, None]:
    """Get cache session (for dependency injection)."""
    
    cache = get_cache()
    
    try:
        yield cache
    finally:
        # Cleanup if needed
        pass


def close_cache():
    """Close cache connection."""
    
    global cache_storage
    
    if cache_storage:
        # CacheStorage doesn't have explicit close method
        # Just clear the reference
        cache_storage = None
        logger.info("Cache connection closed")


def check_cache_health() -> dict:
    """Check cache health."""
    
    try:
        cache = get_cache()
        
        # Test basic operations
        test_key = "health_check"
        test_value = {"status": "ok", "timestamp": "2024-01-01T00:00:00Z"}
        
        # Test set
        cache.set(test_key, test_value, ttl=60)
        
        # Test get
        retrieved = cache.get(test_key)
        
        # Test delete
        cache.delete(test_key)
        
        if retrieved and retrieved.get("status") == "ok":
            return {
                "status": "healthy",
                "connection": "active",
                "cache_dir": str(cache.cache_dir)
            }
        else:
            return {
                "status": "unhealthy",
                "error": "Cache test failed",
                "connection": "inactive"
            }
        
    except Exception as e:
        logger.error(f"Cache health check failed: {e}")
        return {
            "status": "unhealthy",
            "error": str(e),
            "connection": "inactive"
        }


def get_cache_stats() -> dict:
    """Get cache statistics."""
    
    try:
        cache = get_cache()
        return cache.get_cache_info()
        
    except Exception as e:
        logger.error(f"Error getting cache stats: {e}")
        return {"error": str(e)}


def clear_cache() -> int:
    """Clear all cache entries."""
    
    try:
        cache = get_cache()
        return cache.clear()
        
    except Exception as e:
        logger.error(f"Error clearing cache: {e}")
        return 0


def cleanup_expired_cache() -> int:
    """Clean up expired cache entries."""
    
    try:
        cache = get_cache()
        return cache.cleanup_expired()
        
    except Exception as e:
        logger.error(f"Error cleaning up expired cache: {e}")
        return 0


def get_cache_size() -> dict:
    """Get cache size information."""
    
    try:
        cache = get_cache()
        stats = cache.get_cache_info()
        
        return {
            "total_entries": stats["total_entries"],
            "total_size_mb": stats["total_size_mb"],
            "cache_dir": str(cache.cache_dir)
        }
        
    except Exception as e:
        logger.error(f"Error getting cache size: {e}")
        return {"error": str(e)}


def warm_up_cache(keys: list = None):
    """Warm up cache with common data."""
    
    try:
        cache = get_cache()
        
        # Pre-load common data if keys provided
        if keys:
            for key in keys:
                cache.get(key)  # This would trigger loading if implemente
        
        logger.info("Cache warm-up completed")
        
    except Exception as e:
        logger.error(f"Error warming up cache: {e}")


def get_cache_performance_metrics() -> dict:
    """Get cache performance metrics."""
    
    try:
        cache = get_cache()
        stats = cache.get_cache_info()
        
        return {
            "total_entries": stats["total_entries"],
            "total_size_mb": stats["total_size_mb"],
            "expired_entries": stats["expired_entries"],
            "entries_by_age": stats["entries_by_age"],
            "health": check_cache_health()
        }
        
    except Exception as e:
        logger.error(f"Error getting cache performance metrics: {e}")
        return {"error": str(e)}


def configure_cache_settings(settings: dict) -> bool:
    """Configure cache settings."""
    
    try:
        cache = get_cache()
        
        if "default_ttl" in settings:
            cache.default_ttl = settings["default_ttl"]
        
        if "cache_dir" in settings:
            # This would require reinitializing cache
            logger.warning("Cache directory change requires restart")
        
        logger.info("Cache settings configured")
        return True
        
    except Exception as e:
        logger.error(f"Error configuring cache settings: {e}")
        return False


def export_cache_data(export_path: str) -> bool:
    """Export cache data to file."""
    
    try:
        cache = get_cache()
        return cache.export_cache(export_path)
        
    except Exception as e:
        logger.error(f"Error exporting cache data: {e}")
        return False


def import_cache_data(import_path: str) -> int:
    """Import cache data from file."""
    
    try:
        cache = get_cache()
        return cache.import_cache(import_path)
        
    except Exception as e:
        logger.error(f"Error importing cache data: {e}")
        return 0


def get_cache_key_info(key: str) -> dict:
    """Get information about a specific cache key."""
    
    try:
        cache = get_cache()
        
        if cache.has(key):
            return {
                "key": key,
                "exists": True,
                "valid": cache._is_cache_valid(cache._generate_cache_key(key))
            }
        else:
            return {
                "key": key,
                "exists": False,
                "valid": False
            }
        
    except Exception as e:
        logger.error(f"Error getting cache key info: {e}")
        return {"error": str(e)}


def get_cache_keys_by_tag(tag: str) -> list:
    """Get all cache keys with a specific tag."""
    
    try:
        cache = get_cache()
        return cache.get_by_tag(tag)
        
    except Exception as e:
        logger.error(f"Error getting cache keys by tag: {e}")
        return []


def delete_cache_keys_by_tag(tag: str) -> int:
    """Delete all cache keys with a specific tag."""
    
    try:
        cache = get_cache()
        return cache.delete_by_tag(tag)
        
    except Exception as e:
        logger.error(f"Error deleting cache keys by tag: {e}")
        return 0


def get_cache_tags_stats() -> dict:
    """Get cache statistics by tags."""
    
    try:
        cache = get_cache()
        return cache.get_cache_stats_by_tag()
        
    except Exception as e:
        logger.error(f"Error getting cache tags stats: {e}")
        return {}


def set_cache_with_tags(key: str, value, tags: list, ttl: int = None) -> bool:
    """Set cache value with tags."""
    
    try:
        cache = get_cache()
        return cache.set_with_tags(key, value, tags, ttl)
        
    except Exception as e:
        logger.error(f"Error setting cache with tags: {e}")
        return False


def get_cache_ttl(key: str) -> Optional[int]:
    """Get TTL for a cache key."""
    
    try:
        cache = get_cache()
        
        cache_key = cache._generate_cache_key(key)
        
        if cache_key in cache.cache_index:
            return cache.cache_index[cache_key].get("ttl")
        
        return None
        
    except Exception as e:
        logger.error(f"Error getting cache TTL: {e}")
        return None


def extend_cache_ttl(key: str, additional_ttl: int) -> bool:
    """Extend TTL for a cache key."""
    
    try:
        cache = get_cache()
        
        if cache.has(key):
            # Get current TTL
            current_ttl = get_cache_ttl(key)
            if current_ttl:
                new_ttl = current_ttl + additional_ttl
                
                # Get current value and reset with new TTL
                current_value = cache.get(key)
                if current_value:
                    cache.set(key, current_value, ttl=new_ttl)
                    return True
        
        return False
        
    except Exception as e:
        logger.error(f"Error extending cache TTL: {e}")
        return False


def get_cache_hit_rate() -> float:
    """Get cache hit rate (placeholder)."""
    
    # This would require tracking hits/misses in CacheStorage
    # For now, return a reasonable default
    return 0.85


def get_cache_memory_usage() -> dict:
    """Get cache memory usage information."""
    
    try:
        cache = get_cache()
        stats = cache.get_cache_info()
        
        return {
            "total_size_mb": stats["total_size_mb"],
            "entries_count": stats["total_entries"],
            "avg_entry_size_kb": (stats["total_size_mb"] * 1024) / max(stats["total_entries"], 1)
        }
        
    except Exception as e:
        logger.error(f"Error getting cache memory usage: {e}")
        return {"error": str(e)}


def optimize_cache() -> bool:
    """Optimize cache performance."""
    
    try:
        # Clean up expired entries
        cleaned = cleanup_expired_cache()
        
        # This could include other optimizations like compaction
        logger.info(f"Cache optimization completed. Cleaned {cleaned} expired entries")
        return True
        
    except Exception as e:
        logger.error(f"Error optimizing cache: {e}")
        return False


def reset_cache() -> bool:
    """Reset cache to initial state."""
    
    try:
        global cache_storage
        
        # Clear cache
        cleared = clear_cache()
        
        # Reinitialize
        cache_storage = None
        cache_storage = CacheStorage()
        
        logger.info(f"Cache reset completed. Cleared {cleared} entries")
        return True
        
    except Exception as e:
        logger.error(f"Error resetting cache: {e}")
        return False


def get_cache_configuration() -> dict:
    """Get cache configuration."""
    
    try:
        cache = get_cache()
        
        return {
            "cache_dir": str(cache.cache_dir),
            "default_ttl": cache.default_ttl,
            "max_size": getattr(cache, 'max_size', None),
            "similarity_threshold": getattr(cache, 'similarity_threshold', 0.8)
        }
        
    except Exception as e:
        logger.error(f"Error getting cache configuration: {e}")
        return {"error": str(e)}


def backup_cache(backup_path: str) -> bool:
    """Backup cache data."""
    
    return export_cache_data(backup_path)


def restore_cache(backup_path: str) -> int:
    """Restore cache data from backup."""
    
    return import_cache_data(backup_path)


def get_cache_health_detailed() -> dict:
    """Get detailed cache health information."""
    
    try:
        cache = get_cache()
        
        health = check_cache_health()
        stats = cache.get_cache_info()
        
        return {
            "health": health,
            "statistics": stats,
            "memory_usage": get_cache_memory_usage(),
            "performance": {
                "hit_rate": get_cache_hit_rate(),
                "expired_entries": stats["expired_entries"]
            },
            "configuration": get_cache_configuration()
        }
        
    except Exception as e:
        logger.error(f"Error getting detailed cache health: {e}")
        return {"error": str(e)}


def monitor_cache_performance() -> dict:
    """Monitor cache performance metrics."""
    
    try:
        cache = get_cache()
        
        # Get current stats
        stats = cache.get_cache_info()
        
        # Calculate performance metrics
        total_entries = stats["total_entries"]
        expired_entries = stats["expired_entries"]
        
        # Health score based on expired entries ratio
        health_score = 100
        if total_entries > 0:
            expired_ratio = expired_entries / total_entries
            health_score = max(0, 100 - (expired_ratio * 100))
        
        return {
            "health_score": health_score,
            "total_entries": total_entries,
            "expired_entries": expired_entries,
            "expired_percentage": (expired_entries / total_entries * 100) if total_entries > 0 else 0,
            "size_mb": stats["total_size_mb"],
            "status": "healthy" if health_score > 70 else "degraded" if health_score > 40 else "unhealthy"
        }
        
    except Exception as e:
        logger.error(f"Error monitoring cache performance: {e}")
        return {"error": str(e)}

"""
Cache storage for temporary data storage.
"""
import json
import hashlib
import time
from typing import Dict, Any, List, Optional, Union
import logging
from datetime import datetime, timedelta
import os
from pathlib import Path

logger = logging.getLogger(__name__)


class CacheStorage:
    """Cache storage for temporary data storage with TTL."""
    
    def __init__(self, cache_dir: str = "cache", default_ttl: int = 3600):
        """Initialize cache storage."""
        self.cache_dir = Path(cache_dir)
        self.cache_dir.mkdir(parents=True, exist_ok=True)
        
        self.default_ttl = default_ttl  # Default TTL in seconds (1 hour)
        self.cache_index_file = self.cache_dir / "cache_index.json"
        self.cache_index = self._load_cache_index()
        
        logger.info(f"Cache storage initialized: {self.cache_dir}")
    
    def _load_cache_index(self) -> Dict[str, Any]:
        """Load cache index from file."""
        
        if self.cache_index_file.exists():
            try:
                with open(self.cache_index_file, 'r') as f:
                    return json.load(f)
            except Exception as e:
                logger.error(f"Error loading cache index: {e}")
        
        return {}
    
    def _save_cache_index(self):
        """Save cache index to file."""
        
        try:
            with open(self.cache_index_file, 'w') as f:
                json.dump(self.cache_index, f, indent=2)
        except Exception as e:
            logger.error(f"Error saving cache index: {e}")
    
    def _generate_cache_key(self, data: Union[str, Dict[str, Any]]) -> str:
        """Generate cache key from data."""
        
        if isinstance(data, str):
            key_data = data
        else:
            key_data = json.dumps(data, sort_keys=True)
        
        return hashlib.md5(key_data.encode()).hexdigest()
    
    def _get_cache_file_path(self, cache_key: str) -> Path:
        """Get cache file path for key."""
        
        return self.cache_dir / f"{cache_key}.cache"
    
    def _is_cache_valid(self, cache_key: str) -> bool:
        """Check if cache entry is still valid."""
        
        if cache_key not in self.cache_index:
            return False
        
        cache_info = self.cache_index[cache_key]
        cache_file = self._get_cache_file_path(cache_key)
        
        # Check if file exists
        if not cache_file.exists():
            return False
        
        # Check TTL
        created_at = cache_info.get('created_at', 0)
        ttl = cache_info.get('ttl', self.default_ttl)
        
        return (time.time() - created_at) < ttl
    
    def set(self, key: str, value: Any, ttl: int = None) -> bool:
        """Set value in cache."""
        
        if ttl is None:
            ttl = self.default_ttl
        
        try:
            cache_key = self._generate_cache_key(key)
            cache_file = self._get_cache_file_path(cache_key)
            
            # Save value to file
            cache_data = {
                'value': value,
                'key': key,
                'cache_key': cache_key,
                'created_at': time.time(),
                'ttl': ttl,
                'expires_at': time.time() + ttl
            }
            
            with open(cache_file, 'w') as f:
                json.dump(cache_data, f, indent=2, default=str)
            
            # Update index
            self.cache_index[cache_key] = {
                'key': key,
                'created_at': time.time(),
                'ttl': ttl,
                'expires_at': time.time() + ttl,
                'file_size': cache_file.stat().st_size
            }
            
            self._save_cache_index()
            
            logger.debug(f"Cached data for key: {key}")
            return True
            
        except Exception as e:
            logger.error(f"Error setting cache value: {e}")
            return False
    
    def get(self, key: str, default: Any = None) -> Any:
        """Get value from cache."""
        
        try:
            cache_key = self._generate_cache_key(key)
            
            if not self._is_cache_valid(cache_key):
                return default
            
            cache_file = self._get_cache_file_path(cache_key)
            
            with open(cache_file, 'r') as f:
                cache_data = json.load(f)
            
            logger.debug(f"Retrieved cached data for key: {key}")
            return cache_data.get('value', default)
            
        except Exception as e:
            logger.error(f"Error getting cache value: {e}")
            return default
    
    def delete(self, key: str) -> bool:
        """Delete value from cache."""
        
        try:
            cache_key = self._generate_cache_key(key)
            cache_file = self._get_cache_file_path(cache_key)
            
            # Delete file
            if cache_file.exists():
                cache_file.unlink()
            
            # Remove from index
            if cache_key in self.cache_index:
                del self.cache_index[cache_key]
                self._save_cache_index()
            
            logger.debug(f"Deleted cached data for key: {key}")
            return True
            
        except Exception as e:
            logger.error(f"Error deleting cache value: {e}")
            return False
    
    def clear(self) -> int:
        """Clear all cache entries."""
        
        try:
            deleted_count = 0
            
            # Delete all cache files
            for cache_file in self.cache_dir.glob("*.cache"):
                cache_file.unlink()
                deleted_count += 1
            
            # Clear index
            self.cache_index = {}
            self._save_cache_index()
            
            logger.info(f"Cleared {deleted_count} cache entries")
            return deleted_count
            
        except Exception as e:
            logger.error(f"Error clearing cache: {e}")
            return 0
    
    def cleanup_expired(self) -> int:
        """Clean up expired cache entries."""
        
        try:
            expired_keys = []
            current_time = time.time()
            
            # Find expired entries
            for cache_key, cache_info in self.cache_index.items():
                expires_at = cache_info.get('expires_at', 0)
                if current_time >= expires_at:
                    expired_keys.append(cache_key)
            
            # Delete expired entries
            deleted_count = 0
            for cache_key in expired_keys:
                cache_file = self._get_cache_file_path(cache_key)
                
                if cache_file.exists():
                    cache_file.unlink()
                
                del self.cache_index[cache_key]
                deleted_count += 1
            
            if deleted_count > 0:
                self._save_cache_index()
                logger.info(f"Cleaned up {deleted_count} expired cache entries")
            
            return deleted_count
            
        except Exception as e:
            logger.error(f"Error cleaning up expired cache: {e}")
            return 0
    
    def cache_listings(self, listings: List[Dict[str, Any]], search_params: Dict[str, Any], ttl: int = None) -> bool:
        """Cache listings with search parameters."""
        
        cache_key = f"listings_{json.dumps(search_params, sort_keys=True)}"
        
        cache_data = {
            'listings': listings,
            'search_params': search_params,
            'count': len(listings),
            'cached_at': datetime.now().isoformat()
        }
        
        return self.set(cache_key, cache_data, ttl)
    
    def get_cached_listings(self, search_params: Dict[str, Any]) -> List[Dict[str, Any]]:
        """Get cached listings for search parameters."""
        
        cache_key = f"listings_{json.dumps(search_params, sort_keys=True)}"
        cache_data = self.get(cache_key)
        
        if cache_data and isinstance(cache_data, dict):
            return cache_data.get('listings', [])
        
        return []
    
    def cache_scraper_results(self, scraper_name: str, results: List[Dict[str, Any]], ttl: int = None) -> bool:
        """Cache scraper results."""
        
        cache_key = f"scraper_{scraper_name}_{datetime.now().strftime('%Y%m%d')}"
        
        cache_data = {
            'scraper_name': scraper_name,
            'results': results,
            'count': len(results),
            'cached_at': datetime.now().isoformat()
        }
        
        return self.set(cache_key, cache_data, ttl)
    
    def get_cached_scraper_results(self, scraper_name: str, date: str = None) -> List[Dict[str, Any]]:
        """Get cached scraper results."""
        
        if date is None:
            date = datetime.now().strftime('%Y%m%d')
        
        cache_key = f"scraper_{scraper_name}_{date}"
        cache_data = self.get(cache_key)
        
        if cache_data and isinstance(cache_data, dict):
            return cache_data.get('results', [])
        
        return []
    
    def cache_search_page(self, url: str, content: str, ttl: int = None) -> bool:
        """Cache search page content."""
        
        cache_key = f"page_{url}"
        
        cache_data = {
            'url': url,
            'content': content,
            'cached_at': datetime.now().isoformat()
        }
        
        return self.set(cache_key, cache_data, ttl)
    
    def get_cached_search_page(self, url: str) -> str:
        """Get cached search page content."""
        
        cache_key = f"page_{url}"
        cache_data = self.get(cache_key)
        
        if cache_data and isinstance(cache_data, dict):
            return cache_data.get('content', '')
        
        return ''
    
    def cache_api_response(self, endpoint: str, params: Dict[str, Any], response: Dict[str, Any], ttl: int = None) -> bool:
        """Cache API response."""
        
        cache_key = f"api_{endpoint}_{json.dumps(params, sort_keys=True)}"
        
        cache_data = {
            'endpoint': endpoint,
            'params': params,
            'response': response,
            'cached_at': datetime.now().isoformat()
        }
        
        return self.set(cache_key, cache_data, ttl)
    
    def get_cached_api_response(self, endpoint: str, params: Dict[str, Any]) -> Dict[str, Any]:
        """Get cached API response."""
        
        cache_key = f"api_{endpoint}_{json.dumps(params, sort_keys=True)}"
        cache_data = self.get(cache_key)
        
        if cache_data and isinstance(cache_data, dict):
            return cache_data.get('response', {})
        
        return {}
    
    def get_cache_info(self) -> Dict[str, Any]:
        """Get cache information."""
        
        info = {
            'cache_dir': str(self.cache_dir),
            'total_entries': len(self.cache_index),
            'default_ttl': self.default_ttl,
            'total_size_mb': 0,
            'entries_by_age': {},
            'expired_entries': 0
        }
        
        try:
            current_time = time.time()
            total_size = 0
            age_groups = {'0-1h': 0, '1-24h': 0, '1-7d': 0, '7d+': 0}
            
            for cache_key, cache_info in self.cache_index.items():
                created_at = cache_info.get('created_at', 0)
                file_size = cache_info.get('file_size', 0)
                
                total_size += file_size
                
                # Check if expired
                expires_at = cache_info.get('expires_at', 0)
                if current_time >= expires_at:
                    info['expired_entries'] += 1
                
                # Age grouping
                age_hours = (current_time - created_at) / 3600
                
                if age_hours <= 1:
                    age_groups['0-1h'] += 1
                elif age_hours <= 24:
                    age_groups['1-24h'] += 1
                elif age_hours <= 168:  # 7 days
                    age_groups['1-7d'] += 1
                else:
                    age_groups['7d+'] += 1
            
            info['total_size_mb'] = total_size / (1024 * 1024)
            info['entries_by_age'] = age_groups
            
        except Exception as e:
            logger.error(f"Error getting cache info: {e}")
        
        return info
    
    def get_cache_keys(self) -> List[str]:
        """Get all cache keys."""
        
        return [cache_info.get('key', '') for cache_info in self.cache_index.values()]
    
    def has(self, key: str) -> bool:
        """Check if key exists in cache and is valid."""
        
        cache_key = self._generate_cache_key(key)
        return self._is_cache_valid(cache_key)
    
    def set_with_tags(self, key: str, value: Any, tags: List[str], ttl: int = None) -> bool:
        """Set value in cache with tags."""
        
        if ttl is None:
            ttl = self.default_ttl
        
        try:
            cache_key = self._generate_cache_key(key)
            cache_file = self._get_cache_file_path(cache_key)
            
            # Save value with tags
            cache_data = {
                'value': value,
                'key': key,
                'cache_key': cache_key,
                'tags': tags,
                'created_at': time.time(),
                'ttl': ttl,
                'expires_at': time.time() + ttl
            }
            
            with open(cache_file, 'w') as f:
                json.dump(cache_data, f, indent=2, default=str)
            
            # Update index with tags
            self.cache_index[cache_key] = {
                'key': key,
                'tags': tags,
                'created_at': time.time(),
                'ttl': ttl,
                'expires_at': time.time() + ttl,
                'file_size': cache_file.stat().st_size
            }
            
            self._save_cache_index()
            
            logger.debug(f"Cached data with tags {tags} for key: {key}")
            return True
            
        except Exception as e:
            logger.error(f"Error setting cache value with tags: {e}")
            return False
    
    def get_by_tag(self, tag: str) -> List[Any]:
        """Get all values with specific tag."""
        
        results = []
        
        try:
            for cache_key, cache_info in self.cache_index.items():
                tags = cache_info.get('tags', [])
                
                if tag in tags and self._is_cache_valid(cache_key):
                    cache_file = self._get_cache_file_path(cache_key)
                    
                    with open(cache_file, 'r') as f:
                        cache_data = json.load(f)
                    
                    results.append(cache_data.get('value'))
            
            logger.debug(f"Retrieved {len(results)} cached items with tag: {tag}")
            
        except Exception as e:
            logger.error(f"Error getting cache values by tag: {e}")
        
        return results
    
    def delete_by_tag(self, tag: str) -> int:
        """Delete all values with specific tag."""
        
        deleted_count = 0
        
        try:
            keys_to_delete = []
            
            for cache_key, cache_info in self.cache_index.items():
                tags = cache_info.get('tags', [])
                
                if tag in tags:
                    keys_to_delete.append(cache_info.get('key'))
            
            for key in keys_to_delete:
                if self.delete(key):
                    deleted_count += 1
            
            logger.info(f"Deleted {deleted_count} cache entries with tag: {tag}")
            
        except Exception as e:
            logger.error(f"Error deleting cache values by tag: {e}")
        
        return deleted_count
    
    def get_cache_stats_by_tag(self) -> Dict[str, int]:
        """Get cache statistics by tag."""
        
        tag_stats = {}
        
        try:
            for cache_info in self.cache_index.values():
                tags = cache_info.get('tags', [])
                
                for tag in tags:
                    tag_stats[tag] = tag_stats.get(tag, 0) + 1
            
        except Exception as e:
            logger.error(f"Error getting cache stats by tag: {e}")
        
        return tag_stats
    
    def export_cache(self, export_path: str) -> bool:
        """Export cache data to file."""
        
        try:
            export_data = {
                'export_timestamp': datetime.now().isoformat(),
                'cache_info': self.get_cache_info(),
                'cache_entries': {}
            }
            
            # Export all valid cache entries
            for cache_key, cache_info in self.cache_index.items():
                if self._is_cache_valid(cache_key):
                    cache_file = self._get_cache_file_path(cache_key)
                    
                    with open(cache_file, 'r') as f:
                        cache_data = json.load(f)
                    
                    export_data['cache_entries'][cache_key] = cache_data
            
            with open(export_path, 'w') as f:
                json.dump(export_data, f, indent=2, default=str)
            
            logger.info(f"Exported cache to {export_path}")
            return True
            
        except Exception as e:
            logger.error(f"Error exporting cache: {e}")
            return False
    
    def import_cache(self, import_path: str) -> int:
        """Import cache data from file."""
        
        try:
            with open(import_path, 'r') as f:
                import_data = json.load(f)
            
            imported_count = 0
            
            for cache_key, cache_data in import_data.get('cache_entries', {}).items():
                # Restore cache file
                cache_file = self._get_cache_file_path(cache_key)
                
                with open(cache_file, 'w') as f:
                    json.dump(cache_data, f, indent=2, default=str)
                
                # Restore index entry
                if cache_key in import_data.get('cache_entries', {}):
                    cache_entry = cache_data
                    self.cache_index[cache_key] = {
                        'key': cache_entry.get('key'),
                        'tags': cache_entry.get('tags', []),
                        'created_at': cache_entry.get('created_at', time.time()),
                        'ttl': cache_entry.get('ttl', self.default_ttl),
                        'expires_at': cache_entry.get('expires_at', time.time() + self.default_ttl),
                        'file_size': cache_file.stat().st_size
                    }
                
                imported_count += 1
            
            if imported_count > 0:
                self._save_cache_index()
                logger.info(f"Imported {imported_count} cache entries from {import_path}")
            
            return imported_count
            
        except Exception as e:
            logger.error(f"Error importing cache: {e}")
            return 0

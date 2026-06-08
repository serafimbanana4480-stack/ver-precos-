"""
File storage for data persistence.
"""
import json
import csv
import pickle
import pandas as pd
from typing import Dict, Any, List, Optional, Union
import logging
from datetime import datetime
import os
import shutil
from pathlib import Path

logger = logging.getLogger(__name__)


class FileStorage:
    """File storage for car listings data."""
    
    def __init__(self, storage_dir: str = "data"):
        """Initialize file storage."""
        self.storage_dir = Path(storage_dir)
        self.storage_dir.mkdir(parents=True, exist_ok=True)
        
        # Create subdirectories
        (self.storage_dir / "listings").mkdir(exist_ok=True)
        (self.storage_dir / "exports").mkdir(exist_ok=True)
        (self.storage_dir / "backups").mkdir(exist_ok=True)
        (self.storage_dir / "logs").mkdir(exist_ok=True)
        
        logger.info(f"File storage initialized: {self.storage_dir}")
    
    def save_listings_json(self, listings: List[Dict[str, Any]], filename: str = None) -> str:
        """Save listings to JSON file."""
        
        if not listings:
            logger.warning("No listings to save")
            return ""
        
        if filename is None:
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            filename = f"listings_{timestamp}.json"
        
        filepath = self.storage_dir / "listings" / filename
        
        try:
            # Add metadata
            data = {
                "metadata": {
                    "saved_at": datetime.now().isoformat(),
                    "total_listings": len(listings),
                    "sources": list(set(listing.get('source', 'unknown') for listing in listings)),
                    "date_range": self._get_date_range(listings)
                },
                "listings": listings
            }
            
            with open(filepath, 'w', encoding='utf-8') as f:
                json.dump(data, f, indent=2, ensure_ascii=False, default=str)
            
            logger.info(f"Saved {len(listings)} listings to {filepath}")
            return str(filepath)
            
        except Exception as e:
            logger.error(f"Error saving listings to JSON: {e}")
            return ""
    
    def load_listings_json(self, filename: str) -> List[Dict[str, Any]]:
        """Load listings from JSON file."""
        
        filepath = self.storage_dir / "listings" / filename
        
        if not filepath.exists():
            logger.warning(f"File not found: {filepath}")
            return []
        
        try:
            with open(filepath, 'r', encoding='utf-8') as f:
                data = json.load(f)
            
            if isinstance(data, dict) and 'listings' in data:
                return data['listings']
            elif isinstance(data, list):
                return data
            else:
                logger.error(f"Invalid JSON format in {filepath}")
                return []
                
        except Exception as e:
            logger.error(f"Error loading listings from JSON: {e}")
            return []
    
    def save_listings_csv(self, listings: List[Dict[str, Any]], filename: str = None) -> str:
        """Save listings to CSV file."""
        
        if not listings:
            logger.warning("No listings to save")
            return ""
        
        if filename is None:
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            filename = f"listings_{timestamp}.csv"
        
        filepath = self.storage_dir / "listings" / filename
        
        try:
            df = pd.DataFrame(listings)
            df.to_csv(filepath, index=False, encoding='utf-8')
            
            logger.info(f"Saved {len(listings)} listings to {filepath}")
            return str(filepath)
            
        except Exception as e:
            logger.error(f"Error saving listings to CSV: {e}")
            return ""
    
    def load_listings_csv(self, filename: str) -> List[Dict[str, Any]]:
        """Load listings from CSV file."""
        
        filepath = self.storage_dir / "listings" / filename
        
        if not filepath.exists():
            logger.warning(f"File not found: {filepath}")
            return []
        
        try:
            df = pd.read_csv(filepath, encoding='utf-8')
            
            # Convert NaN values to None
            df = df.where(pd.notnull(df), None)
            
            return df.to_dict('records')
            
        except Exception as e:
            logger.error(f"Error loading listings from CSV: {e}")
            return []
    
    def save_listings_parquet(self, listings: List[Dict[str, Any]], filename: str = None) -> str:
        """Save listings to Parquet file."""
        
        if not listings:
            logger.warning("No listings to save")
            return ""
        
        if filename is None:
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            filename = f"listings_{timestamp}.parquet"
        
        filepath = self.storage_dir / "listings" / filename
        
        try:
            df = pd.DataFrame(listings)
            df.to_parquet(filepath, index=False)
            
            logger.info(f"Saved {len(listings)} listings to {filepath}")
            return str(filepath)
            
        except Exception as e:
            logger.error(f"Error saving listings to Parquet: {e}")
            return ""
    
    def load_listings_parquet(self, filename: str) -> List[Dict[str, Any]]:
        """Load listings from Parquet file."""
        
        filepath = self.storage_dir / "listings" / filename
        
        if not filepath.exists():
            logger.warning(f"File not found: {filepath}")
            return []
        
        try:
            df = pd.read_parquet(filepath)
            return df.to_dict('records')
            
        except Exception as e:
            logger.error(f"Error loading listings from Parquet: {e}")
            return []
    
    def save_listings_pickle(self, listings: List[Dict[str, Any]], filename: str = None) -> str:
        """Save listings to pickle file."""
        
        if not listings:
            logger.warning("No listings to save")
            return ""
        
        if filename is None:
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            filename = f"listings_{timestamp}.pkl"
        
        filepath = self.storage_dir / "listings" / filename
        
        try:
            with open(filepath, 'wb') as f:
                pickle.dump(listings, f)
            
            logger.info(f"Saved {len(listings)} listings to {filepath}")
            return str(filepath)
            
        except Exception as e:
            logger.error(f"Error saving listings to pickle: {e}")
            return ""
    
    def load_listings_pickle(self, filename: str) -> List[Dict[str, Any]]:
        """Load listings from pickle file."""
        
        filepath = self.storage_dir / "listings" / filename
        
        if not filepath.exists():
            logger.warning(f"File not found: {filepath}")
            return []
        
        try:
            with open(filepath, 'rb') as f:
                return pickle.load(f)
                
        except Exception as e:
            logger.error(f"Error loading listings from pickle: {e}")
            return []
    
    def append_to_file(self, listings: List[Dict[str, Any]], filename: str, format: str = 'json') -> bool:
        """Append listings to existing file."""
        
        if not listings:
            return False
        
        filepath = self.storage_dir / "listings" / filename
        
        try:
            if format == 'json':
                # Load existing data
                existing_data = []
                if filepath.exists():
                    existing_data = self.load_listings_json(filename)
                
                # Append new data
                existing_data.extend(listings)
                
                # Save back
                self.save_listings_json(existing_data, filename)
                return True
                
            elif format == 'csv':
                # For CSV, append to file
                df = pd.DataFrame(listings)
                
                if filepath.exists():
                    df.to_csv(filepath, mode='a', header=False, index=False, encoding='utf-8')
                else:
                    df.to_csv(filepath, index=False, encoding='utf-8')
                
                return True
                
        except Exception as e:
            logger.error(f"Error appending to file: {e}")
            return False
    
    def get_file_list(self, directory: str = "listings") -> List[str]:
        """Get list of files in directory."""
        
        dir_path = self.storage_dir / directory
        
        if not dir_path.exists():
            return []
        
        try:
            return [f.name for f in dir_path.iterdir() if f.is_file()]
            
        except Exception as e:
            logger.error(f"Error getting file list: {e}")
            return []
    
    def get_file_info(self, filename: str, directory: str = "listings") -> Dict[str, Any]:
        """Get file information."""
        
        filepath = self.storage_dir / directory / filename
        
        if not filepath.exists():
            return {}
        
        try:
            stat = filepath.stat()
            
            info = {
                'filename': filename,
                'filepath': str(filepath),
                'size_bytes': stat.st_size,
                'size_mb': stat.st_size / (1024 * 1024),
                'created': datetime.fromtimestamp(stat.st_ctime).isoformat(),
                'modified': datetime.fromtimestamp(stat.st_mtime).isoformat(),
                'extension': filepath.suffix.lower()
            }
            
            # Add listing count if it's a data file
            if directory == "listings":
                if filepath.suffix.lower() == '.json':
                    data = self.load_listings_json(filename)
                    info['listings_count'] = len(data) if isinstance(data, list) else 0
                elif filepath.suffix.lower() == '.csv':
                    data = self.load_listings_csv(filename)
                    info['listings_count'] = len(data) if isinstance(data, list) else 0
                elif filepath.suffix.lower() == '.parquet':
                    data = self.load_listings_parquet(filename)
                    info['listings_count'] = len(data) if isinstance(data, list) else 0
                elif filepath.suffix.lower() == '.pkl':
                    data = self.load_listings_pickle(filename)
                    info['listings_count'] = len(data) if isinstance(data, list) else 0
            
            return info
            
        except Exception as e:
            logger.error(f"Error getting file info: {e}")
            return {}
    
    def delete_file(self, filename: str, directory: str = "listings") -> bool:
        """Delete a file."""
        
        filepath = self.storage_dir / directory / filename
        
        try:
            if filepath.exists():
                filepath.unlink()
                logger.info(f"Deleted file: {filepath}")
                return True
            else:
                logger.warning(f"File not found: {filepath}")
                return False
                
        except Exception as e:
            logger.error(f"Error deleting file: {e}")
            return False
    
    def backup_file(self, filename: str, directory: str = "listings") -> str:
        """Create a backup of a file."""
        
        filepath = self.storage_dir / directory / filename
        
        if not filepath.exists():
            logger.warning(f"File not found: {filepath}")
            return ""
        
        try:
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            backup_filename = f"{filepath.stem}_backup_{timestamp}{filepath.suffix}"
            backup_path = self.storage_dir / "backups" / backup_filename
            
            shutil.copy2(filepath, backup_path)
            
            logger.info(f"Created backup: {backup_path}")
            return str(backup_path)
            
        except Exception as e:
            logger.error(f"Error creating backup: {e}")
            return ""
    
    def cleanup_old_files(self, directory: str = "listings", days: int = 30) -> int:
        """Clean up old files."""
        
        dir_path = self.storage_dir / directory
        
        if not dir_path.exists():
            return 0
        
        try:
            cutoff_time = datetime.now() - timedelta(days=days)
            deleted_count = 0
            
            for filepath in dir_path.iterdir():
                if filepath.is_file():
                    file_time = datetime.fromtimestamp(filepath.stat().st_mtime)
                    
                    if file_time < cutoff_time:
                        filepath.unlink()
                        deleted_count += 1
            
            logger.info(f"Cleaned up {deleted_count} old files from {directory}")
            return deleted_count
            
        except Exception as e:
            logger.error(f"Error cleaning up old files: {e}")
            return 0
    
    def compress_files(self, directory: str = "listings") -> str:
        """Compress directory into zip file."""
        
        dir_path = self.storage_dir / directory
        
        if not dir_path.exists():
            logger.warning(f"Directory not found: {dir_path}")
            return ""
        
        try:
            import zipfile
            
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            zip_filename = f"{directory}_{timestamp}.zip"
            zip_path = self.storage_dir / zip_filename
            
            with zipfile.ZipFile(zip_path, 'w', zipfile.ZIP_DEFLATED) as zipf:
                for filepath in dir_path.rglob('*'):
                    if filepath.is_file():
                        zipf.write(filepath, filepath.name)
            
            logger.info(f"Compressed directory to: {zip_path}")
            return str(zip_path)
            
        except Exception as e:
            logger.error(f"Error compressing directory: {e}")
            return ""
    
    def get_storage_stats(self) -> Dict[str, Any]:
        """Get storage statistics."""
        
        stats = {
            'storage_dir': str(self.storage_dir),
            'total_size_mb': 0,
            'file_count': 0,
            'directory_stats': {}
        }
        
        try:
            # Calculate total size and file count
            for item in self.storage_dir.rglob('*'):
                if item.is_file():
                    stats['total_size_mb'] += item.stat().st_size / (1024 * 1024)
                    stats['file_count'] += 1
            
            # Get directory stats
            for subdir in self.storage_dir.iterdir():
                if subdir.is_dir():
                    subdir_stats = self._get_directory_stats(subdir.name)
                    stats['directory_stats'][subdir.name] = subdir_stats
            
        except Exception as e:
            logger.error(f"Error getting storage stats: {e}")
        
        return stats
    
    def _get_directory_stats(self, directory: str) -> Dict[str, Any]:
        """Get statistics for a specific directory."""
        
        dir_path = self.storage_dir / directory
        
        if not dir_path.exists():
            return {}
        
        stats = {
            'file_count': 0,
            'total_size_mb': 0,
            'file_types': {},
            'largest_file': None,
            'newest_file': None,
            'oldest_file': None
        }
        
        try:
            files = []
            for filepath in dir_path.rglob('*'):
                if filepath.is_file():
                    files.append(filepath)
            
            stats['file_count'] = len(files)
            
            if files:
                # Calculate total size
                total_size = sum(f.stat().st_size for f in files)
                stats['total_size_mb'] = total_size / (1024 * 1024)
                
                # File types
                for filepath in files:
                    ext = filepath.suffix.lower()
                    stats['file_types'][ext] = stats['file_types'].get(ext, 0) + 1
                
                # Largest file
                largest_file = max(files, key=lambda f: f.stat().st_size)
                stats['largest_file'] = {
                    'name': largest_file.name,
                    'size_mb': largest_file.stat().st_size / (1024 * 1024)
                }
                
                # Newest and oldest files
                newest_file = max(files, key=lambda f: f.stat().st_mtime)
                oldest_file = min(files, key=lambda f: f.stat().st_mtime)
                
                stats['newest_file'] = {
                    'name': newest_file.name,
                    'modified': datetime.fromtimestamp(newest_file.stat().st_mtime).isoformat()
                }
                
                stats['oldest_file'] = {
                    'name': oldest_file.name,
                    'modified': datetime.fromtimestamp(oldest_file.stat().st_mtime).isoformat()
                }
        
        except Exception as e:
            logger.error(f"Error getting directory stats for {directory}: {e}")
        
        return stats
    
    def _get_date_range(self, listings: List[Dict[str, Any]]) -> Dict[str, str]:
        """Get date range from listings."""
        
        dates = []
        
        for listing in listings:
            scraped_at = listing.get('scraped_at')
            if scraped_at:
                try:
                    dates.append(datetime.fromisoformat(scraped_at.replace('Z', '+00:00')))
                except:
                    continue
        
        if not dates:
            return {}
        
        return {
            'earliest': min(dates).isoformat(),
            'latest': max(dates).isoformat()
        }
    
    def export_listings(self, listings: List[Dict[str, Any]], filename: str = None, format: str = 'csv') -> str:
        """Export listings to file with format selection."""
        
        if format == 'json':
            return self.save_listings_json(listings, filename)
        elif format == 'csv':
            return self.save_listings_csv(listings, filename)
        elif format == 'parquet':
            return self.save_listings_parquet(listings, filename)
        elif format == 'pickle':
            return self.save_listings_pickle(listings, filename)
        else:
            logger.error(f"Unsupported format: {format}")
            return ""
    
    def import_listings(self, filename: str, directory: str = "listings", format: str = 'json') -> List[Dict[str, Any]]:
        """Import listings from file with format selection."""
        
        if format == 'json':
            return self.load_listings_json(filename)
        elif format == 'csv':
            return self.load_listings_csv(filename)
        elif format == 'parquet':
            return self.load_listings_parquet(filename)
        elif format == 'pickle':
            return self.load_listings_pickle(filename)
        else:
            logger.error(f"Unsupported format: {format}")
            return []

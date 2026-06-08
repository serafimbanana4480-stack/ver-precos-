"""
Database storage for data persistence.
"""
import sqlite3
import pandas as pd
import json
from typing import Dict, Any, List, Optional, Union
import logging
from datetime import datetime, timedelta
import asyncio
import aiosqlite

logger = logging.getLogger(__name__)


class DatabaseStorage:
    """Database storage for car listings data."""
    
    def __init__(self, db_path: str = "ver_precos.db"):
        """Initialize database storage."""
        self.db_path = db_path
        self.connection = None
        self.async_connection = None
        self._initialize_database()
    
    def _initialize_database(self):
        """Initialize database and create tables."""
        
        try:
            self.connection = sqlite3.connect(self.db_path)
            self.connection.row_factory = sqlite3.Row
            
            # Create tables
            self._create_tables()
            
            logger.info(f"Database initialized: {self.db_path}")
            
        except Exception as e:
            logger.error(f"Error initializing database: {e}")
            raise
    
    def _create_tables(self):
        """Create database tables."""
        
        cursor = self.connection.cursor()
        
        # Listings table
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS listings (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                listing_id TEXT UNIQUE,
                source TEXT NOT NULL,
                url TEXT,
                title TEXT,
                make TEXT,
                model TEXT,
                year INTEGER,
                price REAL,
                mileage INTEGER,
                fuel_type TEXT,
                transmission TEXT,
                engine_size REAL,
                location TEXT,
                condition TEXT,
                description TEXT,
                image_url TEXT,
                seller_name TEXT,
                seller_type TEXT,
                scraped_at TIMESTAMP,
                updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        ''')
        
        # Create indexes
        cursor.execute('''
            CREATE INDEX IF NOT EXISTS idx_listings_source ON listings(source)
        ''')
        
        cursor.execute('''
            CREATE INDEX IF NOT EXISTS idx_listings_make_model ON listings(make, model)
        ''')
        
        cursor.execute('''
            CREATE INDEX IF NOT EXISTS idx_listings_price ON listings(price)
        ''')
        
        cursor.execute('''
            CREATE INDEX IF NOT EXISTS idx_listings_scraped_at ON listings(scraped_at)
        ''')
        
        # Search history table
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS search_history (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                search_params TEXT,
                results_count INTEGER,
                search_timestamp TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                source TEXT
            )
        ''')
        
        # Data quality metrics table
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS data_quality (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                source TEXT,
                total_records INTEGER,
                valid_records INTEGER,
                missing_fields TEXT,
                quality_score REAL,
                check_timestamp TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        ''')
        
        self.connection.commit()
    
    async def initialize_async(self):
        """Initialize async database connection."""
        
        try:
            self.async_connection = await aiosqlite.connect(self.db_path)
            self.async_connection.row_factory = aiosqlite.Row
            
            # Enable WAL mode for better performance
            await self.async_connection.execute('PRAGMA journal_mode=WAL')
            
            logger.info(f"Async database initialized: {self.db_path}")
            
        except Exception as e:
            logger.error(f"Error initializing async database: {e}")
            raise
    
    async def close_async(self):
        """Close async database connection."""
        
        if self.async_connection:
            await self.async_connection.close()
            self.async_connection = None
    
    def close(self):
        """Close database connection."""
        
        if self.connection:
            self.connection.close()
            self.connection = None
    
    def save_listings(self, listings: List[Dict[str, Any]]) -> Dict[str, Any]:
        """Save listings to database."""
        
        if not listings:
            return {'saved': 0, 'updated': 0, 'errors': []}
        
        saved_count = 0
        updated_count = 0
        errors = []
        
        try:
            cursor = self.connection.cursor()
            
            for listing in listings:
                try:
                    # Prepare data for insertion
                    data = {
                        'listing_id': listing.get('listing_id'),
                        'source': listing.get('source'),
                        'url': listing.get('url'),
                        'title': listing.get('title'),
                        'make': listing.get('make'),
                        'model': listing.get('model'),
                        'year': listing.get('year'),
                        'price': listing.get('price'),
                        'mileage': listing.get('mileage'),
                        'fuel_type': listing.get('fuel_type'),
                        'transmission': listing.get('transmission'),
                        'engine_size': listing.get('engine_size'),
                        'location': listing.get('location'),
                        'condition': listing.get('condition'),
                        'description': listing.get('description'),
                        'image_url': listing.get('image_url'),
                        'seller_name': listing.get('seller_name'),
                        'seller_type': listing.get('seller_type'),
                        'scraped_at': listing.get('scraped_at')
                    }
                    
                    # Check if listing already exists
                    cursor.execute('''
                        SELECT id FROM listings 
                        WHERE listing_id = ? AND source = ?
                    ''', (data['listing_id'], data['source']))
                    
                    existing = cursor.fetchone()
                    
                    if existing:
                        # Update existing listing
                        set_clause = ', '.join([f"{k} = ?" for k in data.keys() if k != 'listing_id' and k != 'source'])
                        values = [v for k, v in data.items() if k != 'listing_id' and k != 'source'] + [data['listing_id'], data['source']]
                        
                        cursor.execute(f'''
                            UPDATE listings 
                            SET {set_clause}, updated_at = CURRENT_TIMESTAMP
                            WHERE listing_id = ? AND source = ?
                        ''', values)
                        
                        updated_count += 1
                    else:
                        # Insert new listing
                        columns = ', '.join(data.keys())
                        placeholders = ', '.join(['?'] * len(data))
                        
                        cursor.execute(f'''
                            INSERT INTO listings ({columns})
                            VALUES ({placeholders})
                        ''', list(data.values()))
                        
                        saved_count += 1
                
                except Exception as e:
                    errors.append(f"Error saving listing {listing.get('listing_id', 'unknown')}: {e}")
                    continue
            
            self.connection.commit()
            
            logger.info(f"Saved {saved_count} new listings, updated {updated_count} existing listings")
            
            return {
                'saved': saved_count,
                'updated': updated_count,
                'errors': errors
            }
            
        except Exception as e:
            logger.error(f"Error saving listings to database: {e}")
            return {'saved': 0, 'updated': 0, 'errors': [str(e)]}
    
    async def save_listings_async(self, listings: List[Dict[str, Any]]) -> Dict[str, Any]:
        """Save listings to database asynchronously."""
        
        if not self.async_connection:
            await self.initialize_async()
        
        if not listings:
            return {'saved': 0, 'updated': 0, 'errors': []}
        
        saved_count = 0
        updated_count = 0
        errors = []
        
        try:
            for listing in listings:
                try:
                    # Prepare data for insertion
                    data = {
                        'listing_id': listing.get('listing_id'),
                        'source': listing.get('source'),
                        'url': listing.get('url'),
                        'title': listing.get('title'),
                        'make': listing.get('make'),
                        'model': listing.get('model'),
                        'year': listing.get('year'),
                        'price': listing.get('price'),
                        'mileage': listing.get('mileage'),
                        'fuel_type': listing.get('fuel_type'),
                        'transmission': listing.get('transmission'),
                        'engine_size': listing.get('engine_size'),
                        'location': listing.get('location'),
                        'condition': listing.get('condition'),
                        'description': listing.get('description'),
                        'image_url': listing.get('image_url'),
                        'seller_name': listing.get('seller_name'),
                        'seller_type': listing.get('seller_type'),
                        'scraped_at': listing.get('scraped_at')
                    }
                    
                    # Check if listing already exists
                    cursor = await self.async_connection.execute('''
                        SELECT id FROM listings 
                        WHERE listing_id = ? AND source = ?
                    ''', (data['listing_id'], data['source']))
                    
                    existing = await cursor.fetchone()
                    
                    if existing:
                        # Update existing listing
                        set_clause = ', '.join([f"{k} = ?" for k in data.keys() if k != 'listing_id' and k != 'source'])
                        values = [v for k, v in data.items() if k != 'listing_id' and k != 'source'] + [data['listing_id'], data['source']]
                        
                        await self.async_connection.execute(f'''
                            UPDATE listings 
                            SET {set_clause}, updated_at = CURRENT_TIMESTAMP
                            WHERE listing_id = ? AND source = ?
                        ''', values)
                        
                        updated_count += 1
                    else:
                        # Insert new listing
                        columns = ', '.join(data.keys())
                        placeholders = ', '.join(['?'] * len(data))
                        
                        await self.async_connection.execute(f'''
                            INSERT INTO listings ({columns})
                            VALUES ({placeholders})
                        ''', list(data.values()))
                        
                        saved_count += 1
                
                except Exception as e:
                    errors.append(f"Error saving listing {listing.get('listing_id', 'unknown')}: {e}")
                    continue
            
            await self.async_connection.commit()
            
            logger.info(f"Async saved {saved_count} new listings, updated {updated_count} existing listings")
            
            return {
                'saved': saved_count,
                'updated': updated_count,
                'errors': errors
            }
            
        except Exception as e:
            logger.error(f"Error saving listings to database async: {e}")
            return {'saved': 0, 'updated': 0, 'errors': [str(e)]}
    
    def get_listings(self, 
                    source: str = None,
                    make: str = None,
                    model: str = None,
                    min_price: float = None,
                    max_price: float = None,
                    min_year: int = None,
                    max_year: int = None,
                    location: str = None,
                    limit: int = 100,
                    offset: int = 0) -> List[Dict[str, Any]]:
        """Get listings from database with filters."""
        
        try:
            cursor = self.connection.cursor()
            
            # Build query
            query = "SELECT * FROM listings WHERE 1=1"
            params = []
            
            if source:
                query += " AND source = ?"
                params.append(source)
            
            if make:
                query += " AND make = ?"
                params.append(make)
            
            if model:
                query += " AND model = ?"
                params.append(model)
            
            if min_price:
                query += " AND price >= ?"
                params.append(min_price)
            
            if max_price:
                query += " AND price <= ?"
                params.append(max_price)
            
            if min_year:
                query += " AND year >= ?"
                params.append(min_year)
            
            if max_year:
                query += " AND year <= ?"
                params.append(max_year)
            
            if location:
                query += " AND location LIKE ?"
                params.append(f"%{location}%")
            
            # Add ordering and pagination
            query += " ORDER BY scraped_at DESC LIMIT ? OFFSET ?"
            params.extend([limit, offset])
            
            cursor.execute(query, params)
            rows = cursor.fetchall()
            
            # Convert to list of dictionaries
            listings = [dict(row) for row in rows]
            
            return listings
            
        except Exception as e:
            logger.error(f"Error getting listings from database: {e}")
            return []
    
    def get_listing_by_id(self, listing_id: str, source: str = None) -> Optional[Dict[str, Any]]:
        """Get a specific listing by ID."""
        
        try:
            cursor = self.connection.cursor()
            
            if source:
                cursor.execute('''
                    SELECT * FROM listings 
                    WHERE listing_id = ? AND source = ?
                ''', (listing_id, source))
            else:
                cursor.execute('''
                    SELECT * FROM listings 
                    WHERE listing_id = ?
                ''', (listing_id,))
            
            row = cursor.fetchone()
            
            return dict(row) if row else None
            
        except Exception as e:
            logger.error(f"Error getting listing by ID: {e}")
            return None
    
    def delete_listing(self, listing_id: str, source: str = None) -> bool:
        """Delete a listing from database."""
        
        try:
            cursor = self.connection.cursor()
            
            if source:
                cursor.execute('''
                    DELETE FROM listings 
                    WHERE listing_id = ? AND source = ?
                ''', (listing_id, source))
            else:
                cursor.execute('''
                    DELETE FROM listings 
                    WHERE listing_id = ?
                ''', (listing_id,))
            
            self.connection.commit()
            
            return cursor.rowcount > 0
            
        except Exception as e:
            logger.error(f"Error deleting listing: {e}")
            return False
    
    def save_search_history(self, search_params: Dict[str, Any], results_count: int, source: str):
        """Save search history to database."""
        
        try:
            cursor = self.connection.cursor()
            
            cursor.execute('''
                INSERT INTO search_history (search_params, results_count, source)
                VALUES (?, ?, ?)
            ''', (json.dumps(search_params), results_count, source))
            
            self.connection.commit()
            
        except Exception as e:
            logger.error(f"Error saving search history: {e}")
    
    def get_search_history(self, source: str = None, limit: int = 100) -> List[Dict[str, Any]]:
        """Get search history from database."""
        
        try:
            cursor = self.connection.cursor()
            
            if source:
                cursor.execute('''
                    SELECT * FROM search_history 
                    WHERE source = ?
                    ORDER BY search_timestamp DESC
                    LIMIT ?
                ''', (source, limit))
            else:
                cursor.execute('''
                    SELECT * FROM search_history 
                    ORDER BY search_timestamp DESC
                    LIMIT ?
                ''', (limit,))
            
            rows = cursor.fetchall()
            
            return [dict(row) for row in rows]
            
        except Exception as e:
            logger.error(f"Error getting search history: {e}")
            return []
    
    def save_data_quality_metrics(self, metrics: Dict[str, Any]):
        """Save data quality metrics to database."""
        
        try:
            cursor = self.connection.cursor()
            
            cursor.execute('''
                INSERT INTO data_quality (source, total_records, valid_records, missing_fields, quality_score)
                VALUES (?, ?, ?, ?, ?)
            ''', (
                metrics.get('source'),
                metrics.get('total_records'),
                metrics.get('valid_records'),
                json.dumps(metrics.get('missing_fields', {})),
                metrics.get('quality_score')
            ))
            
            self.connection.commit()
            
        except Exception as e:
            logger.error(f"Error saving data quality metrics: {e}")
    
    def get_data_quality_metrics(self, source: str = None, days: int = 30) -> List[Dict[str, Any]]:
        """Get data quality metrics from database."""
        
        try:
            cursor = self.connection.cursor()
            
            if source:
                cursor.execute('''
                    SELECT * FROM data_quality 
                    WHERE source = ? AND check_timestamp >= datetime('now', '-{} days')
                    ORDER BY check_timestamp DESC
                '''.format(days), (source,))
            else:
                cursor.execute('''
                    SELECT * FROM data_quality 
                    WHERE check_timestamp >= datetime('now', '-{} days')
                    ORDER BY check_timestamp DESC
                '''.format(days))
            
            rows = cursor.fetchall()
            
            return [dict(row) for row in rows]
            
        except Exception as e:
            logger.error(f"Error getting data quality metrics: {e}")
            return []
    
    def get_statistics(self) -> Dict[str, Any]:
        """Get database statistics."""
        
        try:
            cursor = self.connection.cursor()
            
            stats = {}
            
            # Total listings
            cursor.execute('SELECT COUNT(*) as total FROM listings')
            stats['total_listings'] = cursor.fetchone()['total']
            
            # Listings by source
            cursor.execute('''
                SELECT source, COUNT(*) as count 
                FROM listings 
                GROUP BY source
            ''')
            stats['listings_by_source'] = {row['source']: row['count'] for row in cursor.fetchall()}
            
            # Listings by make
            cursor.execute('''
                SELECT make, COUNT(*) as count 
                FROM listings 
                WHERE make IS NOT NULL
                GROUP BY make
                ORDER BY count DESC
                LIMIT 10
            ''')
            stats['top_makes'] = {row['make']: row['count'] for row in cursor.fetchall()}
            
            # Price statistics
            cursor.execute('''
                SELECT 
                    AVG(price) as avg_price,
                    MIN(price) as min_price,
                    MAX(price) as max_price,
                    COUNT(*) as count
                FROM listings 
                WHERE price IS NOT NULL
            ''')
            price_stats = cursor.fetchone()
            stats['price_stats'] = dict(price_stats) if price_stats else {}
            
            # Recent activity
            cursor.execute('''
                SELECT COUNT(*) as recent_count
                FROM listings 
                WHERE scraped_at >= datetime('now', '-7 days')
            ''')
            stats['recent_listings'] = cursor.fetchone()['recent_count']
            
            # Database size
            cursor.execute('''
                SELECT page_count * 1024 as size_bytes
                FROM pragma_page_count()
                WHERE name = 'main'
            ''')
            size_info = cursor.fetchone()
            stats['database_size_mb'] = size_info['size_bytes'] / (1024 * 1024) if size_info else 0
            
            return stats
            
        except Exception as e:
            logger.error(f"Error getting database statistics: {e}")
            return {}
    
    def cleanup_old_listings(self, days: int = 90) -> int:
        """Clean up old listings from database."""
        
        try:
            cursor = self.connection.cursor()
            
            cursor.execute('''
                DELETE FROM listings 
                WHERE scraped_at < datetime('now', '-{} days')
            '''.format(days))
            
            deleted_count = cursor.rowcount
            self.connection.commit()
            
            logger.info(f"Cleaned up {deleted_count} old listings (older than {days} days)")
            
            return deleted_count
            
        except Exception as e:
            logger.error(f"Error cleaning up old listings: {e}")
            return 0
    
    def export_to_csv(self, filepath: str, **filters) -> bool:
        """Export listings to CSV file."""
        
        try:
            listings = self.get_listings(**filters)
            
            if not listings:
                logger.warning("No listings to export")
                return False
            
            df = pd.DataFrame(listings)
            df.to_csv(filepath, index=False)
            
            logger.info(f"Exported {len(listings)} listings to {filepath}")
            return True
            
        except Exception as e:
            logger.error(f"Error exporting to CSV: {e}")
            return False
    
    def import_from_csv(self, filepath: str) -> Dict[str, Any]:
        """Import listings from CSV file."""
        
        try:
            df = pd.read_csv(filepath)
            
            # Convert DataFrame to list of dictionaries
            listings = df.to_dict('records')
            
            # Convert NaN values to None
            for listing in listings:
                for key, value in listing.items():
                    if pd.isna(value):
                        listing[key] = None
            
            result = self.save_listings(listings)
            
            logger.info(f"Imported {result['saved']} listings from {filepath}")
            return result
            
        except Exception as e:
            logger.error(f"Error importing from CSV: {e}")
            return {'saved': 0, 'updated': 0, 'errors': [str(e)]}

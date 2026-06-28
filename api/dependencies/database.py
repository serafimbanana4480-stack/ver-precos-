"""
Database dependencies for API.
"""
from typing import Generator
import logging

from ingestion.storage.database_storage import DatabaseStorage

logger = logging.getLogger(__name__)

# Global database instance
db_storage = None


def get_database() -> DatabaseStorage:
    """Get database storage instance."""
    
    global db_storage
    
    if db_storage is None:
        db_storage = DatabaseStorage()
        logger.info("Database storage initialized")
    
    return db_storage


def get_db_session() -> Generator[DatabaseStorage, None, None]:
    """Get database session (for dependency injection)."""
    
    db = get_database()
    
    try:
        yield db
    finally:
        # Cleanup if needed
        pass


async def get_async_database() -> DatabaseStorage:
    """Get async database storage instance."""
    
    db = get_database()
    
    if not db.async_connection:
        await db.initialize_async()
    
    return db


async def get_async_db_session() -> Generator[DatabaseStorage, None, None]:
    """Get async database session."""
    
    db = await get_async_database()
    
    try:
        yield db
    finally:
        # Cleanup if needed
        pass


def get_database_connection():
    """Get database connection."""
    
    db = get_database()
    
    if not db.connection:
        db._initialize_database()
    
    return db.connection


def get_async_database_connection():
    """Get async database connection."""
    
    import asyncio
    
    async def _get_connection():
        db = await get_async_database()
        return db.async_connection
    
    return _get_connection()


def close_database():
    """Close database connection."""
    
    global db_storage
    
    if db_storage:
        db_storage.close()
        db_storage = None
        logger.info("Database connection closed")


async def close_async_database():
    """Close async database connection."""
    
    global db_storage
    
    if db_storage and db_storage.async_connection:
        await db_storage.close_async()
        logger.info("Async database connection closed")


def check_database_health() -> dict:
    """Check database health."""
    
    try:
        db = get_database()
        
        # Try to execute a simple query
        cursor = db.connection.cursor()
        cursor.execute("SELECT 1")
        cursor.fetchone()
        
        return {
            "status": "healthy",
            "connection": "active",
            "database_path": str(db.db_path)
        }
        
    except Exception as e:
        logger.error(f"Database health check failed: {e}")
        return {
            "status": "unhealthy",
            "error": str(e),
            "connection": "inactive"
        }


async def check_async_database_health() -> dict:
    """Check async database health."""
    
    try:
        db = await get_async_database()
        
        # Try to execute a simple query
        cursor = await db.async_connection.execute("SELECT 1")
        await cursor.fetchone()
        
        return {
            "status": "healthy",
            "connection": "active",
            "database_path": str(db.db_path)
        }
        
    except Exception as e:
        logger.error(f"Async database health check failed: {e}")
        return {
            "status": "unhealthy",
            "error": str(e),
            "connection": "inactive"
        }


def get_database_stats() -> dict:
    """Get database statistics."""
    
    try:
        db = get_database()
        return db.get_statistics()
        
    except Exception as e:
        logger.error(f"Error getting database stats: {e}")
        return {"error": str(e)}


def cleanup_old_database_data(days: int = 90) -> int:
    """Clean up old database data."""
    
    try:
        db = get_database()
        return db.cleanup_old_listings(days)
        
    except Exception as e:
        logger.error(f"Error cleaning up database data: {e}")
        return 0


def backup_database(backup_path: str) -> bool:
    """Backup database to file."""
    
    try:
        db = get_database()
        
        # Export to CSV as backup
        return db.export_to_csv(backup_path)
        
    except Exception as e:
        logger.error(f"Error backing up database: {e}")
        return False


def restore_database(backup_path: str) -> dict:
    """Restore database from backup."""
    
    try:
        db = get_database()
        return db.import_from_csv(backup_path)
        
    except Exception as e:
        logger.error(f"Error restoring database: {e}")
        return {"saved": 0, "updated": 0, "errors": [str(e)]}


def validate_database_schema() -> dict:
    """Validate database schema."""
    
    try:
        db = get_database()
        
        # Check if tables exist
        cursor = db.connection.cursor()
        
        required_tables = ['listings', 'search_history', 'data_quality']
        existing_tables = []
        
        for table in required_tables:
            cursor.execute("SELECT name FROM sqlite_master WHERE type='table' AND name=?", (table,))
            if cursor.fetchone():
                existing_tables.append(table)
        
        missing_tables = set(required_tables) - set(existing_tables)
        
        return {
            "status": "valid" if not missing_tables else "invalid",
            "existing_tables": existing_tables,
            "missing_tables": list(missing_tables)
        }
        
    except Exception as e:
        logger.error(f"Error validating database schema: {e}")
        return {"status": "error", "error": str(e)}


def migrate_database() -> bool:
    """Run database migrations."""
    
    try:
        db = get_database()
        
        # Create tables if they don't exist
        db._create_tables()
        
        logger.info("Database migration completed")
        return True
        
    except Exception as e:
        logger.error(f"Error running database migration: {e}")
        return False


def reset_database() -> bool:
    """Reset database (dangerous operation)."""
    
    try:
        db = get_database()
        
        # Close current connection
        db.close()
        
        # Remove database file
        import os
        if os.path.exists(db.db_path):
            os.remove(db.db_path)
        
        # Reinitialize
        db._initialize_database()
        
        logger.warning("Database reset completed")
        return True
        
    except Exception as e:
        logger.error(f"Error resetting database: {e}")
        return False


def optimize_database() -> bool:
    """Optimize database performance."""
    
    try:
        db = get_database()
        
        # Run VACUUM to optimize SQLite database
        cursor = db.connection.cursor()
        cursor.execute("VACUUM")
        
        # Run ANALYZE to update statistics
        cursor.execute("ANALYZE")
        
        db.connection.commit()
        
        logger.info("Database optimization completed")
        return True
        
    except Exception as e:
        logger.error(f"Error optimizing database: {e}")
        return False


def get_database_size() -> dict:
    """Get database size information."""
    
    try:
        db = get_database()
        
        import os
        if os.path.exists(db.db_path):
            size_bytes = os.path.getsize(db.db_path)
            size_mb = size_bytes / (1024 * 1024)
            
            return {
                "size_bytes": size_bytes,
                "size_mb": size_mb,
                "file_path": str(db.db_path)
            }
        else:
            return {"size_bytes": 0, "size_mb": 0, "file_path": str(db.db_path)}
            
    except Exception as e:
        logger.error(f"Error getting database size: {e}")
        return {"error": str(e)}


def check_database_integrity() -> dict:
    """Check database integrity."""
    
    try:
        db = get_database()
        
        cursor = db.connection.cursor()
        cursor.execute("PRAGMA integrity_check")
        result = cursor.fetchone()
        
        return {
            "status": "ok" if result[0] == "ok" else "error",
            "result": result[0]
        }
        
    except Exception as e:
        logger.error(f"Error checking database integrity: {e}")
        return {"status": "error", "error": str(e)}


def get_database_info() -> dict:
    """Get comprehensive database information."""
    
    try:
        db = get_database()
        cursor = db.connection.cursor()
        
        # Get SQLite version
        cursor.execute("SELECT sqlite_version()")
        sqlite_version = cursor.fetchone()[0]
        
        # Get page size
        cursor.execute("PRAGMA page_size")
        page_size = cursor.fetchone()[0]
        
        # Get page count
        cursor.execute("PRAGMA page_count")
        page_count = cursor.fetchone()[0]
        
        # Get journal mode
        cursor.execute("PRAGMA journal_mode")
        journal_mode = cursor.fetchone()[0]
        
        # Get foreign key setting
        cursor.execute("PRAGMA foreign_keys")
        foreign_keys = cursor.fetchone()[0]
        
        return {
            "sqlite_version": sqlite_version,
            "page_size": page_size,
            "page_count": page_count,
            "journal_mode": journal_mode,
            "foreign_keys": bool(foreign_keys),
            "database_path": str(db.db_path),
            "size_info": get_database_size(),
            "health": check_database_health(),
            "schema": validate_database_schema()
        }
        
    except Exception as e:
        logger.error(f"Error getting database info: {e}")
        return {"error": str(e)}


def setup_database_connection_pool(pool_size: int = 5):
    """Setup database connection pool (placeholder for future implementation)."""
    
    logger.info(f"Database connection pool setup requested with size {pool_size}")
    # SQLite doesn't need connection pooling like other databases
    # This would be relevant for PostgreSQL, MySQL, etc.


def get_connection_pool_stats() -> dict:
    """Get connection pool statistics."""
    
    return {
        "pool_size": 1,  # SQLite uses single connection
        "active_connections": 1,
        "idle_connections": 0,
        "total_requests": 0
    }


def close_all_connections():
    """Close all database connections."""
    
    close_database()
    logger.info("All database connections closed")


def warm_up_database():
    """Warm up database with common queries."""
    
    try:
        db = get_database()
        
        # Execute common queries to warm up cache
        common_queries = [
            "SELECT COUNT(*) FROM listings",
            "SELECT DISTINCT make FROM listings LIMIT 10",
            "SELECT AVG(price) FROM listings",
            "SELECT source, COUNT(*) FROM listings GROUP BY source"
        ]
        
        cursor = db.connection.cursor()
        
        for query in common_queries:
            try:
                cursor.execute(query)
                cursor.fetchone()
            except Exception as e:
                logger.warning(f"Warm-up query failed: {query} - {e}")
        
        logger.info("Database warm-up completed")
        
    except Exception as e:
        logger.error(f"Error warming up database: {e}")


def get_database_performance_metrics() -> dict:
    """Get database performance metrics."""
    
    try:
        db = get_database()
        cursor = db.connection.cursor()
        
        # Get database performance stats
        cursor.execute("PRAGMA cache_size")
        cache_size = cursor.fetchone()[0]
        
        cursor.execute("PRAGMA temp_store")
        temp_store = cursor.fetchone()[0]
        
        return {
            "cache_size": cache_size,
            "temp_store": temp_store,
            "optimization_status": "optimized" if optimize_database() else "not_optimized",
            "integrity_check": check_database_integrity(),
            "size_info": get_database_size()
        }
        
    except Exception as e:
        logger.error(f"Error getting database performance metrics: {e}")
        return {"error": str(e)}


def configure_database_settings(settings: dict) -> bool:
    """Configure database settings."""
    
    try:
        db = get_database()
        cursor = db.connection.cursor()
        
        # Apply settings (parameterized PRAGMA to prevent SQL injection)
        pragma_map = {
            "cache_size": "cache_size",
            "temp_store": "temp_store",
            "journal_mode": "journal_mode",
            "synchronous": "synchronous",
        }
        for key, pragma in pragma_map.items():
            if key in settings:
                value = settings[key]
                if isinstance(value, str):
                    cursor.execute(f"PRAGMA {pragma} = ?", (value,))
                else:
                    cursor.execute(f"PRAGMA {pragma} = ?", (int(value),))
        
        db.connection.commit()
        
        logger.info("Database settings configured")
        return True
        
    except Exception as e:
        logger.error(f"Error configuring database settings: {e}")
        return False

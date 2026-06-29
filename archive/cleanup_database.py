"""
Database Cleanup Script
Remove test data, fake entries, and duplicates from database
"""
import sqlite3
import logging
from pathlib import Path

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


def cleanup_database(db_path: str = "d:/VER PRECOS/autodeal.db"):
    """Remove test data and fake entries from database"""
    print("\n" + "="*60)
    print("DATABASE CLEANUP")
    print("="*60)
    
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()
    
    try:
        # Remove test/QA vehicles
        cursor.execute("""
            DELETE FROM vehicles 
            WHERE source_id LIKE '%test%' 
               OR source_id LIKE '%qa%'
               OR source_id LIKE '%sample%'
               OR source_id LIKE '%demo%'
        """)
        test_deleted = cursor.rowcount
        print(f"Deleted {test_deleted} test/QA vehicles")
        
        # Remove vehicles with placeholder titles
        cursor.execute("""
            DELETE FROM vehicles 
            WHERE title LIKE '%test%' 
               OR title LIKE '%placeholder%' 
               OR title LIKE '%sample%'
               OR title LIKE '%demo%'
        """)
        placeholder_deleted = cursor.rowcount
        print(f"Deleted {placeholder_deleted} vehicles with placeholder titles")
        
        # Remove duplicate descriptions (keep the most recent one)
        cursor.execute("""
            DELETE FROM vehicles 
            WHERE rowid NOT IN (
                SELECT MAX(rowid) 
                FROM vehicles 
                WHERE description IS NOT NULL AND length(description) > 50
                GROUP BY description
            )
            AND description IS NOT NULL 
            AND length(description) > 50
        """)
        duplicate_deleted = cursor.rowcount
        print(f"Deleted {duplicate_deleted} vehicles with duplicate descriptions")
        
        conn.commit()
        
        # Verify cleanup
        cursor.execute("SELECT COUNT(*) FROM vehicles")
        total_remaining = cursor.fetchone()[0]
        print(f"\nTotal vehicles remaining: {total_remaining}")
        
        # Check for remaining test data
        cursor.execute("""
            SELECT COUNT(*) FROM vehicles 
            WHERE source_id LIKE '%test%' 
               OR source_id LIKE '%qa%'
        """)
        remaining_test = cursor.fetchone()[0]
        if remaining_test > 0:
            print(f"WARNING: {remaining_test} test vehicles still remain")
        else:
            print("All test vehicles removed")
        
        return True
        
    except Exception as e:
        logger.error(f"Database cleanup failed: {e}")
        conn.rollback()
        return False
    finally:
        conn.close()


if __name__ == "__main__":
    success = cleanup_database()
    if success:
        print("\nDatabase cleanup completed successfully")
    else:
        print("\nDatabase cleanup failed")

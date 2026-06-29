"""
Database Migration Script
Add new columns for AI enrichment and multi-dimensional scoring
"""
import sqlite3
import logging
from pathlib import Path

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


def migrate_database(db_path: str = "d:/VER PRECOS/autodeal.db"):
    """
    Add new columns to the vehicles table for AI enrichment and scoring
    """
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()
    
    # New columns to add
    new_columns = [
        # AI analysis fields
        ("ai_risk_score", "REAL"),
        ("ai_recommendation", "VARCHAR(20)"),
        ("vision_confidence", "REAL"),
        ("llm_confidence", "REAL"),
        
        # Scoring components
        ("market_deviation_score", "REAL"),
        ("ai_risk_score_component", "REAL"),
        ("vision_damage_score", "REAL"),
        ("price_anomaly_score", "REAL"),
        ("demand_signal_score", "REAL"),
        
        # Score interpretation
        ("score_interpretation", "VARCHAR(50)"),
        ("recommended_action", "VARCHAR(50)"),
        
        # Damage detection (rename from damages_detected)
        ("detected_damages", "TEXT"),
        ("has_accident_indicators", "BOOLEAN"),
    ]
    
    try:
        # Check if table exists
        cursor.execute("""
            SELECT name FROM sqlite_master 
            WHERE type='table' AND name='vehicles'
        """)
        
        if not cursor.fetchone():
            logger.error("Vehicles table does not exist")
            return False
        
        # Get existing columns
        cursor.execute("PRAGMA table_info(vehicles)")
        existing_columns = {row[1] for row in cursor.fetchall()}
        
        # Add new columns
        added_count = 0
        for column_name, column_type in new_columns:
            if column_name not in existing_columns:
                try:
                    cursor.execute(f"""
                        ALTER TABLE vehicles 
                        ADD COLUMN {column_name} {column_type}
                    """)
                    logger.info(f"Added column: {column_name}")
                    added_count += 1
                except Exception as e:
                    logger.warning(f"Failed to add column {column_name}: {e}")
            else:
                logger.info(f"Column {column_name} already exists")
        
        conn.commit()
        logger.info(f"Migration completed: {added_count} columns added")
        return True
        
    except Exception as e:
        logger.error(f"Migration failed: {e}")
        conn.rollback()
        return False
    finally:
        conn.close()


if __name__ == "__main__":
    success = migrate_database()
    if success:
        print("✓ Database migration successful")
    else:
        print("✗ Database migration failed")

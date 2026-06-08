"""
Schema evolution and migration management
Based on Obsidian Vault documentation for schema evolution
"""
import logging
from typing import List, Dict, Any, Optional
from datetime import datetime
from sqlalchemy import text, inspect
from database.db import engine
from database.models import Base

logger = logging.getLogger(__name__)


class SchemaEvolution:
    """Manage schema evolution and migrations"""
    
    def __init__(self, engine):
        self.engine = engine
        self.inspector = inspect(engine)
    
    def get_current_schema_version(self) -> str:
        """Get current schema version from database"""
        try:
            with self.engine.connect() as conn:
                result = conn.execute(text("SELECT version FROM schema_version ORDER BY applied_at DESC LIMIT 1"))
                version = result.fetchone()
                return version[0] if version else "0.0.0"
        except Exception as e:
            logger.warning(f"Could not get schema version: {e}")
            return "0.0.0"
    
    def create_version_table(self):
        """Create schema version table if it doesn't exist"""
        try:
            with self.engine.connect() as conn:
                conn.execute(text("""
                    CREATE TABLE IF NOT EXISTS schema_version (
                        id SERIAL PRIMARY KEY,
                        version VARCHAR(20) NOT NULL,
                        description TEXT,
                        applied_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                        rollback_script TEXT
                    )
                """))
                conn.commit()
                logger.info("Schema version table created")
        except Exception as e:
            logger.error(f"Error creating version table: {e}")
            raise
    
    def apply_migration(
        self,
        version: str,
        description: str,
        migration_sql: str,
        rollback_sql: Optional[str] = None
    ) -> bool:
        """
        Apply a schema migration
        
        Args:
            version: Version string (e.g., "1.0.0")
            description: Migration description
            migration_sql: SQL to execute
            rollback_sql: Optional SQL for rollback
            
        Returns:
            True if successful
        """
        try:
            with self.engine.connect() as conn:
                # Check if already applied
                result = conn.execute(
                    text("SELECT COUNT(*) FROM schema_version WHERE version = :version"),
                    {"version": version}
                )
                if result.fetchone()[0] > 0:
                    logger.info(f"Migration {version} already applied")
                    return True
                
                # Execute migration
                logger.info(f"Applying migration {version}: {description}")
                conn.execute(text(migration_sql))
                
                # Record migration
                conn.execute(text("""
                    INSERT INTO schema_version (version, description, rollback_script)
                    VALUES (:version, :description, :rollback_script)
                """), {
                    "version": version,
                    "description": description,
                    "rollback_script": rollback_sql or ""
                })
                
                conn.commit()
                logger.info(f"Migration {version} applied successfully")
                return True
                
        except Exception as e:
            logger.error(f"Error applying migration {version}: {e}")
            return False
    
    def rollback_migration(self, version: str) -> bool:
        """
        Rollback a migration using stored rollback script
        
        Args:
            version: Version to rollback
            
        Returns:
            True if successful
        """
        try:
            with self.engine.connect() as conn:
                # Get rollback script
                result = conn.execute(
                    text("SELECT rollback_script FROM schema_version WHERE version = :version"),
                    {"version": version}
                )
                row = result.fetchone()
                
                if not row or not row[0]:
                    logger.error(f"No rollback script for version {version}")
                    return False
                
                # Execute rollback
                logger.info(f"Rolling back migration {version}")
                conn.execute(text(row[0]))
                
                # Remove version record
                conn.execute(
                    text("DELETE FROM schema_version WHERE version = :version"),
                    {"version": version}
                )
                
                conn.commit()
                logger.info(f"Migration {version} rolled back successfully")
                return True
                
        except Exception as e:
            logger.error(f"Error rolling back migration {version}: {e}")
            return False
    
    def get_pending_migrations(self, migrations: List[Dict[str, str]]) -> List[Dict[str, str]]:
        """
        Get migrations that haven't been applied yet
        
        Args:
            migrations: List of migration dictionaries
            
        Returns:
            List of pending migrations
        """
        current_version = self.get_current_schema_version()
        pending = []
        
        for migration in migrations:
            if migration['version'] > current_version:
                pending.append(migration)
        
        return pending
    
    def validate_schema(self) -> Dict[str, Any]:
        """
        Validate current schema against expected models
        
        Returns:
            Validation report
        """
        report = {
            'valid': True,
            'tables': {},
            'columns': {},
            'indexes': {},
            'issues': []
        }
        
        try:
            # Check all expected tables exist
            expected_tables = Base.metadata.tables.keys()
            existing_tables = self.inspector.get_table_names()
            
            for table in expected_tables:
                if table not in existing_tables:
                    report['valid'] = False
                    report['issues'].append(f"Missing table: {table}")
                    report['tables'][table] = 'missing'
                else:
                    report['tables'][table] = 'exists'
                    
                    # Check columns
                    expected_columns = Base.metadata.tables[table].columns.keys()
                    existing_columns = [col['name'] for col in self.inspector.get_columns(table)]
                    
                    for col in expected_columns:
                        if col not in existing_columns:
                            report['valid'] = False
                            report['issues'].append(f"Missing column {table}.{col}")
                            report['columns'][f"{table}.{col}"] = 'missing'
                        else:
                            report['columns'][f"{table}.{col}"] = 'exists'
            
            logger.info(f"Schema validation: {'VALID' if report['valid'] else 'INVALID'}")
            
        except Exception as e:
            logger.error(f"Error validating schema: {e}")
            report['valid'] = False
            report['issues'].append(f"Validation error: {e}")
        
        return report


# Predefined migrations
MIGRATIONS = [
    {
        'version': '1.0.0',
        'description': 'Initial schema creation',
        'migration_sql': """
            -- Tables are created by SQLAlchemy Base.metadata.create_all()
            -- This is a placeholder for the initial migration
        """,
        'rollback_sql': """
            DROP TABLE IF EXISTS ai_reviews CASCADE;
            DROP TABLE IF EXISTS price_history CASCADE;
            DROP TABLE IF EXISTS scraping_logs CASCADE;
            DROP TABLE IF EXISTS watchlist CASCADE;
            DROP TABLE IF EXISTS vehicles CASCADE;
        """
    },
    {
        'version': '1.1.0',
        'description': 'Add vision analysis fields',
        'migration_sql': """
            ALTER TABLE vehicles 
            ADD COLUMN IF NOT EXISTS vision_confidence FLOAT,
            ADD COLUMN IF NOT EXISTS llm_confidence FLOAT,
            ADD COLUMN IF NOT EXISTS ai_risk_score_component FLOAT,
            ADD COLUMN IF NOT EXISTS vision_damage_score FLOAT;
        """,
        'rollback_sql': """
            ALTER TABLE vehicles 
            DROP COLUMN IF EXISTS vision_confidence,
            DROP COLUMN IF EXISTS llm_confidence,
            DROP COLUMN IF EXISTS ai_risk_score_component,
            DROP COLUMN IF EXISTS vision_damage_score;
        """
    },
    {
        'version': '1.2.0',
        'description': 'Add scoring interpretation fields',
        'migration_sql': """
            ALTER TABLE vehicles 
            ADD COLUMN IF NOT EXISTS score_interpretation VARCHAR(50),
            ADD COLUMN IF NOT EXISTS recommended_action VARCHAR(50),
            ADD COLUMN IF NOT EXISTS price_anomaly_score FLOAT,
            ADD COLUMN IF NOT EXISTS demand_signal_score FLOAT;
        """,
        'rollback_sql': """
            ALTER TABLE vehicles 
            DROP COLUMN IF EXISTS score_interpretation,
            DROP COLUMN IF EXISTS recommended_action,
            DROP COLUMN IF EXISTS price_anomaly_score,
            DROP COLUMN IF EXISTS demand_signal_score;
        """
    }
]


def migrate_to_latest():
    """Apply all pending migrations"""
    evolution = SchemaEvolution(engine)
    evolution.create_version_table()
    
    pending = evolution.get_pending_migrations(MIGRATIONS)
    
    if not pending:
        logger.info("No pending migrations")
        return
    
    logger.info(f"Found {len(pending)} pending migrations")
    
    for migration in pending:
        success = evolution.apply_migration(
            version=migration['version'],
            description=migration['description'],
            migration_sql=migration['migration_sql'],
            rollback_sql=migration.get('rollback_sql')
        )
        
        if not success:
            logger.error(f"Failed to apply migration {migration['version']}")
            break


if __name__ == "__main__":
    # Test schema evolution
    evolution = SchemaEvolution(engine)
    evolution.create_version_table()
    
    current_version = evolution.get_current_schema_version()
    print(f"Current schema version: {current_version}")
    
    # Validate schema
    report = evolution.validate_schema()
    print(f"Schema validation: {report}")

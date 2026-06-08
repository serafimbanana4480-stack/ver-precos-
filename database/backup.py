"""
Database backup procedures
Based on Obsidian Vault documentation for backup procedures
"""
import logging
import subprocess
import os
from datetime import datetime
from typing import Optional
from pathlib import Path
from config import settings

logger = logging.getLogger(__name__)


class DatabaseBackup:
    """Handle database backup operations"""
    
    def __init__(self, database_url: str, backup_dir: str = "backups"):
        self.database_url = database_url
        self.backup_dir = Path(backup_dir)
        self.backup_dir.mkdir(exist_ok=True)
    
    def parse_database_url(self) -> dict:
        """Parse database URL into components"""
        # Format: postgresql://user:password@host:port/database
        if self.database_url.startswith("sqlite"):
            return {
                'type': 'sqlite',
                'path': self.database_url.replace("sqlite:///", "")
            }
        
        # PostgreSQL parsing
        url = self.database_url.replace("postgresql://", "")
        if "@" in url:
            auth, host_port_db = url.split("@")
            user, password = auth.split(":")
            host_port, database = host_port_db.split("/")
            if ":" in host_port:
                host, port = host_port.split(":")
            else:
                host = host_port
                port = "5432"
        else:
            raise ValueError("Invalid database URL format")
        
        return {
            'type': 'postgresql',
            'user': user,
            'password': password,
            'host': host,
            'port': port,
            'database': database
        }
    
    def create_backup(
        self,
        backup_type: str = "full",
        compression: bool = True
    ) -> Optional[str]:
        """
        Create a database backup
        
        Args:
            backup_type: Type of backup ('full', 'schema_only', 'data_only')
            compression: Whether to compress the backup
            
        Returns:
            Path to backup file or None if failed
        """
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        db_info = self.parse_database_url()
        
        if db_info['type'] == 'sqlite':
            return self._backup_sqlite(db_info, timestamp, compression)
        elif db_info['type'] == 'postgresql':
            return self._backup_postgresql(db_info, timestamp, backup_type, compression)
        else:
            logger.error(f"Unsupported database type: {db_info['type']}")
            return None
    
    def _backup_sqlite(self, db_info: dict, timestamp: str, compression: bool) -> Optional[str]:
        """Backup SQLite database"""
        try:
            source_path = Path(db_info['path'])
            backup_name = f"sqlite_backup_{timestamp}.db"
            backup_path = self.backup_dir / backup_name
            
            # Copy database file
            import shutil
            shutil.copy2(source_path, backup_path)
            
            if compression:
                import gzip
                compressed_path = backup_path.with_suffix('.db.gz')
                with open(backup_path, 'rb') as f_in:
                    with gzip.open(compressed_path, 'wb') as f_out:
                        shutil.copyfileobj(f_in, f_out)
                backup_path.unlink()
                backup_path = compressed_path
            
            logger.info(f"SQLite backup created: {backup_path}")
            return str(backup_path)
            
        except Exception as e:
            logger.error(f"SQLite backup failed: {e}")
            return None
    
    def _backup_postgresql(
        self,
        db_info: dict,
        timestamp: str,
        backup_type: str,
        compression: bool
    ) -> Optional[str]:
        """Backup PostgreSQL database using pg_dump"""
        try:
            backup_name = f"pg_backup_{timestamp}.sql"
            backup_path = self.backup_dir / backup_name
            
            # Build pg_dump command
            cmd = [
                'pg_dump',
                f"--host={db_info['host']}",
                f"--port={db_info['port']}",
                f"--user={db_info['user']}",
                f"--dbname={db_info['database']}"
            ]
            
            if backup_type == 'schema_only':
                cmd.append('--schema-only')
            elif backup_type == 'data_only':
                cmd.append('--data-only')
            
            if compression:
                cmd.append('--compress=9')
            
            # Set environment variable for password
            env = os.environ.copy()
            env['PGPASSWORD'] = db_info['password']
            
            # Execute pg_dump
            with open(backup_path, 'w') as f:
                result = subprocess.run(
                    cmd,
                    env=env,
                    stdout=f,
                    stderr=subprocess.PIPE,
                    text=True
                )
            
            if result.returncode != 0:
                logger.error(f"pg_dump failed: {result.stderr}")
                backup_path.unlink()
                return None
            
            logger.info(f"PostgreSQL backup created: {backup_path}")
            return str(backup_path)
            
        except Exception as e:
            logger.error(f"PostgreSQL backup failed: {e}")
            return None
    
    def restore_backup(self, backup_path: str) -> bool:
        """
        Restore database from backup
        
        Args:
            backup_path: Path to backup file
            
        Returns:
            True if successful
        """
        try:
            backup_file = Path(backup_path)
            db_info = self.parse_database_url()
            
            if db_info['type'] == 'sqlite':
                return self._restore_sqlite(backup_file, db_info)
            elif db_info['type'] == 'postgresql':
                return self._restore_postgresql(backup_file, db_info)
            else:
                logger.error(f"Unsupported database type: {db_info['type']}")
                return False
                
        except Exception as e:
            logger.error(f"Restore failed: {e}")
            return False
    
    def _restore_sqlite(self, backup_file: Path, db_info: dict) -> bool:
        """Restore SQLite database"""
        try:
            import shutil
            import gzip
            
            # Decompress if needed
            if backup_file.suffix == '.gz':
                decompressed_path = backup_file.with_suffix('.db')
                with gzip.open(backup_file, 'rb') as f_in:
                    with open(decompressed_path, 'wb') as f_out:
                        shutil.copyfileobj(f_in, f_out)
                backup_file = decompressed_path
            
            # Copy to database location
            target_path = Path(db_info['path'])
            shutil.copy2(backup_file, target_path)
            
            logger.info(f"SQLite restore completed")
            return True
            
        except Exception as e:
            logger.error(f"SQLite restore failed: {e}")
            return False
    
    def _restore_postgresql(self, backup_file: Path, db_info: dict) -> bool:
        """Restore PostgreSQL database using psql"""
        try:
            cmd = [
                'psql',
                f"--host={db_info['host']}",
                f"--port={db_info['port']}",
                f"--user={db_info['user']}",
                f"--dbname={db_info['database']}",
                f"--file={backup_file}"
            ]
            
            env = os.environ.copy()
            env['PGPASSWORD'] = db_info['password']
            
            result = subprocess.run(cmd, env=env, capture_output=True, text=True)
            
            if result.returncode != 0:
                logger.error(f"psql restore failed: {result.stderr}")
                return False
            
            logger.info(f"PostgreSQL restore completed")
            return True
            
        except Exception as e:
            logger.error(f"PostgreSQL restore failed: {e}")
            return False
    
    def list_backups(self) -> list:
        """List all available backups"""
        backups = []
        
        for file in self.backup_dir.iterdir():
            if file.is_file() and (file.suffix in ['.db', '.sql', '.gz']):
                stat = file.stat()
                backups.append({
                    'name': file.name,
                    'path': str(file),
                    'size': stat.st_size,
                    'created': datetime.fromtimestamp(stat.st_ctime)
                })
        
        return sorted(backups, key=lambda x: x['created'], reverse=True)
    
    def cleanup_old_backups(self, keep_count: int = 10):
        """Remove old backups, keeping only the most recent ones"""
        backups = self.list_backups()
        
        if len(backups) > keep_count:
            for backup in backups[keep_count:]:
                try:
                    Path(backup['path']).unlink()
                    logger.info(f"Deleted old backup: {backup['name']}")
                except Exception as e:
                    logger.error(f"Failed to delete backup {backup['name']}: {e}")


if __name__ == "__main__":
    # Test backup
    backup = DatabaseBackup(settings.database_url)
    
    # Create backup
    backup_path = backup.create_backup()
    print(f"Backup created: {backup_path}")
    
    # List backups
    backups = backup.list_backups()
    print(f"Available backups: {len(backups)}")

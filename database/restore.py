"""
Database restore procedures
Based on Obsidian Vault documentation for restore procedures
"""
import logging
from typing import Optional
from database.backup import DatabaseBackup

logger = logging.getLogger(__name__)


class DatabaseRestore:
    """Handle database restore operations with safety checks"""
    
    def __init__(self, database_url: str, backup_dir: str = "backups"):
        self.backup = DatabaseBackup(database_url, backup_dir)
    
    def validate_backup(self, backup_path: str) -> dict:
        """
        Validate backup file before restore
        
        Args:
            backup_path: Path to backup file
            
        Returns:
            Validation report
        """
        from pathlib import Path
        
        report = {
            'valid': True,
            'errors': [],
            'warnings': []
        }
        
        backup_file = Path(backup_path)
        
        # Check file exists
        if not backup_file.exists():
            report['valid'] = False
            report['errors'].append("Backup file does not exist")
            return report
        
        # Check file size
        if backup_file.stat().st_size == 0:
            report['valid'] = False
            report['errors'].append("Backup file is empty")
            return report
        
        # Check file extension
        valid_extensions = ['.db', '.sql', '.gz']
        if backup_file.suffix not in valid_extensions and backup_file.suffixes[-1] not in valid_extensions:
            report['valid'] = False
            report['errors'].append(f"Invalid file extension: {backup_file.suffix}")
        
        return report
    
    def create_pre_restore_backup(self) -> Optional[str]:
        """
        Create a backup of current database before restore
        
        Returns:
            Path to pre-restore backup or None if failed
        """
        logger.info("Creating pre-restore backup...")
        timestamp = "pre_restore"
        return self.backup.create_backup()
    
    def restore_with_safety(
        self,
        backup_path: str,
        create_pre_backup: bool = True,
        confirm: bool = False
    ) -> dict:
        """
        Restore database with safety checks
        
        Args:
            backup_path: Path to backup file
            create_pre_backup: Whether to backup current database first
            confirm: Confirmation flag (must be True to proceed)
            
        Returns:
            Restore report
        """
        report = {
            'success': False,
            'pre_backup': None,
            'validation': None,
            'restore': None,
            'errors': []
        }
        
        # Safety check
        if not confirm:
            report['errors'].append("Restore not confirmed (confirm=True required)")
            return report
        
        # Validate backup
        validation = self.validate_backup(backup_path)
        report['validation'] = validation
        
        if not validation['valid']:
            report['errors'].extend(validation['errors'])
            return report
        
        # Create pre-restore backup
        if create_pre_backup:
            pre_backup = self.create_pre_restore_backup()
            report['pre_backup'] = pre_backup
            if not pre_backup:
                report['errors'].append("Failed to create pre-restore backup")
                return report
        
        # Perform restore
        logger.info(f"Restoring from backup: {backup_path}")
        success = self.backup.restore_backup(backup_path)
        
        report['restore'] = {
            'backup_path': backup_path,
            'success': success
        }
        
        if success:
            report['success'] = True
            logger.info("Restore completed successfully")
        else:
            report['errors'].append("Restore operation failed")
            logger.error("Restore failed")
        
        return report
    
    def rollback_to_pre_restore(self, pre_backup_path: str) -> bool:
        """
        Rollback to pre-restore backup if restore failed
        
        Args:
            pre_backup_path: Path to pre-restore backup
            
        Returns:
            True if rollback successful
        """
        logger.info(f"Rolling back to pre-restore backup: {pre_backup_path}")
        return self.backup.restore_backup(pre_backup_path)


if __name__ == "__main__":
    # Test restore procedures
    from config import settings
    
    restore = DatabaseRestore(settings.database_url)
    
    # List available backups
    backups = restore.backup.list_backups()
    print(f"Available backups: {len(backups)}")
    
    if backups:
        # Validate latest backup
        validation = restore.validate_backup(backups[0]['path'])
        print(f"Backup validation: {validation}")

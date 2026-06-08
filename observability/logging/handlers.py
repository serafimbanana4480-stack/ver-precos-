"""
Handlers for logging.
"""
import logging
from logging.handlers import RotatingFileHandler
from pathlib import Path
from typing import Optional


class FileHandler:
    """File handler for logging."""
    
    def __init__(self, file_path: str, max_bytes: int = 10485760, backup_count: int = 5):
        self.file_path = Path(file_path)
        self.file_path.parent.mkdir(parents=True, exist_ok=True)
        self.handler = RotatingFileHandler(
            file_path,
            maxBytes=max_bytes,
            backupCount=backup_count,
        )
    
    def get_handler(self) -> logging.Handler:
        """Get logging handler."""
        return self.handler


class ConsoleHandler:
    """Console handler for logging."""
    
    def __init__(self):
        self.handler = logging.StreamHandler()
    
    def get_handler(self) -> logging.Handler:
        """Get logging handler."""
        return self.handler

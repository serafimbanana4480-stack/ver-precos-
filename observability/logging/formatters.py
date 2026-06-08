"""
Formatters for logging.
"""
import logging
import json
from datetime import datetime


class JSONFormatter(logging.Formatter):
    """JSON formatter for structured logging."""
    
    def format(self, record: logging.LogRecord) -> str:
        """Format log record as JSON."""
        log_data = {
            "timestamp": datetime.utcnow().isoformat(),
            "level": record.levelname,
            "logger": record.name,
            "message": record.getMessage(),
            "module": record.module,
            "function": record.funcName,
            "line": record.lineno,
        }
        
        if hasattr(record, "extra"):
            log_data.update(record.extra)
        
        return json.dumps(log_data)


class TextFormatter(logging.Formatter):
    """Text formatter for human-readable logging."""
    
    def format(self, record: logging.LogRecord) -> str:
        """Format log record as text."""
        timestamp = datetime.utcnow().strftime("%Y-%m-%d %H:%M:%S")
        return f"[{timestamp}] [{record.levelname}] [{record.name}] {record.getMessage()}"

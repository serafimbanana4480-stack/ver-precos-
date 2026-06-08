"""
Structured Logging System
Production-grade structured logging with JSON format
"""
from __future__ import annotations
import logging
import json
import sys
from datetime import datetime
from typing import Any, Dict, Optional
from pathlib import Path
import traceback


class StructuredFormatter(logging.Formatter):
    """
    Custom formatter that outputs logs as JSON
    """
    
    def format(self, record: logging.LogRecord) -> str:
        """
        Format log record as JSON
        """
        log_entry = {
            "timestamp": datetime.utcnow().isoformat(),
            "level": record.levelname,
            "logger": record.name,
            "message": record.getMessage(),
            "module": record.module,
            "function": record.funcName,
            "line": record.lineno,
        }
        
        # Add exception info if present
        if record.exc_info:
            log_entry["exception"] = {
                "type": record.exc_info[0].__name__,
                "message": str(record.exc_info[1]),
                "traceback": traceback.format_exception(*record.exc_info)
            }
        
        # Add extra fields if present
        for key, value in record.__dict__.items():
            if key not in ['name', 'msg', 'args', 'created', 'filename', 'funcName', 
                          'levelname', 'levelno', 'lineno', 'module', 'msecs', 
                          'message', 'pathname', 'process', 'processName', 'relativeCreated', 
                          'thread', 'threadName', 'exc_info', 'exc_text', 'stack_info']:
                log_entry[key] = value
        
        return json.dumps(log_entry)


class TextFormatter(logging.Formatter):
    """
    Custom formatter for human-readable text logs
    """
    
    def format(self, record: logging.LogRecord) -> str:
        """
        Format log record as text
        """
        timestamp = datetime.utcnow().isoformat()
        level = record.levelname.ljust(8)
        logger_name = record.name.ljust(30)
        message = record.getMessage()
        
        log_line = f"{timestamp} | {level} | {logger_name} | {message}"
        
        if record.exc_info:
            log_line += "\n" + "".join(traceback.format_exception(*record.exc_info))
        
        return log_line


class StructuredLogger:
    """
    Structured logger with both JSON and text output
    """
    
    def __init__(
        self,
        name: str,
        log_level: str = "INFO",
        log_format: str = "json",
        log_file: Optional[str] = None,
        console_output: bool = True
    ):
        self.logger = logging.getLogger(name)
        self.logger.setLevel(getattr(logging, log_level.upper()))
        
        # Clear existing handlers
        self.logger.handlers.clear()
        
        # Console handler
        if console_output:
            console_handler = logging.StreamHandler(sys.stdout)
            if log_format == "json":
                console_handler.setFormatter(StructuredFormatter())
            else:
                console_handler.setFormatter(TextFormatter())
            self.logger.addHandler(console_handler)
        
        # File handler
        if log_file:
            log_path = Path(log_file)
            log_path.parent.mkdir(parents=True, exist_ok=True)
            
            file_handler = logging.FileHandler(log_file)
            if log_format == "json":
                file_handler.setFormatter(StructuredFormatter())
            else:
                file_handler.setFormatter(TextFormatter())
            self.logger.addHandler(file_handler)
    
    def debug(self, message: str, **kwargs):
        """Log debug message"""
        self.logger.debug(message, extra=kwargs)
    
    def info(self, message: str, **kwargs):
        """Log info message"""
        self.logger.info(message, extra=kwargs)
    
    def warning(self, message: str, **kwargs):
        """Log warning message"""
        self.logger.warning(message, extra=kwargs)
    
    def error(self, message: str, **kwargs):
        """Log error message"""
        self.logger.error(message, extra=kwargs)
    
    def critical(self, message: str, **kwargs):
        """Log critical message"""
        self.logger.critical(message, extra=kwargs)
    
    def exception(self, message: str, **kwargs):
        """Log exception with traceback"""
        self.logger.exception(message, extra=kwargs)


def get_logger(
    name: str,
    log_level: str = "INFO",
    log_format: str = "json",
    log_file: Optional[str] = None,
    console_output: bool = True
) -> StructuredLogger:
    """
    Get a structured logger instance
    
    Args:
        name: Logger name
        log_level: Logging level (DEBUG, INFO, WARNING, ERROR, CRITICAL)
        log_format: Log format (json, text)
        log_file: Path to log file (optional)
        console_output: Whether to output to console
        
    Returns:
        StructuredLogger instance
    """
    return StructuredLogger(
        name=name,
        log_level=log_level,
        log_format=log_format,
        log_file=log_file,
        console_output=console_output
    )


# Module-level logger factory
def setup_logging(
    log_level: str = "INFO",
    log_format: str = "json",
    log_file: Optional[str] = None
):
    """
    Setup root logging configuration
    
    Args:
        log_level: Logging level
        log_format: Log format (json, text)
        log_file: Path to log file
    """
    root_logger = logging.getLogger()
    root_logger.setLevel(getattr(logging, log_level.upper()))
    
    # Clear existing handlers
    root_logger.handlers.clear()
    
    # Console handler
    console_handler = logging.StreamHandler(sys.stdout)
    if log_format == "json":
        console_handler.setFormatter(StructuredFormatter())
    else:
        console_handler.setFormatter(TextFormatter())
    root_logger.addHandler(console_handler)
    
    # File handler
    if log_file:
        log_path = Path(log_file)
        log_path.parent.mkdir(parents=True, exist_ok=True)
        
        file_handler = logging.FileHandler(log_file)
        if log_format == "json":
            file_handler.setFormatter(StructuredFormatter())
        else:
            file_handler.setFormatter(TextFormatter())
        root_logger.addHandler(file_handler)

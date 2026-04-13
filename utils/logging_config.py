"""
Logging configuration
"""
import logging
import sys
import json
from logging.handlers import RotatingFileHandler
from datetime import datetime
from pathlib import Path
from typing import Optional, Dict, Any
from config import settings, LOGS_DIR


def setup_logging():
    """
    Setup logging configuration with log rotation
    """
    # Ensure logs directory exists
    LOGS_DIR.mkdir(parents=True, exist_ok=True)
    
    # Create rotating file handler
    file_handler = RotatingFileHandler(
        settings.log_file,
        maxBytes=settings.log_max_bytes,
        backupCount=settings.log_backup_count
    )
    
    # Configure root logger
    logging.basicConfig(
        level=getattr(logging, settings.log_level),
        format=settings.log_format,
        handlers=[
            file_handler,
            logging.StreamHandler(sys.stdout)
        ]
    )
    
    # Set specific logger levels
    logging.getLogger("httpx").setLevel(logging.WARNING)
    logging.getLogger("urllib3").setLevel(logging.WARNING)
    logging.getLogger("playwright").setLevel(logging.WARNING)
    
    # Create validation error logger
    validation_logger = logging.getLogger("validation_error")
    validation_logger.setLevel(logging.WARNING)
    
    # Create retry logger
    retry_logger = logging.getLogger("retry")
    retry_logger.setLevel(logging.INFO)


def log_validation_error(
    field_name: str,
    invalid_value: Any,
    expected_value: Optional[str] = None,
    source: Optional[str] = None,
    vehicle_id: Optional[str] = None,
    context: Optional[Dict[str, Any]] = None
) -> None:
    """
    Log validation failure with structured context
    
    Args:
        field_name: Name of the field that failed validation
        invalid_value: The invalid value that was provided
        expected_value: Expected value or range
        source: Source location (file, function, line)
        vehicle_id: Vehicle ID or identifier if available
        context: Additional context as dictionary
    """
    logger = logging.getLogger("validation_error")
    
    # Determine log level based on strict mode
    log_level = logging.ERROR if settings.validation_strict_mode else logging.WARNING
    
    # Build structured log data
    log_data = {
        "field_name": field_name,
        "invalid_value": str(invalid_value),
        "expected_value": expected_value,
        "source": source,
        "vehicle_id": vehicle_id,
        "context": context or {}
    }
    
    # Log with structured format
    logger.log(
        log_level,
        json.dumps(log_data, default=str),
        extra={"structured": True}
    )
    
    # Track validation failure count
    track_validation_failure()


# Validation failure tracking (simple in-memory counter)
_validation_failure_count = 0
_validation_failure_start = None
_validation_failure_fields = {}  # Track which fields are failing


def track_validation_failure(field_name: Optional[str] = None) -> None:
    """Track validation failure count for alerting"""
    global _validation_failure_count, _validation_failure_start, _validation_failure_fields
    
    if _validation_failure_start is None:
        _validation_failure_start = datetime.utcnow()
    
    _validation_failure_count += 1
    
    # Track which fields are failing
    if field_name:
        _validation_failure_fields[field_name] = _validation_failure_fields.get(field_name, 0) + 1
    
    # Check if threshold exceeded
    if _validation_failure_count >= settings.validation_failure_threshold:
        logger = logging.getLogger("validation_error")
        
        # Calculate failure rate
        if _validation_failure_start:
            elapsed = (datetime.utcnow() - _validation_failure_start).total_seconds()
            failure_rate = _validation_failure_count / max(elapsed, 1)
        else:
            failure_rate = 0
        
        # Get top failing fields
        top_fields = sorted(_validation_failure_fields.items(), key=lambda x: x[1], reverse=True)[:5]
        
        logger.critical(
            f"Validation failure threshold exceeded: {_validation_failure_count} failures",
            extra={
                "structured": True,
                "failure_rate": failure_rate,
                "top_failing_fields": dict(top_fields)
            }
        )
        
        # Send alert if enabled
        if settings.validation_alert_enabled:
            send_validation_alert(_validation_failure_count, failure_rate, top_fields)


def send_validation_alert(count: int, rate: float, top_fields: list) -> None:
    """Send validation failure alert via configured notification channels"""
    # This is a placeholder - actual implementation would use notification channels
    logger = logging.getLogger("validation_error")
    logger.warning(
        f"VALIDATION ALERT: {count} failures detected (rate: {rate:.2f}/sec). Top fields: {top_fields}"
    )
    # TODO: Integrate with Discord/Email/Telegram notifications


def get_validation_health() -> Dict[str, Any]:
    """Get validation health status for health check endpoint"""
    global _validation_failure_count, _validation_failure_start, _validation_failure_fields
    
    if _validation_failure_start:
        elapsed = (datetime.utcnow() - _validation_failure_start).total_seconds()
        failure_rate = _validation_failure_count / max(elapsed, 1)
    else:
        failure_rate = 0
    
    return {
        "failure_count": _validation_failure_count,
        "failure_rate": failure_rate,
        "threshold": settings.validation_failure_threshold,
        "threshold_exceeded": _validation_failure_count >= settings.validation_failure_threshold,
        "top_failing_fields": dict(sorted(_validation_failure_fields.items(), key=lambda x: x[1], reverse=True)[:5]),
        "alert_enabled": settings.validation_alert_enabled,
        "strict_mode": settings.validation_strict_mode
    }


def reset_validation_failure_count() -> None:
    """Reset validation failure counter (called hourly)"""
    global _validation_failure_count, _validation_failure_start, _validation_failure_fields
    _validation_failure_count = 0
    _validation_failure_start = None
    _validation_failure_fields = {}


def get_validation_failure_count() -> int:
    """Get current validation failure count"""
    return _validation_failure_count


def log_retry_attempt(
    attempt_number: int,
    wait_time: float,
    exception_type: str,
    error_message: str,
    operation: str,
    context: Optional[Dict[str, Any]] = None
) -> None:
    """
    Log retry attempt with context
    
    Args:
        attempt_number: Current retry attempt number
        wait_time: Time to wait before next retry
        exception_type: Type of exception that triggered retry
        error_message: Error message
        operation: Operation being retried (function name)
        context: Additional context
    """
    logger = logging.getLogger("retry")
    
    log_data = {
        "attempt_number": attempt_number,
        "wait_time": wait_time,
        "exception_type": exception_type,
        "error_message": error_message,
        "operation": operation,
        "context": context or {}
    }
    
    logger.warning(
        json.dumps(log_data, default=str),
        extra={"structured": True}
    )

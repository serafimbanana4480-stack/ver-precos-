"""
Production safeguards and enhanced error handling for critical operations
"""
from __future__ import annotations
import logging
import sys
import traceback
from typing import Optional, Callable, Any, Dict
from functools import wraps
from datetime import datetime, timezone, timedelta
from contextlib import contextmanager

from config import settings

logger = logging.getLogger(__name__)


class ProductionError(Exception):
    """Base exception for production errors"""
    def __init__(self, message: str, context: Optional[Dict[str, Any]] = None):
        super().__init__(message)
        self.context = context or {}
        self.timestamp = datetime.now(timezone.utc)


class CircuitBreaker:
    """Circuit breaker pattern to prevent cascading failures"""
    
    def __init__(
        self,
        failure_threshold: int = 5,
        recovery_timeout: int = 60,
        expected_exception: Exception = Exception
    ):
        self.failure_threshold = failure_threshold
        self.recovery_timeout = recovery_timeout
        self.expected_exception = expected_exception
        
        self.failure_count = 0
        self.last_failure_time = None
        self.state = 'closed'  # closed, open, half-open
    
    def record_success(self) -> None:
        """Record a successful operation"""
        self.failure_count = 0
        self.state = 'closed'
        logger.debug("Circuit breaker: operation succeeded, circuit closed")
    
    def record_failure(self) -> None:
        """Record a failed operation"""
        self.failure_count += 1
        self.last_failure_time = datetime.now(timezone.utc)
        
        if self.failure_count >= self.failure_threshold:
            self.state = 'open'
            logger.warning(
                f"Circuit breaker: failure threshold ({self.failure_threshold}) reached, circuit opened"
            )
    
    def can_attempt(self) -> bool:
        """Check if operation can be attempted"""
        if self.state == 'closed':
            return True
        
        if self.state == 'open':
            if self.last_failure_time:
                time_since_failure = (datetime.now(timezone.utc) - self.last_failure_time).total_seconds()
                if time_since_failure > self.recovery_timeout:
                    self.state = 'half-open'
                    logger.info("Circuit breaker: recovery timeout elapsed, attempting recovery")
                    return True
            return False
        
        if self.state == 'half-open':
            return True
        
        return False


# Global circuit breakers for critical operations
_olx_circuit_breaker = CircuitBreaker(failure_threshold=3, recovery_timeout=300)
_standvirtual_circuit_breaker = CircuitBreaker(failure_threshold=3, recovery_timeout=300)
_autosapo_circuit_breaker = CircuitBreaker(failure_threshold=3, recovery_timeout=300)
_ai_api_circuit_breaker = CircuitBreaker(failure_threshold=5, recovery_timeout=60)
_database_circuit_breaker = CircuitBreaker(failure_threshold=5, recovery_timeout=30)

# Legacy alias for backward compatibility
_scraping_circuit_breaker = _olx_circuit_breaker


def with_circuit_breaker(breaker: CircuitBreaker, operation_name: str):
    """
    Decorator to add circuit breaker protection to operations
    
    Args:
        breaker: Circuit breaker instance
        operation_name: Name of the operation for logging
    """
    import inspect
    def decorator(func: Callable) -> Callable:
        @wraps(func)
        async def async_wrapper(*args, **kwargs) -> Any:
            if not breaker.can_attempt():
                logger.error(f"Circuit breaker: {operation_name} blocked - circuit is {breaker.state}")
                raise ProductionError(
                    f"Operation '{operation_name}' blocked by circuit breaker (state: {breaker.state})",
                    context={"operation": operation_name, "state": breaker.state}
                )
            
            try:
                result = await func(*args, **kwargs)
                breaker.record_success()
                return result
            except breaker.expected_exception:
                breaker.record_failure()
                raise
            except Exception as e:
                # Any other exception might or might not be a failure of the circuit
                # For safety, we catch the expected one above
                raise

        @wraps(func)
        def sync_wrapper(*args, **kwargs) -> Any:
            if not breaker.can_attempt():
                logger.error(f"Circuit breaker: {operation_name} blocked - circuit is {breaker.state}")
                raise ProductionError(
                    f"Operation '{operation_name}' blocked by circuit breaker (state: {breaker.state})",
                    context={"operation": operation_name, "state": breaker.state}
                )
            
            try:
                result = func(*args, **kwargs)
                breaker.record_success()
                return result
            except breaker.expected_exception:
                breaker.record_failure()
                raise

        if inspect.iscoroutinefunction(func):
            return async_wrapper
        return sync_wrapper
    return decorator


def with_production_error_handling(operation_name: str, raise_on_error: bool = True):
    """
    Decorator to add comprehensive error handling for production operations
    
    Args:
        operation_name: Name of the operation for logging
        raise_on_error: Whether to raise exception after logging
    """
    def decorator(func: Callable) -> Callable:
        @wraps(func)
        def wrapper(*args, **kwargs) -> Any:
            start_time = datetime.now(timezone.utc)
            try:
                logger.info(f"[SAFEGUARD] Starting {operation_name}")
                result = func(*args, **kwargs)
                duration = (datetime.now(timezone.utc) - start_time).total_seconds()
                logger.info(f"[SAFEGUARD] {operation_name} completed successfully in {duration:.2f}s")
                return result
            except ProductionError as e:
                duration = (datetime.now(timezone.utc) - start_time).total_seconds()
                logger.error(
                    f"[SAFEGUARD] {operation_name} production error after {duration:.2f}s: {e}",
                    extra={'context': e.context, 'timestamp': e.timestamp.isoformat()}
                )
                if raise_on_error:
                    raise
                return None
            except Exception as e:
                duration = (datetime.now(timezone.utc) - start_time).total_seconds()
                logger.error(
                    f"[SAFEGUARD] {operation_name} unexpected error after {duration:.2f}s: {e}",
                    exc_info=True
                )
                if raise_on_error:
                    raise ProductionError(
                        f"Unexpected error in {operation_name}: {str(e)}",
                        context={'exception_type': type(e).__name__, 'traceback': traceback.format_exc()}
                    )
                return None
        return wrapper
    return decorator


@contextmanager
def timeout_context(timeout_seconds: int, operation_name: str = "operation"):
    """
    Context manager to add timeout protection to operations
    
    Args:
        timeout_seconds: Timeout in seconds
        operation_name: Name of the operation for logging
    """
    import signal
    import threading
    
    timeout_event = threading.Event()
    
    def timeout_handler(signum, frame):
        raise TimeoutError(f"{operation_name} timed out after {timeout_seconds} seconds")
    
    # Standard Unix signal approach
    if sys.platform != 'win32':
        old_handler = signal.signal(signal.SIGALRM, timeout_handler)
        signal.alarm(timeout_seconds)
    else:
        # Windows-compatible watchdog (logs warning but can't easily kill sync thread)
        # However, many our our operations (Playwright, HTTPX) have their own internal timeouts
        def watchdog():
            if not timeout_event.wait(timeout_seconds):
                logger.warning(f"[SAFEGUARD] {operation_name} has exceeded its {timeout_seconds}s timeout on Windows. Internal timeouts should trigger soon.")
        
        watchdog_thread = threading.Thread(target=watchdog, daemon=True)
        watchdog_thread.start()
    
    try:
        yield
    except TimeoutError as e:
        logger.error(f"[SAFEGUARD] {operation_name} timeout: {e}")
        raise ProductionError(f"Operation timeout: {e}", context={'timeout': timeout_seconds})
    finally:
        timeout_event.set()
        if sys.platform != 'win32':
            signal.alarm(0)
            signal.signal(signal.SIGALRM, old_handler)


def validate_environment() -> Dict[str, Any]:
    """
    Validate production environment configuration
    
    Returns:
        Dictionary with validation results
    """
    issues = []
    warnings = []
    
    # Check database configuration
    if not settings.database_url:
        issues.append("DATABASE_URL not configured")
    
    # Check AI configuration
    if not settings.use_ollama and not settings.grok_api_key:
        warnings.append("No AI API configured (Grok or Ollama)")
    
    # If using Ollama, verify it's actually running
    if settings.use_ollama:
        try:
            import httpx
            resp = httpx.get(f"{settings.ollama_url}/api/tags", timeout=5)
            if resp.status_code == 200:
                models = resp.json().get("models", [])
                if not models:
                    warnings.append("Ollama running but no models found. Run: ollama pull qwen2.5-coder:7b")
            else:
                warnings.append(f"Ollama not responding correctly (status: {resp.status_code})")
        except Exception as e:
            warnings.append(f"Ollama not running at {settings.ollama_url}. AI features will be disabled.")
    
    # Check logging directory
    if not settings.log_file:
        issues.append("Log file path not configured")
    
    # Check critical directories exist
    from pathlib import Path
    from config import LOGS_DIR, DATA_DIR, MODELS_DIR
    critical_dirs = [LOGS_DIR, DATA_DIR, MODELS_DIR]
    for dir_path in critical_dirs:
        if not isinstance(dir_path, Path):
            dir_path = Path(dir_path)
        if not dir_path.exists():
            try:
                dir_path.mkdir(parents=True, exist_ok=True)
            except Exception as e:
                issues.append(f"Cannot create directory {dir_path}: {e}")
    
    # Check Sentry configuration for production
    if settings.is_production and not settings.sentry_dsn:
        warnings.append("Production environment without Sentry DSN configured")

    # JWT secret required in production
    if settings.is_production:
        jwt_secret = (settings.jwt_secret or "").strip()
        if not jwt_secret:
            issues.append("JWT_SECRET (or jwt_secret in .env) must be set in production")
        elif jwt_secret in (
            "your-secret-key-change-in-production",
            "your-secret-key-here",
            "dev-only-ephemeral-jwt-secret",
        ):
            issues.append("JWT secret must not use a default/placeholder value in production")
    
    return {
        'is_valid': len(issues) == 0,
        'issues': issues,
        'warnings': warnings,
        'timestamp': datetime.now(timezone.utc).isoformat()
    }


def graceful_shutdown(signum=None, frame=None):
    """
    Handle graceful shutdown of the application
    
    Args:
        signum: Signal number
        frame: Current stack frame
    """
    logger.info("[SAFEGUARD] Graceful shutdown initiated")
    
    # Shutdown request queue
    try:
        from utils.request_queue import shutdown_queue
        shutdown_queue()
        logger.info("[SAFEGUARD] Request queue stopped")
    except Exception as e:
        logger.error(f"[SAFEGUARD] Error stopping request queue: {e}")
    
    # Close database connections
    try:
        from database.db import engine
        engine.dispose()
        logger.info("[SAFEGUARD] Database connections closed")
    except Exception as e:
        logger.error(f"[SAFEGUARD] Error closing database: {e}")
    
    # Flush logs
    for handler in logging.getLogger().handlers:
        try:
            handler.flush()
        except Exception:
            pass
    
    logger.info("[SAFEGUARD] Graceful shutdown completed")
    sys.exit(0)


def setup_signal_handlers():
    """Setup signal handlers for graceful shutdown"""
    import signal
    
    signal.signal(signal.SIGINT, graceful_shutdown)
    signal.signal(signal.SIGTERM, graceful_shutdown)
    
    logger.info("[SAFEGUARD] Signal handlers configured for graceful shutdown")


def monitor_system_health() -> Dict[str, Any]:
    """
    Monitor system health metrics
    
    Returns:
        Dictionary with health metrics
    """
    try:
        import psutil
    except ImportError:
        logger.warning("psutil not installed, skipping system health monitoring")
        return {
            'status': 'unknown',
            'error': 'psutil not installed',
            'timestamp': datetime.now(timezone.utc).isoformat()
        }
    
    import os
    
    try:
        # CPU usage
        cpu_percent = psutil.cpu_percent(interval=1)
        
        # Memory usage
        memory = psutil.virtual_memory()
        memory_percent = memory.percent
        
        # Disk usage
        disk = psutil.disk_usage('/')
        disk_percent = disk.percent
        
        # Process info
        process = psutil.Process(os.getpid())
        process_memory = process.memory_info().rss / 1024 / 1024  # MB
        
        health_status = 'healthy'
        if cpu_percent > 90 or memory_percent > 90 or disk_percent > 90:
            health_status = 'warning'
        if cpu_percent > 95 or memory_percent > 95 or disk_percent > 95:
            health_status = 'critical'
        
        return {
            'status': health_status,
            'cpu_percent': cpu_percent,
            'memory_percent': memory_percent,
            'disk_percent': disk_percent,
            'process_memory_mb': process_memory,
            'timestamp': datetime.now(timezone.utc).isoformat()
        }
    except ImportError:
        logger.warning("psutil not installed, skipping system health monitoring")
        return {
            'status': 'unknown',
            'error': 'psutil not installed',
            'timestamp': datetime.now(timezone.utc).isoformat()
        }
    except Exception as e:
        logger.error(f"Error monitoring system health: {e}")
        return {
            'status': 'error',
            'error': str(e),
            'timestamp': datetime.now(timezone.utc).isoformat()
        }


def check_database_health() -> Dict[str, Any]:
    """
    Check database connectivity and health
    
    Returns:
        Dictionary with database health status
    """
    try:
        from database.db import get_db_context
        from database.models import Vehicle
        from sqlalchemy import text
        
        start_time = datetime.now(timezone.utc)
        
        with get_db_context() as db:
            # Test basic connectivity
            db.execute(text("SELECT 1"))
            
            # Test query performance
            db.query(Vehicle).limit(1).first()
            
        duration = (datetime.now(timezone.utc) - start_time).total_seconds()
        
        if duration > 5:
            status = 'slow'
        elif duration > 1:
            status = 'degraded'
        else:
            status = 'healthy'
        
        return {
            'status': status,
            'duration_seconds': duration,
            'timestamp': datetime.now(timezone.utc).isoformat()
        }
    except Exception as e:
        logger.error(f"Database health check failed: {e}")
        return {
            'status': 'unhealthy',
            'error': str(e),
            'timestamp': datetime.now(timezone.utc).isoformat()
        }


def get_health_check_summary() -> Dict[str, Any]:
    """
    Get comprehensive health check summary
    
    Returns:
        Dictionary with overall health status
    """
    env_validation = validate_environment()
    system_health = monitor_system_health()
    db_health = check_database_health()
    
    # Determine overall status
    overall_status = 'healthy'
    if env_validation['issues'] or db_health['status'] == 'unhealthy':
        overall_status = 'unhealthy'
    elif env_validation['warnings'] or system_health['status'] in ['warning', 'critical']:
        overall_status = 'warning'
    
    return {
        'overall_status': overall_status,
        'environment': env_validation,
        'system': system_health,
        'database': db_health,
        'timestamp': datetime.now(timezone.utc).isoformat()
    }

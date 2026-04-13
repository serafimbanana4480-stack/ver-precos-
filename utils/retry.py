"""
Retry utility decorators using tenacity
"""
from tenacity import (
    retry,
    stop_after_attempt,
    wait_exponential,
    retry_if_exception_type,
    before_sleep_log
)
import logging
from typing import Type, Tuple, Any
from utils.logging_config import log_retry_attempt

logger = logging.getLogger(__name__)


def retry_network(max_attempts: int = 3, min_wait: float = 2, max_wait: float = 10):
    """
    Retry decorator for network-related errors (TimeoutError, ConnectionError, HTTPError)
    
    Retries only on transient errors:
    - TimeoutError, ConnectionError
    - HTTPError with status 429 (rate limit)
    - HTTPError with status 5xx (server errors)
    
    Does NOT retry on:
    - HTTPError with status 4xx (client errors, except 429)
    - ValueError (logic errors)
    - KeyError (missing data errors)
    
    Args:
        max_attempts: Maximum number of retry attempts (default: 3)
        min_wait: Minimum wait time in seconds (default: 2)
        max_wait: Maximum wait time in seconds (default: 10)
    """
    def decorator(func):
        @retry(
            stop=stop_after_attempt(max_attempts),
            wait=wait_exponential(multiplier=1, min=min_wait, max=max_wait),
            retry=retry_if_exception_type((TimeoutError, ConnectionError)),
            before_sleep=before_sleep_log(logger, logging.WARNING),
            reraise=True
        )
        def wrapper(*args, **kwargs):
            return func(*args, **kwargs)
        return wrapper
    return decorator


def retry_ai_api(max_attempts: int = 3, min_wait: float = 2, max_wait: float = 10):
    """
    Retry decorator for AI API errors (rate limits, timeouts)
    
    Args:
        max_attempts: Maximum number of retry attempts (default: 3)
        min_wait: Minimum wait time in seconds (default: 2)
        max_wait: Maximum wait time in seconds (default: 10)
    """
    def decorator(func):
        @retry(
            stop=stop_after_attempt(max_attempts),
            wait=wait_exponential(multiplier=1, min=min_wait, max=max_wait),
            retry=retry_if_exception_type((TimeoutError, ConnectionError)),
            before_sleep=before_sleep_log(logger, logging.WARNING),
            reraise=True
        )
        def wrapper(*args, **kwargs):
            return func(*args, **kwargs)
        return wrapper
    return decorator


def retry_database(max_attempts: int = 3, min_wait: float = 2, max_wait: float = 10):
    """
    Retry decorator for database connection failures
    
    Args:
        max_attempts: Maximum number of retry attempts (default: 3)
        min_wait: Minimum wait time in seconds (default: 2)
        max_wait: Maximum wait time in seconds (default: 10)
    """
    def decorator(func):
        @retry(
            stop=stop_after_attempt(max_attempts),
            wait=wait_exponential(multiplier=1, min=min_wait, max=max_wait),
            retry=retry_if_exception_type((ConnectionError, TimeoutError)),
            before_sleep=before_sleep_log(logger, logging.WARNING),
            reraise=True
        )
        def wrapper(*args, **kwargs):
            return func(*args, **kwargs)
        return wrapper
    return decorator


def retry_with_custom_exceptions(
    exceptions: Tuple[Type[Exception], ...],
    max_attempts: int = 3,
    min_wait: float = 2,
    max_wait: float = 10
):
    """
    Retry decorator for custom exception types
    
    Args:
        exceptions: Tuple of exception types to retry on
        max_attempts: Maximum number of retry attempts (default: 3)
        min_wait: Minimum wait time in seconds (default: 2)
        max_wait: Maximum wait time in seconds (default: 10)
    """
    def decorator(func):
        @retry(
            stop=stop_after_attempt(max_attempts),
            wait=wait_exponential(multiplier=1, min=min_wait, max=max_wait),
            retry=retry_if_exception_type(exceptions),
            before_sleep=before_sleep_log(logger, logging.WARNING),
            reraise=True
        )
        def wrapper(*args, **kwargs):
            return func(*args, **kwargs)
        return wrapper
    return decorator

"""
Alert retry logic for AutoDeal IA Hunter.
"""
import time
from typing import Callable
from functools import wraps


def retry_alert(max_attempts: int = 3, delay_seconds: float = 5.0):
    """Decorator to retry failed alert sends."""
    def decorator(func: Callable):
        @wraps(func)
        def wrapper(*args, **kwargs):
            for attempt in range(max_attempts):
                try:
                    result = func(*args, **kwargs)
                    if result:
                        return True
                except Exception:
                    pass
                
                if attempt < max_attempts - 1:
                    time.sleep(delay_seconds)
            
            return False
        return wrapper
    return decorator

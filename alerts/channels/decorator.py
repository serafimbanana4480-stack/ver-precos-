"""
Channel decorator for alerts.
"""
from typing import Callable
from functools import wraps


def log_send(func: Callable) -> Callable:
    """Decorator to log channel sends."""
    @wraps(func)
    def wrapper(self, *args, **kwargs):
        print(f"Sending alert via {self.__class__.__name__}")
        result = func(self, *args, **kwargs)
        print(f"Alert send result: {result}")
        return result
    return wrapper

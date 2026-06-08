"""
Profiler for AutoDeal IA Hunter.
"""
import cProfile
import pstats
from typing import Optional, Callable
from contextlib import contextmanager


class Profiler:
    """Profiler for performance analysis."""
    
    def __init__(self):
        self.profiler = cProfile.Profile()
    
    @contextmanager
    def profile(self, sort_by: str = "cumulative"):
        """Profile code block."""
        self.profiler.enable()
        try:
            yield
        finally:
            self.profiler.disable()
            stats = pstats.Stats(self.profiler)
            stats.sort_stats(sort_by)
            stats.print_stats(20)
    
    def profile_function(self, func: Callable) -> Callable:
        """Decorator to profile function."""
        def wrapper(*args, **kwargs):
            with self.profile():
                return func(*args, **kwargs)
        return wrapper

"""
FastAPI instrumentation for AutoDeal IA Hunter.
"""
from typing import Callable
from fastapi import FastAPI, Request


class FastAPIInstrumentation:
    """Instrumentation for FastAPI."""
    
    def __init__(self, app: FastAPI):
        self.app = app
        self._setup_middleware()
    
    def _setup_middleware(self) -> None:
        """Setup instrumentation middleware."""
        @self.app.middleware("http")
        async def instrument_requests(request: Request, call_next: Callable):
            # Add instrumentation logic here
            response = await call_next(request)
            return response

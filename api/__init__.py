"""
Legacy standalone API package (experimental).

Canonical HTTP API: ``app.api.main`` (FastAPI app).
This package is kept for reference; import submodules directly if needed.
"""

import warnings

warnings.warn(
    "Package 'api' is legacy; use app.api.main as the canonical FastAPI entrypoint.",
    DeprecationWarning,
    stacklevel=2,
)

__all__ = [
    "api_router",
    "setup_middleware",
    "get_database",
    "get_cache",
]


def __getattr__(name: str):
    if name == "api_router":
        from .routes import api_router
        return api_router
    if name == "setup_middleware":
        from .middleware import setup_middleware
        return setup_middleware
    if name == "get_database":
        from .dependencies import get_database
        return get_database
    if name == "get_cache":
        from .dependencies import get_cache
        return get_cache
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")

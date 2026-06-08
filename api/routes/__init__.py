"""
API routes module.
"""

from .listings import listings_router
from .search import search_router
from .analytics import analytics_router
from .health import health_router
# Admin router disabled - AdminService not implemented yet
# from .admin import admin_router

__all__ = [
    'listings_router',
    'search_router',
    'analytics_router',
    'health_router',
    # 'admin_router'
]

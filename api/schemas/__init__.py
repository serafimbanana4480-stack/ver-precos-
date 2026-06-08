"""
API schemas module.
"""

from .listings import (
    ListingResponse, 
    ListingCreate, 
    ListingUpdate, 
    ListingFilter
)
from .search import (
    SearchRequest, 
    SearchResult, 
    SearchFilter
)
from .users import (
    UserResponse, 
    UserCreate, 
    UserUpdate,
    UserLogin,
    UserRegister
)
from .analytics import (
    AnalyticsRequest,
    AnalyticsResponse,
    MarketTrendsResponse,
    PriceAnalysisResponse
)
from .common import (
    BaseResponse,
    ErrorResponse,
    PaginationParams,
    DateRangeParams
)

__all__ = [
    'ListingResponse',
    'ListingCreate', 
    'ListingUpdate', 
    'ListingFilter',
    'SearchRequest', 
    'SearchResult', 
    'SearchFilter',
    'UserResponse', 
    'UserCreate', 
    'UserUpdate',
    'UserLogin',
    'UserRegister',
    'AnalyticsRequest',
    'AnalyticsResponse',
    'MarketTrendsResponse',
    'PriceAnalysisResponse',
    'BaseResponse',
    'ErrorResponse',
    'PaginationParams',
    'DateRangeParams'
]

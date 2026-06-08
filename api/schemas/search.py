"""
Search schemas for API.
"""
from typing import Optional, List, Dict, Any, Union
from datetime import datetime
from pydantic import BaseModel, Field, validator
import re


class BaseSearch(BaseModel):
    """Base search schema."""
    
    query: Optional[str] = None
    filters: Optional[Dict[str, Any]] = None
    sort_by: Optional[str] = None
    sort_order: Optional[str] = None
    limit: Optional[int] = None
    offset: Optional[int] = None
    
    class Config:
        from_attributes = True


class SearchRequest(BaseSearch):
    """Search request schema."""
    
    query: Optional[str] = Field(None, min_length=2, max_length=100)
    make: Optional[str] = None
    model: Optional[str] = None
    min_price: Optional[float] = Field(None, ge=0)
    max_price: Optional[float] = Field(None, le=1000000)
    min_year: Optional[int] = Field(None, ge=1900)
    max_year: Optional[int] = Field(None, le=datetime.now().year + 1)
    min_mileage: Optional[int] = Field(None, ge=0)
    max_mileage: Optional[int] = Field(None, le=500000)
    fuel_type: Optional[str] = None
    transmission: Optional[str] = None
    location: Optional[str] = None
    condition: Optional[str] = None
    source: Optional[str] = None
    seller_type: Optional[str] = None
    has_image: Optional[bool] = None
    keywords: Optional[List[str]] = None
    exclude_keywords: Optional[List[str]] = None
    sort_by: str = Field("scraped_at", pattern="^(price|year|mileage|scraped_at|relevance)$")
    sort_order: str = Field("desc", pattern="^(asc|desc)$")
    limit: int = Field(20, ge=1, le=100)
    offset: int = Field(0, ge=0)
    include_facets: bool = False
    include_highlights: bool = False
    include_aggregations: bool = False
    
    @validator('query')
    def clean_query(cls, v):
        if v:
            return v.strip()
        return v
    
    @validator('keywords')
    def clean_keywords(cls, v):
        if v:
            return [kw.strip() for kw in v if kw.strip()]
        return v
    
    @validator('exclude_keywords')
    def clean_exclude_keywords(cls, v):
        if v:
            return [kw.strip() for kw in v if kw.strip()]
        return v
    
    @validator('make')
    def clean_make(cls, v):
        if v:
            return v.strip().title()
        return v
    
    @validator('model')
    def clean_model(cls, v):
        if v:
            return v.strip().title()
        return v
    
    @validator('location')
    def clean_location(cls, v):
        if v:
            return v.strip().title()
        return v


class SearchResult(BaseModel):
    """Search result schema."""
    
    listings: List[Dict[str, Any]]
    total: int
    limit: int
    offset: int
    has_more: bool
    facets: Optional[Dict[str, Any]] = None
    aggregations: Optional[Dict[str, Any]] = None
    search_time: Optional[float] = None
    suggestions: Optional[List[str]] = None
    
    @validator('listings')
    def validate_listings(cls, v):
        if v is None:
            return []
        return v


class SearchFilter(BaseModel):
    """Search filter schema."""
    
    field: str = Field(..., min_length=1)
    operator: str = Field("eq", pattern="^(eq|ne|gt|gte|lt|lte|in|nin|contains|startswith|endswith|regex)$")
    value: Union[str, int, float, bool, List[Any]]
    
    @validator('field')
    def clean_field(cls, v):
        return v.strip()
    
    @validator('value')
    def clean_value(cls, v):
        if isinstance(v, str):
            return v.strip()
        return v


class AdvancedSearchRequest(BaseModel):
    """Advanced search request schema."""
    
    query: Optional[str] = Field(None, min_length=2, max_length=200)
    filters: List[SearchFilter] = Field(default_factory=list)
    must_filters: List[SearchFilter] = Field(default_factory=list)
    must_not_filters: List[SearchFilter] = Field(default_factory=list)
    should_filters: List[SearchFilter] = Field(default_factory=list)
    should_not_filters: List[SearchFilter] = Field(default_factory=list)
    sort_by: List[Dict[str, Any]] = Field(default_factory=list)
    limit: int = Field(20, ge=1, le=100)
    offset: int = Field(0, ge=0)
    include_facets: bool = True
    include_highlights: bool = True
    include_aggregations: bool = True
    min_score: Optional[float] = Field(None, ge=0, le=1)
    explain: bool = False
    
    @validator('query')
    def clean_query(cls, v):
        if v:
            return v.strip()
        return v


class SearchSuggestion(BaseModel):
    """Search suggestion schema."""
    
    text: str = Field(..., min_length=1)
    type: str = Field(..., pattern="^(make|model|location|keyword)$")
    score: float = Field(..., ge=0, le=1)
    metadata: Optional[Dict[str, Any]] = None


class SearchFacet(BaseModel):
    """Search facet schema."""
    
    field: str
    values: List[Dict[str, Any]]
    total: int


class SearchAggregation(BaseModel):
    """Search aggregation schema."""
    
    name: str
    type: str
    result: Dict[str, Any]


class SearchHighlight(BaseModel):
    """Search highlight schema."""
    
    field: str
    fragments: List[str]
    pre_tag: str = "<em>"
    post_tag: str = "</em>"


class SavedSearch(BaseModel):
    """Saved search schema."""
    
    id: Optional[str] = None
    name: str = Field(..., min_length=1, max_length=100)
    query: str = Field(..., min_length=2, max_length=200)
    filters: Dict[str, Any] = Field(default_factory=dict)
    sort_by: Optional[str] = None
    sort_order: Optional[str] = None
    user_id: Optional[str] = None
    is_active: bool = True
    notification_enabled: bool = False
    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None
    
    @validator('name')
    def clean_name(cls, v):
        return v.strip()
    
    @validator('query')
    def clean_query(cls, v):
        return v.strip()


class SearchHistory(BaseModel):
    """Search history schema."""
    
    id: Optional[str] = None
    query: str = Field(..., min_length=2, max_length=200)
    filters: Dict[str, Any] = Field(default_factory=dict)
    results_count: int = Field(..., ge=0)
    user_id: Optional[str] = None
    session_id: Optional[str] = None
    created_at: Optional[datetime] = None


class SearchAnalytics(BaseModel):
    """Search analytics schema."""
    
    query: str = Field(..., min_length=2, max_length=200)
    search_count: int = Field(..., ge=0)
    avg_results: float = Field(..., ge=0)
    avg_search_time: float = Field(..., ge=0)
    click_through_rate: float = Field(..., ge=0, le=1)
    popular_filters: List[Dict[str, Any]]
    time_distribution: Dict[str, int]
    user_distribution: Dict[str, int]


class SearchExport(BaseModel):
    """Search export schema."""
    
    format: str = Field("csv", pattern="^(csv|json|excel)$")
    include_filters: bool = True
    include_facets: bool = True
    include_highlights: bool = False
    max_results: int = Field(1000, ge=1, le=10000)
    fields: Optional[List[str]] = None


class SearchComparison(BaseModel):
    """Search comparison schema."""
    
    name: str = Field(..., min_length=1, max_length=100)
    queries: List[str] = Field(..., min_items=2, max_items=5)
    compare_metrics: List[str] = Field(default_factory=lambda: ["results_count", "avg_price", "price_range"])
    filters: Optional[Dict[str, Any]] = None


class SearchRecommendation(BaseModel):
    """Search recommendation schema."""
    
    user_id: Optional[str] = None
    session_id: Optional[str] = None
    current_query: Optional[str] = None
    current_filters: Optional[Dict[str, Any]] = None
    limit: int = Field(10, ge=1, le=50)
    include_reasoning: bool = False


class SearchAutocomplete(BaseModel):
    """Search autocomplete schema."""
    
    query: str = Field(..., min_length=1, max_length=50)
    limit: int = Field(10, ge=1, le=20)
    types: List[str] = Field(default_factory=lambda: ["make", "model", "location"])
    include_counts: bool = True


class SearchSpellCheck(BaseModel):
    """Search spell check schema."""
    
    query: str = Field(..., min_length=2, max_length=100)
    suggestions: List[str] = Field(default_factory=list)
    did_you_mean: Optional[str] = None
    corrections: List[Dict[str, str]] = Field(default_factory=list)


class SearchBoost(BaseModel):
    """Search boost configuration schema."""
    
    field: str = Field(..., min_length=1)
    boost: float = Field(..., ge=0, le=10)
    condition: Optional[str] = None


class SearchAnalyzer(BaseModel):
    """Search analyzer configuration schema."""
    
    name: str = Field(..., min_length=1)
    tokenizer: str = Field("standard", pattern="^(standard|keyword|whitespace)$")
    filters: List[str] = Field(default_factory=list)
    char_filters: List[str] = Field(default_factory=list)


class SearchIndex(BaseModel):
    """Search index configuration schema."""
    
    name: str = Field(..., min_length=1)
    fields: List[Dict[str, Any]]
    analyzers: List[SearchAnalyzer] = Field(default_factory=list)
    boosters: List[SearchBoost] = Field(default_factory=list)
    settings: Dict[str, Any] = Field(default_factory=dict)


class SearchQuery(BaseModel):
    """Search query DSL schema."""
    
    bool: Optional[Dict[str, Any]] = None
    must: Optional[List[Dict[str, Any]]] = None
    filter: Optional[List[Dict[str, Any]]] = None
    should: Optional[List[Dict[str, Any]]] = None
    must_not: Optional[List[Dict[str, Any]]] = None
    sort: Optional[List[Dict[str, Any]]] = None
    from_: Optional[int] = Field(None, ge=0, alias="from")
    size: Optional[int] = Field(None, ge=1, le=10000)
    highlight: Optional[Dict[str, Any]] = None
    aggs: Optional[Dict[str, Any]] = None
    explain: Optional[bool] = False


class SearchTemplate(BaseModel):
    """Search template schema."""
    
    id: Optional[str] = None
    name: str = Field(..., min_length=1, max_length=100)
    description: Optional[str] = Field(None, max_length=500)
    template: str = Field(..., min_length=1)
    parameters: List[str] = Field(default_factory=list)
    is_active: bool = True
    created_by: Optional[str] = None
    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None


class SearchAlert(BaseModel):
    """Search alert schema."""
    
    id: Optional[str] = None
    name: str = Field(..., min_length=1, max_length=100)
    query: str = Field(..., min_length=2, max_length=200)
    filters: Dict[str, Any] = Field(default_factory=dict)
    alert_type: str = Field("new_listings", pattern="^(new_listings|price_drop|price_increase)$")
    threshold: Optional[float] = None
    notification_methods: List[str] = Field(default_factory=lambda: ["email"])
    is_active: bool = True
    last_triggered: Optional[datetime] = None
    trigger_count: int = Field(0, ge=0)
    user_id: Optional[str] = None
    created_at: Optional[datetime] = None
    
    @validator('name')
    def clean_name(cls, v):
        return v.strip()
    
    @validator('query')
    def clean_query(cls, v):
        return v.strip()


class SearchPerformance(BaseModel):
    """Search performance metrics schema."""
    
    query: str = Field(..., min_length=2, max_length=200)
    total_time: float = Field(..., ge=0)
    query_time: float = Field(..., ge=0)
    fetch_time: float = Field(..., ge=0)
    results_count: int = Field(..., ge=0)
    cache_hit: bool = False
    index_used: str
    shards: Dict[str, Any] = Field(default_factory=dict)


class SearchOptimization(BaseModel):
    """Search optimization suggestions schema."""
    
    query_id: str
    original_query: str
    optimized_query: str
    performance_improvement: float
    suggestions: List[str]
    applied_optimizations: List[str]


class SearchDebug(BaseModel):
    """Search debug information schema."""
    
    query: str = Field(..., min_length=2, max_length=200)
    parsed_query: Dict[str, Any]
    execution_plan: List[Dict[str, Any]]
    timing_breakdown: Dict[str, float]
    index_stats: Dict[str, Any]
    shard_stats: Dict[str, Any]
    cache_stats: Dict[str, Any]


class SearchValidation(BaseModel):
    """Search validation schema."""
    
    query: str = Field(..., min_length=2, max_length=200)
    is_valid: bool
    errors: List[str] = Field(default_factory=list)
    warnings: List[str] = Field(default_factory=list)
    suggestions: List[str] = Field(default_factory=list)


class SearchConfiguration(BaseModel):
    """Search configuration schema."""
    
    default_limit: int = Field(20, ge=1, le=100)
    max_limit: int = Field(100, ge=1, le=1000)
    default_sort_by: str = Field("scraped_at")
    default_sort_order: str = Field("desc")
    enable_facets: bool = True
    enable_highlights: bool = False
    enable_aggregations: bool = False
    enable_suggestions: bool = True
    enable_spell_check: bool = True
    enable_autocomplete: bool = True
    cache_results: bool = True
    cache_ttl: int = Field(300, ge=0, le=3600)
    index_refresh_interval: int = Field(3600, ge=60, le=86400)
    max_query_length: int = Field(200, ge=10, le=1000)
    
    @validator('default_sort_by')
    def validate_default_sort_by(cls, v):
        valid_fields = ["price", "year", "mileage", "scraped_at", "relevance"]
        if v not in valid_fields:
            raise ValueError(f'Default sort_by must be one of: {valid_fields}')
        return v
    
    @validator('default_sort_order')
    def validate_default_sort_order(cls, v):
        if v not in ["asc", "desc"]:
            raise ValueError('Default sort_order must be either "asc" or "desc"')
        return v


class SearchStats(BaseModel):
    """Search statistics schema."""
    
    total_searches: int
    unique_queries: int
    avg_query_length: float
    avg_results_count: float
    avg_search_time: float
    top_queries: List[Dict[str, Any]]
    top_filters: List[Dict[str, Any]]
    search_trends: List[Dict[str, Any]]
    performance_metrics: Dict[str, float]
    cache_hit_rate: float
    error_rate: float

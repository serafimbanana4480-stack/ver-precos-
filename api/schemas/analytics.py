"""
Analytics schemas for API.
"""
from typing import Optional, List, Dict, Any, Union
from datetime import datetime, date
from pydantic import BaseModel, Field, validator
import re


class BaseAnalytics(BaseModel):
    """Base analytics schema."""
    
    date_range: Optional[Dict[str, Any]] = None
    filters: Optional[Dict[str, Any]] = None
    metrics: Optional[List[str]] = None
    
    class Config:
        from_attributes = True


class AnalyticsRequest(BaseAnalytics):
    """Analytics request schema."""
    
    request_type: str = Field(..., pattern="^(overview|trends|price_analysis|market_share|performance)$")
    date_range: Dict[str, Union[str, datetime]] = Field(..., min_items=2, max_items=2)
    filters: Optional[Dict[str, Any]] = Field(default_factory=dict)
    metrics: Optional[List[str]] = Field(default_factory=list)
    group_by: Optional[str] = Field(None, pattern="^(make|model|location|fuel_type|transmission|condition)$")
    sort_by: Optional[str] = Field(None, pattern="^(date|value|count|percentage)$")
    sort_order: Optional[str] = Field("desc", pattern="^(asc|desc)$")
    limit: Optional[int] = Field(None, ge=1, le=1000)
    include_forecasts: bool = False
    include_comparisons: bool = False
    
    @validator('date_range')
    def validate_date_range(cls, v):
        if 'start' not in v or 'end' not in v:
            raise ValueError('Date range must include start and end dates')
        
        start_date = v['start']
        end_date = v['end']
        
        if isinstance(start_date, str):
            try:
                start_date = datetime.fromisoformat(start_date.replace('Z', '+00:00'))
            except ValueError:
                raise ValueError('Invalid start date format')
        
        if isinstance(end_date, str):
            try:
                end_date = datetime.fromisoformat(end_date.replace('Z', '+00:00'))
            except ValueError:
                raise ValueError('Invalid end date format')
        
        if start_date >= end_date:
            raise ValueError('Start date must be before end date')
        
        return {'start': start_date, 'end': end_date}
    
    @validator('metrics')
    def validate_metrics(cls, v):
        if v:
            valid_metrics = [
                'total_listings', 'average_price', 'median_price', 'price_range',
                'total_views', 'unique_users', 'conversion_rate', 'market_share',
                'inventory_turnover', 'days_on_market', 'price_per_km', 'depreciation_rate'
            ]
            
            for metric in v:
                if metric not in valid_metrics:
                    raise ValueError(f'Invalid metric: {metric}')
        
        return v


class AnalyticsResponse(BaseModel):
    """Analytics response schema."""
    
    request_id: str
    request_type: str
    date_range: Dict[str, datetime]
    data: Dict[str, Any]
    metadata: Dict[str, Any]
    generated_at: datetime
    cache_ttl: Optional[int] = None
    
    @validator('date_range')
    def validate_date_range(cls, v):
        if 'start' in v and 'end' in v:
            start_date = v['start']
            end_date = v['end']
            
            if isinstance(start_date, str):
                start_date = datetime.fromisoformat(start_date.replace('Z', '+00:00'))
            if isinstance(end_date, str):
                end_date = datetime.fromisoformat(end_date.replace('Z', '+00:00'))
            
            v['start'] = start_date
            v['end'] = end_date
        
        return v


class MarketTrendsResponse(BaseModel):
    """Market trends response schema."""
    
    overall_trend: str = Field(..., pattern="^(increasing|decreasing|stable|volatile)$")
    price_trend: Dict[str, Any]
    volume_trend: Dict[str, Any]
    seasonal_patterns: List[Dict[str, Any]]
    top_growing_makes: List[Dict[str, Any]]
    top_declining_makes: List[Dict[str, Any]]
    market_insights: List[str]
    forecast: Optional[Dict[str, Any]] = None
    confidence_score: float = Field(..., ge=0, le=1)


class PriceAnalysisResponse(BaseModel):
    """Price analysis response schema."""
    
    average_price: float
    median_price: float
    price_range: Dict[str, float]
    price_distribution: Dict[str, Any]
    price_by_make: Dict[str, float]
    price_by_model: Dict[str, float]
    price_by_year: Dict[str, float]
    price_by_location: Dict[str, float]
    price_trends: List[Dict[str, Any]]
    market_position: Dict[str, Any]
    price_factors: List[Dict[str, Any]]
    recommendations: List[str]


class MarketShareResponse(BaseModel):
    """Market share response schema."""
    
    total_listings: int
    market_share_by_make: Dict[str, float]
    market_share_by_model: Dict[str, float]
    market_share_by_location: Dict[str, float]
    market_share_by_fuel_type: Dict[str, float]
    market_share_by_transmission: Dict[str, float]
    market_share_trends: List[Dict[str, Any]]
    competitive_analysis: Dict[str, Any]
    market_leaders: List[Dict[str, Any]]


class InventoryAnalysis(BaseModel):
    """Inventory analysis schema."""
    
    total_inventory: int
    inventory_by_make: Dict[str, int]
    inventory_by_condition: Dict[str, int]
    inventory_by_year: Dict[str, int]
    inventory_by_location: Dict[str, int]
    turnover_rate: float
    days_on_market: Dict[str, float]
    aging_analysis: Dict[str, Any]
    inventory_health: Dict[str, Any]
    recommendations: List[str]


class PerformanceMetrics(BaseModel):
    """Performance metrics schema."""
    
    total_views: int
    unique_visitors: int
    page_views: int
    bounce_rate: float
    average_session_duration: float
    conversion_rate: float
    search_queries: int
    listing_views: int
    contact_requests: int
    lead_quality_score: float
    roi_metrics: Dict[str, float]


class DepreciationAnalysis(BaseModel):
    """Depreciation analysis schema."""
    
    average_depreciation_rate: float
    depreciation_by_make: Dict[str, float]
    depreciation_by_model: Dict[str, float]
    depreciation_by_year: Dict[str, float]
    depreciation_curve: List[Dict[str, Any]]
    residual_values: Dict[str, float]
    total_cost_of_ownership: Dict[str, float]
    best_retention_value: List[Dict[str, Any]]
    market_factors: List[Dict[str, Any]]


class SeasonalAnalysis(BaseModel):
    """Seasonal analysis schema."""
    
    seasonal_patterns: Dict[str, Any]
    peak_seasons: List[str]
    off_seasons: List[str]
    monthly_trends: List[Dict[str, Any]]
    quarterly_trends: List[Dict[str, Any]]
    year_over_year_comparison: Dict[str, Any]
    seasonal_forecasts: List[Dict[str, Any]]
    market_cycles: List[Dict[str, Any]]


class GeographicAnalysis(BaseModel):
    """Geographic analysis schema."""
    
    regional_distribution: Dict[str, Any]
    price_by_region: Dict[str, float]
    volume_by_region: Dict[str, int]
    market_penetration: Dict[str, float]
    regional_trends: List[Dict[str, Any]]
    hot_markets: List[Dict[str, Any]]
    emerging_markets: List[Dict[str, Any]]
    geographic_insights: List[str]


class CompetitorAnalysis(BaseModel):
    """Competitor analysis schema."""
    
    competitor_listings: int
    competitor_average_price: float
    competitor_market_share: float
    price_comparison: Dict[str, float]
    volume_comparison: Dict[str, int]
    competitive_advantages: List[str]
    competitive_threats: List[str]
    market_positioning: Dict[str, Any]
    strategic_recommendations: List[str]


class UserBehaviorAnalysis(BaseModel):
    """User behavior analysis schema."""
    
    user_segments: Dict[str, Any]
    search_patterns: List[Dict[str, Any]]
    viewing_patterns: List[Dict[str, Any]]
    conversion_funnel: Dict[str, Any]
    user_journey: List[Dict[str, Any]]
    engagement_metrics: Dict[str, float]
    retention_analysis: Dict[str, Any]
    user_insights: List[str]


class LeadAnalysis(BaseModel):
    """Lead analysis schema."""
    
    total_leads: int
    qualified_leads: int
    lead_conversion_rate: float
    lead_sources: Dict[str, int]
    lead_quality_score: float
    response_time: Dict[str, float]
    follow_up_rate: float
    lead_value: Dict[str, float]
    lead_pipeline: Dict[str, Any]


class CustomAnalyticsRequest(BaseModel):
    """Custom analytics request schema."""
    
    name: str = Field(..., min_length=1, max_length=100)
    description: Optional[str] = Field(None, max_length=500)
    metrics: List[str] = Field(..., min_items=1)
    dimensions: List[str] = Field(default_factory=list)
    filters: Dict[str, Any] = Field(default_factory=dict)
    calculations: List[Dict[str, Any]] = Field(default_factory=list)
    visualizations: List[Dict[str, Any]] = Field(default_factory=list)
    schedule: Optional[Dict[str, Any]] = None
    
    @validator('name')
    def clean_name(cls, v):
        return v.strip()
    
    @validator('metrics')
    def validate_metrics(cls, v):
        valid_metrics = [
            'total_listings', 'average_price', 'median_price', 'price_range',
            'total_views', 'unique_users', 'conversion_rate', 'market_share',
            'inventory_turnover', 'days_on_market', 'price_per_km', 'depreciation_rate'
        ]
        
        for metric in v:
            if metric not in valid_metrics:
                raise ValueError(f'Invalid metric: {metric}')
        
        return v


class AnalyticsExport(BaseModel):
    """Analytics export schema."""
    
    format: str = Field("csv", pattern="^(csv|json|excel|pdf)$")
    report_type: str = Field(..., pattern="^(overview|trends|price_analysis|market_share|performance)$")
    date_range: Dict[str, Union[str, datetime]]
    filters: Optional[Dict[str, Any]] = None
    include_charts: bool = True
    include_raw_data: bool = False
    email_recipients: Optional[List[str]] = None
    
    @validator('email_recipients')
    def validate_emails(cls, v):
        if v:
            email_pattern = r'^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$'
            for email in v:
                if not re.match(email_pattern, email):
                    raise ValueError(f'Invalid email: {email}')
        return v


class AnalyticsAlert(BaseModel):
    """Analytics alert schema."""
    
    name: str = Field(..., min_length=1, max_length=100)
    description: Optional[str] = Field(None, max_length=500)
    metric: str = Field(..., pattern="^(price|volume|conversion_rate|market_share)$")
    condition: str = Field(..., pattern="^(greater_than|less_than|equals|changes_by)$")
    threshold: Union[float, int]
    time_window: int = Field(..., ge=1, le=365)
    notification_channels: List[str] = Field(default_factory=lambda: ["email"])
    is_active: bool = True
    last_triggered: Optional[datetime] = None
    
    @validator('name')
    def clean_name(cls, v):
        return v.strip()
    
    @validator('notification_channels')
    def validate_notification_channels(cls, v):
        valid_channels = ["email", "sms", "webhook", "slack", "teams"]
        for channel in v:
            if channel not in valid_channels:
                raise ValueError(f'Invalid notification channel: {channel}')
        return v


class AnalyticsDashboard(BaseModel):
    """Analytics dashboard schema."""
    
    id: Optional[str] = None
    name: str = Field(..., min_length=1, max_length=100)
    description: Optional[str] = Field(None, max_length=500)
    widgets: List[Dict[str, Any]] = Field(..., min_items=1)
    layout: Dict[str, Any] = Field(default_factory=dict)
    filters: Optional[Dict[str, Any]] = None
    refresh_interval: int = Field(300, ge=60, le=3600)
    is_public: bool = False
    created_by: Optional[str] = None
    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None
    
    @validator('name')
    def clean_name(cls, v):
        return v.strip()
    
    @validator('widgets')
    def validate_widgets(cls, v):
        if len(v) == 0:
            raise ValueError('At least one widget must be provided')
        
        widget_types = ['chart', 'metric', 'table', 'gauge', 'map']
        for widget in v:
            if 'type' not in widget or widget['type'] not in widget_types:
                raise ValueError(f'Invalid widget type: {widget.get("type", "unknown")}')
        
        return v


class AnalyticsForecast(BaseModel):
    """Analytics forecast schema."""
    
    metric: str = Field(..., pattern="^(price|volume|conversion_rate|market_share)$")
    forecast_period: int = Field(..., ge=1, le=365)
    confidence_level: float = Field(0.95, ge=0.8, le=0.99)
    model_type: str = Field("linear", pattern="^(linear|exponential|seasonal|arima)$")
    include_seasonality: bool = True
    historical_data_points: int = Field(30, ge=10, le=365)
    
    @validator('confidence_level')
    def validate_confidence_level(cls, v):
        if v < 0.8 or v > 0.99:
            raise ValueError('Confidence level must be between 0.8 and 0.99')
        return v


class AnalyticsComparison(BaseModel):
    """Analytics comparison schema."""
    
    name: str = Field(..., min_length=1, max_length=100)
    comparison_type: str = Field(..., pattern="^(period|segment|competitor)$")
    base_period: Dict[str, Union[str, datetime]]
    comparison_periods: List[Dict[str, Union[str, datetime]]] = Field(..., min_items=1)
    metrics: List[str] = Field(..., min_items=1)
    dimensions: Optional[List[str]] = None
    
    @validator('name')
    def clean_name(cls, v):
        return v.strip()
    
    @validator('metrics')
    def validate_metrics(cls, v):
        valid_metrics = [
            'total_listings', 'average_price', 'median_price', 'price_range',
            'total_views', 'unique_users', 'conversion_rate', 'market_share',
            'inventory_turnover', 'days_on_market', 'price_per_km', 'depreciation_rate'
        ]
        
        for metric in v:
            if metric not in valid_metrics:
                raise ValueError(f'Invalid metric: {metric}')
        
        return v


class AnalyticsInsight(BaseModel):
    """Analytics insight schema."""
    
    title: str = Field(..., min_length=1, max_length=200)
    description: str = Field(..., min_length=10, max_length=1000)
    category: str = Field(..., pattern="^(pricing|inventory|market|performance|trend)$")
    severity: str = Field("medium", pattern="^(low|medium|high|critical)$")
    confidence: float = Field(..., ge=0, le=1)
    impact: str = Field(..., pattern="^(low|medium|high)$")
    actionable: bool = True
    recommendations: List[str] = Field(..., min_items=1)
    supporting_data: Dict[str, Any] = Field(default_factory=dict)
    generated_at: datetime
    expires_at: Optional[datetime] = None
    
    @validator('title')
    def clean_title(cls, v):
        return v.strip()
    
    @validator('description')
    def clean_description(cls, v):
        return v.strip()


class AnalyticsReport(BaseModel):
    """Analytics report schema."""
    
    id: Optional[str] = None
    title: str = Field(..., min_length=1, max_length=200)
    description: Optional[str] = Field(None, max_length=500)
    report_type: str = Field(..., pattern="^(overview|trends|price_analysis|market_share|performance)$")
    parameters: Dict[str, Any] = Field(default_factory=dict)
    sections: List[Dict[str, Any]] = Field(..., min_items=1)
    generated_at: datetime
    generated_by: Optional[str] = None
    file_path: Optional[str] = None
    is_public: bool = False
    
    @validator('title')
    def clean_title(cls, v):
        return v.strip()
    
    @validator('sections')
    def validate_sections(cls, v):
        if len(v) == 0:
            raise ValueError('At least one section must be provided')
        
        for section in v:
            if 'title' not in section or 'content' not in section:
                raise ValueError('Each section must have title and content')
        
        return v


class AnalyticsMetrics(BaseModel):
    """Analytics metrics schema."""
    
    metric_name: str = Field(..., min_length=1)
    metric_value: Union[int, float, str]
    metric_type: str = Field(..., pattern="^(count|sum|average|median|percentage|ratio)$")
    unit: Optional[str] = None
    trend: Optional[str] = Field(None, pattern="^(up|down|stable)$")
    trend_percentage: Optional[float] = None
    comparison_period: Optional[str] = None
    last_updated: datetime
    
    @validator('metric_name')
    def clean_metric_name(cls, v):
        return v.strip().lower().replace(' ', '_')
    
    @validator('trend_percentage')
    def validate_trend_percentage(cls, v):
        if v is not None and (v < -100 or v > 100):
            raise ValueError('Trend percentage must be between -100 and 100')
        return v


class AnalyticsConfiguration(BaseModel):
    """Analytics configuration schema."""
    
    data_retention_days: int = Field(365, ge=30, le=3650)
    cache_ttl_minutes: int = Field(60, ge=5, le=1440)
    max_concurrent_reports: int = Field(10, ge=1, le=100)
    enable_forecasting: bool = True
    enable_alerts: bool = True
    default_confidence_level: float = Field(0.95, ge=0.8, le=0.99)
    alert_thresholds: Dict[str, Union[float, int]] = Field(default_factory=dict)
    notification_settings: Dict[str, Any] = Field(default_factory=dict)
    
    @validator('default_confidence_level')
    def validate_confidence_level(cls, v):
        if v < 0.8 or v > 0.99:
            raise ValueError('Default confidence level must be between 0.8 and 0.99')
        return v

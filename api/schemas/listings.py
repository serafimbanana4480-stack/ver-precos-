"""
Listings schemas for API.
"""
from typing import Optional, List, Dict, Any
from datetime import datetime
from pydantic import BaseModel, Field, validator
import re


class BaseListing(BaseModel):
    """Base listing schema."""
    
    title: Optional[str] = None
    make: Optional[str] = None
    model: Optional[str] = None
    year: Optional[int] = None
    price: Optional[float] = None
    mileage: Optional[int] = None
    fuel_type: Optional[str] = None
    transmission: Optional[str] = None
    engine_size: Optional[float] = None
    location: Optional[str] = None
    condition: Optional[str] = None
    description: Optional[str] = None
    image_url: Optional[str] = None
    seller_name: Optional[str] = None
    seller_type: Optional[str] = None
    source: Optional[str] = None
    scraped_at: Optional[datetime] = None
    
    class Config:
        from_attributes = True


class ListingResponse(BaseListing):
    """Listing response schema."""
    
    id: str
    url: Optional[str] = None
    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None
    
    @validator('price')
    def validate_price(cls, v):
        if v is not None and (v < 0 or v > 1000000):
            raise ValueError('Price must be between 0 and 1000000')
        return v
    
    @validator('year')
    def validate_year(cls, v):
        if v is not None and (v < 1900 or v > datetime.now().year + 1):
            raise ValueError('Year must be between 1900 and current year + 1')
        return v
    
    @validator('mileage')
    def validate_mileage(cls, v):
        if v is not None and (v < 0 or v > 500000):
            raise ValueError('Mileage must be between 0 and 500000')
        return v
    
    @validator('engine_size')
    def validate_engine_size(cls, v):
        if v is not None and (v < 0.5 or v > 10.0):
            raise ValueError('Engine size must be between 0.5 and 10.0')
        return v
    
    @validator('fuel_type')
    def validate_fuel_type(cls, v):
        if v is not None:
            valid_fuels = ['Gasoline', 'Diesel', 'Electric', 'Hybrid', 'LPG', 'CNG', 'Unknown']
            if v not in valid_fuels:
                raise ValueError(f'Fuel type must be one of: {valid_fuels}')
        return v
    
    @validator('transmission')
    def validate_transmission(cls, v):
        if v is not None:
            valid_transmissions = ['Automatic', 'Manual', 'CVT', 'Tiptronic', 'DSG', 'Unknown']
            if v not in valid_transmissions:
                raise ValueError(f'Transmission must be one of: {valid_transmissions}')
        return v
    
    @validator('condition')
    def validate_condition(cls, v):
        if v is not None:
            valid_conditions = ['Excellent', 'Good', 'Fair', 'Poor', 'Unknown']
            if v not in valid_conditions:
                raise ValueError(f'Condition must be one of: {valid_conditions}')
        return v


class ListingCreate(BaseListing):
    """Listing creation schema."""
    
    title: str = Field(..., min_length=1, max_length=200)
    make: str = Field(..., min_length=1, max_length=50)
    model: str = Field(..., min_length=1, max_length=50)
    year: int = Field(..., ge=1900, le=datetime.now().year + 1)
    price: float = Field(..., gt=0, le=1000000)
    mileage: int = Field(..., ge=0, le=500000)
    fuel_type: str = Field(..., description="Fuel type")
    transmission: Optional[str] = None
    engine_size: Optional[float] = Field(None, ge=0.5, le=10.0)
    location: Optional[str] = Field(None, max_length=100)
    condition: Optional[str] = None
    description: Optional[str] = Field(None, max_length=2000)
    image_url: Optional[str] = None
    seller_name: Optional[str] = Field(None, max_length=100)
    seller_type: Optional[str] = None
    source: str = Field(..., max_length=50)
    url: Optional[str] = None
    
    @validator('title')
    def clean_title(cls, v):
        return v.strip().title()
    
    @validator('make')
    def clean_make(cls, v):
        return v.strip().title()
    
    @validator('model')
    def clean_model(cls, v):
        return v.strip().title()
    
    @validator('location')
    def clean_location(cls, v):
        if v:
            return v.strip().title()
        return v
    
    @validator('description')
    def clean_description(cls, v):
        if v:
            # Remove excessive whitespace
            v = re.sub(r'\s+', ' ', v.strip())
        return v


class ListingUpdate(BaseModel):
    """Listing update schema."""
    
    title: Optional[str] = Field(None, min_length=1, max_length=200)
    make: Optional[str] = Field(None, min_length=1, max_length=50)
    model: Optional[str] = Field(None, min_length=1, max_length=50)
    year: Optional[int] = Field(None, ge=1900, le=datetime.now().year + 1)
    price: Optional[float] = Field(None, gt=0, le=1000000)
    mileage: Optional[int] = Field(None, ge=0, le=500000)
    fuel_type: Optional[str] = None
    transmission: Optional[str] = None
    engine_size: Optional[float] = Field(None, ge=0.5, le=10.0)
    location: Optional[str] = Field(None, max_length=100)
    condition: Optional[str] = None
    description: Optional[str] = Field(None, max_length=2000)
    image_url: Optional[str] = None
    seller_name: Optional[str] = Field(None, max_length=100)
    seller_type: Optional[str] = None
    url: Optional[str] = None
    
    @validator('title')
    def clean_title(cls, v):
        if v:
            return v.strip().title()
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


class ListingFilter(BaseModel):
    """Listing filter schema."""
    
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
    keywords: Optional[str] = None
    
    @validator('keywords')
    def split_keywords(cls, v):
        if v:
            return [kw.strip() for kw in v.split(',') if kw.strip()]
        return []


class ListingBulkCreate(BaseModel):
    """Bulk listing creation schema."""
    
    listings: List[ListingCreate] = Field(..., max_items=1000)
    
    @validator('listings')
    def validate_listings_count(cls, v):
        if len(v) == 0:
            raise ValueError('At least one listing must be provided')
        return v


class ListingBulkUpdate(BaseModel):
    """Bulk listing update schema."""
    
    listing_ids: List[str] = Field(..., max_items=1000)
    updates: ListingUpdate
    
    @validator('listing_ids')
    def validate_listing_ids_count(cls, v):
        if len(v) == 0:
            raise ValueError('At least one listing ID must be provided')
        return v


class ListingBulkDelete(BaseModel):
    """Bulk listing deletion schema."""
    
    listing_ids: List[str] = Field(..., max_items=1000)
    
    @validator('listing_ids')
    def validate_listing_ids_count(cls, v):
        if len(v) == 0:
            raise ValueError('At least one listing ID must be provided')
        return v


class ListingSearch(BaseModel):
    """Listing search schema."""
    
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
    sort_by: Optional[str] = Field("scraped_at", pattern="^(price|year|mileage|scraped_at)$")
    sort_order: Optional[str] = Field("desc", pattern="^(asc|desc)$")
    limit: int = Field(20, ge=1, le=100)
    offset: int = Field(0, ge=0)


class ListingComparison(BaseModel):
    """Listing comparison schema."""
    
    listing_ids: List[str] = Field(..., min_items=2, max_items=10)
    
    @validator('listing_ids')
    def validate_listing_ids_count(cls, v):
        if len(v) < 2:
            raise ValueError('At least 2 listings must be provided for comparison')
        return v


class SimilarListingsRequest(BaseModel):
    """Similar listings request schema."""
    
    listing_id: str = Field(..., min_length=1)
    limit: int = Field(10, ge=1, le=50)
    include_different_makes: bool = False
    price_variance: float = Field(0.2, ge=0, le=1.0)


class FeaturedListingsRequest(BaseModel):
    """Featured listings request schema."""
    
    limit: int = Field(20, ge=1, le=100)
    make: Optional[str] = None
    max_price: Optional[float] = Field(None, le=1000000)
    min_year: Optional[int] = Field(None, ge=1900)


class RecentListingsRequest(BaseModel):
    """Recent listings request schema."""
    
    hours: int = Field(24, ge=1, le=168)
    limit: int = Field(50, ge=1, le=200)
    make: Optional[str] = None


class ListingAnalytics(BaseModel):
    """Listing analytics schema."""
    
    make: Optional[str] = None
    model: Optional[str] = None
    year: Optional[int] = None
    location: Optional[str] = None
    days: int = Field(30, ge=1, le=365)
    include_price_trends: bool = True
    include_mileage_analysis: bool = True


class ListingExport(BaseModel):
    """Listing export schema."""
    
    format: str = Field("csv", pattern="^(csv|json|excel)$")
    filters: Optional[ListingFilter] = None
    fields: Optional[List[str]] = None
    include_images: bool = False


class ListingImport(BaseModel):
    """Listing import schema."""
    
    file_path: str = Field(..., min_length=1)
    format: str = Field("csv", pattern="^(csv|json|excel)$")
    overwrite_existing: bool = False
    validate_data: bool = True


class ListingValidation(BaseModel):
    """Listing validation schema."""
    
    listing: ListingCreate
    strict_mode: bool = False
    check_duplicates: bool = True


class ListingEnrichment(BaseModel):
    """Listing enrichment schema."""
    
    listing_id: str = Field(..., min_length=1)
    enrich_images: bool = True
    enrich_description: bool = True
    extract_features: bool = True
    calculate_scores: bool = True


class ListingRecommendation(BaseModel):
    """Listing recommendation schema."""
    
    user_id: Optional[str] = None
    listing_id: Optional[str] = None
    preferences: Optional[Dict[str, Any]] = None
    limit: int = Field(10, ge=1, le=50)
    include_reasoning: bool = False


class ListingAlert(BaseModel):
    """Listing alert schema."""
    
    name: str = Field(..., min_length=1, max_length=100)
    filters: ListingFilter
    notification_methods: List[str] = Field(default=["email"])
    is_active: bool = True
    
    @validator('notification_methods')
    def validate_notification_methods(cls, v):
        valid_methods = ["email", "sms", "push", "webhook"]
        for method in v:
            if method not in valid_methods:
                raise ValueError(f'Invalid notification method: {method}')
        return v


class ListingFavorite(BaseModel):
    """Listing favorite schema."""
    
    listing_id: str = Field(..., min_length=1)
    user_id: Optional[str] = None
    notes: Optional[str] = Field(None, max_length=500)


class ListingShare(BaseModel):
    """Listing share schema."""
    
    listing_id: str = Field(..., min_length=1)
    share_method: str = Field("link", pattern="^(link|email|social)$")
    recipient: Optional[str] = None
    message: Optional[str] = Field(None, max_length=1000)


class ListingReview(BaseModel):
    """Listing review schema."""
    
    listing_id: str = Field(..., min_length=1)
    rating: int = Field(..., ge=1, le=5)
    title: str = Field(..., min_length=1, max_length=200)
    content: str = Field(..., min_length=10, max_length=1000)
    user_id: Optional[str] = None


class ListingReport(BaseModel):
    """Listing report schema."""
    
    listing_id: str = Field(..., min_length=1)
    reason: str = Field(..., min_length=10, max_length=500)
    description: Optional[str] = Field(None, max_length=1000)
    user_id: Optional[str] = None


class ListingStats(BaseModel):
    """Listing statistics schema."""
    
    total_listings: int
    average_price: float
    median_price: float
    price_range: Dict[str, float]
    top_makes: List[Dict[str, Any]]
    top_models: List[Dict[str, Any]]
    listings_by_source: Dict[str, int]
    listings_by_condition: Dict[str, int]
    listings_by_fuel_type: Dict[str, int]
    listings_by_transmission: Dict[str, int]
    listings_by_year: Dict[str, int]
    price_trends: List[Dict[str, Any]]
    mileage_distribution: Dict[str, int]
    location_distribution: Dict[str, int]

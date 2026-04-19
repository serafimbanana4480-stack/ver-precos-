"""
Scraped data validation models using pydantic

NOTE: ScrapedVehicle is intentionally lenient — it validates INITIAL scrape data
where many fields are missing. Enrichment (brand/model parsing, detail scraping)
happens after initial save. Strict validation belongs at the DB/export layer.
"""
from __future__ import annotations
from typing import Optional, List, Dict, Any
from datetime import datetime
from pydantic import BaseModel, Field, field_validator, ConfigDict
from enum import Enum


class VehicleType(str, Enum):
    CAR = "car"
    MOTO = "moto"


class FuelType(str, Enum):
    GASOLINE = "gasolina"
    DIESEL = "diesel"
    ELECTRIC = "eletrico"
    HYBRID = "hibrido"
    GPL = "gpl"
    GAS_NATURAL = "gas natural"


class Transmission(str, Enum):
    MANUAL = "manual"
    AUTOMATIC = "automatico"
    SEMI_AUTOMATIC = "semi-automatico"


class Source(str, Enum):
    OLX = "olx"
    STANDVIRTUAL = "standvirtual"
    AUTOSAPO = "autosapo"


class ScrapedVehicle(BaseModel):
    """Validation model for scraped vehicle data.
    
    This model is used for INITIAL scraping validation.
    Many fields are Optional because listing cards don't always
    contain all vehicle details. Data enrichment (brand/model parsing,
    detail page scraping) happens after initial save.
    """
    model_config = ConfigDict(extra='allow')
    
    # Required fields - must have at minimum a URL and title
    url: str
    title: str = ""
    source_id: str = ""
    
    # Fields that get enriched after initial scrape
    source: Optional[str] = None
    vehicle_type: Optional[str] = None
    brand: Optional[str] = None
    model: Optional[str] = None
    version: Optional[str] = None
    
    # Fields that may or may not be available from listing cards
    year: Optional[int] = Field(default=None, description="Vehicle year")
    km: Optional[int] = Field(default=None, ge=0, description="Kilometers must be >= 0")
    horsepower: Optional[int] = Field(default=None, ge=0)
    engine_size: Optional[int] = Field(default=None, ge=0)
    fuel_type: Optional[str] = None
    transmission: Optional[str] = None
    doors: Optional[int] = Field(default=None, ge=0)
    seats: Optional[int] = Field(default=None, ge=0)
    color: Optional[str] = None
    location: Optional[str] = None
    district: Optional[str] = None
    price: Optional[float] = Field(default=None, description="Price in EUR")
    description: Optional[str] = None
    images: Optional[List[str]] = None
    image_count: int = Field(default=0, ge=0)
    
    @classmethod
    def with_overrides(cls, data: Dict[str, Any], overrides: Optional[Dict[str, Any]] = None) -> 'ScrapedVehicle':
        """Create instance with optional validation overrides"""
        if overrides:
            for key, value in overrides.items():
                if key in data:
                    data[key] = value
        return cls(**data)
    
    @field_validator('source', mode='before')
    @classmethod
    def validate_source(cls, v: str | None) -> str | None:
        if v is None or v == "":
            return None
        valid_sources = ["olx", "standvirtual", "autosapo"]
        if v.lower() not in valid_sources:
            return None
        return v.lower()
    
    @field_validator('vehicle_type', mode='before')
    @classmethod
    def validate_vehicle_type(cls, v: str | None) -> str | None:
        if v is None or v == "":
            return None
        valid_types = ["car", "moto", "carros", "motos"]
        if v.lower() not in valid_types:
            return None
        return "car" if v.lower() in ["car", "carros"] else "moto"
    
    @field_validator('brand', mode='before')
    @classmethod
    def validate_brand(cls, v: str | None) -> str | None:
        if v is None or (isinstance(v, str) and len(v.strip()) == 0):
            return None
        return v.strip()
    
    @field_validator('model', mode='before')
    @classmethod
    def validate_model(cls, v: str | None) -> str | None:
        if v is None or (isinstance(v, str) and len(v.strip()) == 0):
            return None
        return v.strip()
    
    @field_validator('year', mode='before')
    @classmethod
    def validate_year(cls, v: Any) -> int | None:
        if v is None:
            return None
        try:
            year = int(v)
            if 1980 <= year <= 2030:
                return year
        except (ValueError, TypeError):
            pass
        return None
    
    @field_validator('price', mode='before')
    @classmethod
    def validate_price(cls, v: Any) -> float | None:
        if v is None:
            return None
        try:
            price = float(v)
            if price > 0:
                return price
        except (ValueError, TypeError):
            pass
        return None
    
    @field_validator('fuel_type', mode='before')
    @classmethod
    def validate_fuel_type(cls, v: str | None) -> str | None:
        if v is None or v == "":
            return None
        valid_types = ["gasolina", "diesel", "eletrico", "hibrido", "gpl", "gas natural"]
        if isinstance(v, str) and v.lower() in valid_types:
            return v.lower()
        return None
    
    @field_validator('transmission', mode='before')
    @classmethod
    def validate_transmission(cls, v: str | None) -> str | None:
        if v is None or v == "":
            return None
        valid_types = ["manual", "automatico", "semi-automatico"]
        if isinstance(v, str) and v.lower() in valid_types:
            return v.lower()
        return None
    
    @field_validator('url')
    @classmethod
    def validate_url(cls, v: str) -> str:
        if not v or len(v.strip()) == 0:
            raise ValueError("url cannot be empty")
        if not v.startswith(('http://', 'https://')):
            raise ValueError("url must start with http:// or https://")
        if 'example.com' in v.lower():
            raise ValueError("url appears to be a test/fake URL")
        return v.strip()


class ScrapedPriceHistory(BaseModel):
    """Validation model for scraped price history"""
    vehicle_id: int = Field(gt=0, description="Vehicle ID must be > 0")
    price: float = Field(gt=0, description="Price must be > 0")
    recorded_at: datetime = Field(default_factory=datetime.utcnow)
    source: Optional[str] = None
    
    @field_validator('source')
    @classmethod
    def validate_source(cls, v: str | None) -> str | None:
        if v is None:
            return None
        valid_sources = ["olx", "standvirtual", "autosapo"]
        if v.lower() not in valid_sources:
            raise ValueError(f"source must be one of {valid_sources}")
        return v.lower()

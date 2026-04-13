"""
Scraped data validation models using pydantic
"""
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
    """Validation model for scraped vehicle data"""
    model_config = ConfigDict(extra='allow')
    
    source: str
    source_id: str
    url: str
    vehicle_type: str
    brand: str
    model: str
    version: Optional[str] = None
    year: int = Field(gt=1989, description="Vehicle year must be >= 1990")
    km: Optional[int] = Field(default=None, ge=0, description="Kilometers must be >= 0")
    horsepower: Optional[int] = Field(default=None, ge=0, description="Horsepower must be >= 0")
    engine_size: Optional[int] = Field(default=None, ge=0, description="Engine size in cc must be >= 0")
    fuel_type: Optional[str] = None
    transmission: Optional[str] = None
    doors: Optional[int] = Field(default=None, ge=0, description="Doors must be >= 0")
    seats: Optional[int] = Field(default=None, ge=0, description="Seats must be >= 0")
    color: Optional[str] = None
    location: Optional[str] = None
    district: Optional[str] = None
    price: float = Field(gt=0, description="Price must be > 0")
    title: str
    description: Optional[str] = None
    images: Optional[List[str]] = None
    image_count: int = Field(default=0, ge=0, description="Image count must be >= 0")
    
    @classmethod
    def with_overrides(cls, data: Dict[str, Any], overrides: Optional[Dict[str, Any]] = None) -> 'ScrapedVehicle':
        """Create instance with optional validation overrides"""
        if overrides:
            # Apply overrides to data before validation
            for key, value in overrides.items():
                if key in data:
                    data[key] = value
        return cls(**data)
    
    @field_validator('source')
    @classmethod
    def validate_source(cls, v):
        valid_sources = ["olx", "standvirtual", "autosapo"]
        if v.lower() not in valid_sources:
            raise ValueError(f"source must be one of {valid_sources}")
        return v.lower()
    
    @field_validator('vehicle_type')
    @classmethod
    def validate_vehicle_type(cls, v):
        valid_types = ["car", "moto", "carros", "motos"]
        if v.lower() not in valid_types:
            raise ValueError(f"vehicle_type must be one of {valid_types}")
        # Normalize to enum values
        return "car" if v.lower() in ["car", "carros"] else "moto"
    
    @field_validator('brand')
    @classmethod
    def validate_brand(cls, v):
        known_brands = [
            "Volkswagen", "Renault", "Peugeot", "Citroen", "Ford", "Toyota", 
            "Honda", "BMW", "Mercedes", "Audi", "Opel", "Fiat", "Seat", "Skoda",
            "Nissan", "Hyundai", "Kia", "Mazda", "Suzuki", "Mitsubishi", "Volvo"
        ]
        if not v or len(v.strip()) == 0:
            raise ValueError("brand cannot be empty")
        # Warn if brand not in known list (don't fail to allow new brands)
        if v not in known_brands:
            # Log warning in actual implementation
            pass
        return v.strip()
    
    @field_validator('model')
    @classmethod
    def validate_model(cls, v):
        if not v or len(v.strip()) == 0:
            raise ValueError("model cannot be empty")
        return v.strip()
    
    @field_validator('fuel_type')
    @classmethod
    def validate_fuel_type(cls, v):
        if v is None:
            return None
        valid_types = ["gasolina", "diesel", "eletrico", "hibrido", "gpl", "gas natural"]
        if v.lower() not in valid_types:
            raise ValueError(f"fuel_type must be one of {valid_types}")
        return v.lower()
    
    @field_validator('transmission')
    @classmethod
    def validate_transmission(cls, v):
        if v is None:
            return None
        valid_types = ["manual", "automatico", "semi-automatico"]
        if v.lower() not in valid_types:
            raise ValueError(f"transmission must be one of {valid_types}")
        return v.lower()
    
    @field_validator('url')
    @classmethod
    def validate_url(cls, v):
        if not v or len(v.strip()) == 0:
            raise ValueError("url cannot be empty")
        if not v.startswith(('http://', 'https://')):
            raise ValueError("url must start with http:// or https://")
        return v.strip()


class ScrapedPriceHistory(BaseModel):
    """Validation model for scraped price history"""
    vehicle_id: int = Field(gt=0, description="Vehicle ID must be > 0")
    price: float = Field(gt=0, description="Price must be > 0")
    recorded_at: datetime = Field(default_factory=datetime.utcnow)
    source: Optional[str] = None
    
    @field_validator('source')
    @classmethod
    def validate_source(cls, v):
        if v is None:
            return None
        valid_sources = ["olx", "standvirtual", "autosapo"]
        if v.lower() not in valid_sources:
            raise ValueError(f"source must be one of {valid_sources}")
        return v.lower()

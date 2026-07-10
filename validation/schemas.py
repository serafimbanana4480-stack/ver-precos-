"""
Pydantic Schemas for Data Validation
Production-grade data validation layer
"""
from __future__ import annotations
from typing import Optional, List, Dict, Any
from datetime import datetime
from enum import Enum
from pydantic import BaseModel, Field, field_validator, HttpUrl, ConfigDict
from decimal import Decimal


class VehicleType(str, Enum):
    carros = "carros"
    motos = "motos"


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
    OLX = "OLX"
    STANDVIRTUAL = "STANDVIRTUAL"
    AUTOSAPO = "AUTOSAPO"
    CUSTOJUSTO = "CUSTOJUSTO"
    AUTOPT = "AUTOPT"
    PISCAPISCA = "PISCAPISCA"
    CARPLUS = "CARPLUS"
    AUTOSCOUT24 = "AUTOSCOUT24"
    EBAY_MOTORS = "EBAY_MOTORS"
    VPAUTO = "VPAUTO"
    LEILOSOC = "LEILOSOC"
    MANHEIM = "MANHEIM"
    AUTOROLA = "AUTOROLA"
    BCA = "BCA"


class ScrapedVehicle(BaseModel):
    """Schema for scraped vehicle data with validation"""
    
    # Required fields
    source: Source
    source_id: str = Field(..., min_length=1, max_length=100)
    url: HttpUrl
    title: str = Field(..., min_length=5, max_length=500)
    brand: str = Field(..., min_length=1, max_length=100)
    model: str = Field(..., min_length=2, max_length=100)
    year: Optional[int] = Field(None, ge=1990, le=2026)
    price: float = Field(..., gt=0, lt=1000000)
    vehicle_type: VehicleType
    
    # Optional but important fields
    version: Optional[str] = Field(None, max_length=200)
    km: Optional[int] = Field(None, ge=0, le=500000)
    horsepower: Optional[int] = Field(None, ge=50, le=1000)
    engine_size: Optional[int] = Field(None, ge=500, le=8000)
    fuel_type: Optional[FuelType] = None
    transmission: Optional[Transmission] = None
    doors: Optional[int] = Field(None, ge=2, le=5)
    seats: Optional[int] = Field(None, ge=2, le=9)
    color: Optional[str] = Field(None, max_length=50)
    
    # Location
    location: Optional[str] = Field(None, max_length=200)
    district: Optional[str] = Field(None, max_length=100)
    
    # Description and media
    description: Optional[str] = Field(None, max_length=10000)
    images: Optional[List[str]] = Field(default_factory=list)
    
    # Seller info
    seller_name: Optional[str] = Field(None, max_length=200)
    seller_type: Optional[str] = Field(None, pattern="^(particular|profissional|dealer|individual|private|)$")
    
    # Extras and features
    extras: Optional[List[str]] = Field(default_factory=list)
    features: Optional[Dict[str, Any]] = Field(default_factory=dict)
    
    model_config = ConfigDict(
        json_encoders={
            datetime: lambda v: v.isoformat(),
        }
    )

    @field_validator('source', mode='before')
    @classmethod
    def normalize_source_field(cls, v):
        if v is None:
            return None
        # Normalize to match Source enum values
        v_str = str(v).strip()
        # Handle common lowercase variants
        normalize_map = {
            "olx": "OLX",
            "standvirtual": "STANDVIRTUAL",
            "autosapo": "AUTOSAPO",
            "custojusto": "CUSTOJUSTO",
            "piscapisca": "PISCAPISCA",
            "carplus": "CARPLUS",
            "autopt": "AUTOPT",
            "autoscout24": "AUTOSCOUT24",
            "ebay_motors": "EBAY_MOTORS",
            "vpauto": "VPAUTO",
            "leilosoc": "LEILOSOC",
            "manheim": "MANHEIM",
            "autorola": "AUTOROLA",
            "bca": "BCA",
        }
        v_lower = v_str.lower()
        if v_lower in normalize_map:
            return normalize_map[v_lower]
        # Try uppercase with underscore replacement
        v_upper = v_str.upper().replace(" ", "_")
        # Check if it's already a valid enum value
        from validation.scraped_models import Source
        if v_upper in [e.value for e in Source]:
            return v_upper
        # Return as-is and let Pydantic handle the error
        return v_str

    @field_validator('transmission', mode='before')
    @classmethod
    def normalize_transmission_field(cls, v):
        if v is None:
            return None
        from validation.normalizers import normalize_transmission
        return normalize_transmission(v)

    @field_validator('fuel_type', mode='before')
    @classmethod
    def normalize_fuel_type_field(cls, v):
        if v is None:
            return None
        from validation.normalizers import normalize_fuel_type
        return normalize_fuel_type(v)

    @field_validator('vehicle_type', mode='before')
    @classmethod
    def normalize_vehicle_type_field(cls, v):
        if v is None:
            return None
        from validation.normalizers import normalize_vehicle_type
        return normalize_vehicle_type(v)

    @field_validator('seller_type', mode='before')
    @classmethod
    def normalize_seller_type_field(cls, v):
        if v is None:
            return None
        from validation.normalizers import normalize_seller_type
        return normalize_seller_type(v)
    
    @field_validator('km')
    @classmethod
    def validate_km(cls, v, info):
        """KM is required for cars, optional for motos"""
        if v is None and info.data.get('vehicle_type') == VehicleType.carros:
            raise ValueError('KM is required for cars')
        return v
    
    @field_validator('images')
    @classmethod
    def validate_images(cls, v):
        """Validate image URLs"""
        if v:
            for img_url in v:
                if not img_url.startswith(('http://', 'https://')):
                    raise ValueError(f'Invalid image URL: {img_url}')
        return v
    
    @field_validator('price')
    @classmethod
    def validate_price(cls, v, info):
        """Validate price is reasonable for vehicle type"""
        if info.data.get('vehicle_type') == VehicleType.carros:
            if v < 100:  # Minimum realistic car price
                raise ValueError('Price too low for car (possible deposit)')
        elif info.data.get('vehicle_type') == VehicleType.motos:
            if v < 50:  # Minimum realistic moto price
                raise ValueError('Price too low for moto (possible deposit)')
        return v
    
    @field_validator('year')
    @classmethod
    def validate_year(cls, v):
        """Validate year is not in the future"""
        current_year = datetime.now().year
        if v > current_year + 1:
            raise ValueError(f'Year {v} is in the future')
        return v


class AIAnalysisResult(BaseModel):
    """Schema for AI analysis results"""
    
    # LLM Analysis
    llm_red_flags: List[str] = Field(default_factory=list)
    llm_value_adding_features: List[str] = Field(default_factory=list)
    llm_market_position: str = Field(..., pattern="^(underpriced|fair|overpriced)$")
    llm_risk_score: float = Field(..., ge=0, le=10)
    llm_recommendation: str = Field(..., pattern="^(APPROVED|REJECTED|CAUTION)$")
    llm_confidence: float = Field(..., ge=0, le=1)
    llm_reasoning: str = Field(..., min_length=1, max_length=5000)

    @field_validator('llm_reasoning')
    @classmethod
    def ensure_reasoning_length(cls, v):
        if not v or len(v) < 10:
            return (v or "") + " [Análise gerada automaticamente pelo sistema AutoDeal]"
        return v
    
    # Vision Analysis
    vision_exterior_damage: List[str] = Field(default_factory=list)
    vision_accident_indicators: List[str] = Field(default_factory=list)
    vision_tire_condition: str = Field(..., min_length=1, max_length=50)
    vision_interior_condition: str = Field(..., min_length=1, max_length=50)
    vision_condition_score: float = Field(..., ge=0, le=10)
    vision_major_concerns: List[str] = Field(default_factory=list)
    vision_confidence: float = Field(..., ge=0, le=1)
    
    # Metadata
    processing_time_llm: float = Field(..., ge=0)
    processing_time_vision: float = Field(..., ge=0)
    models_used: Dict[str, str] = Field(default_factory=dict)
    created_at: datetime = Field(default_factory=datetime.utcnow)


class VehicleWithAI(ScrapedVehicle):
    """Extended vehicle schema with AI analysis"""
    
    # AI Analysis
    ai_analysis: Optional[AIAnalysisResult] = None
    
    # AI-derived fields
    ai_risk_score: Optional[float] = Field(None, ge=0, le=10)
    ai_condition_score: Optional[float] = Field(None, ge=0, le=10)
    ai_recommendation: Optional[str] = Field(None, pattern="^(APPROVED|REJECTED|CAUTION)$")
    
    # Damage detection
    detected_damages: List[str] = Field(default_factory=list)
    has_accident_indicators: bool = False


class PricingResult(BaseModel):
    """Schema for pricing calculation results"""
    
    # Statistical pricing
    statistical_price: Optional[float] = None
    statistical_comparables_count: int = 0
    
    # Comparable clustering
    comparable_price: Optional[float] = None
    comparable_cluster_size: int = 0
    
    # ML pricing (only if valid model)
    ml_price: Optional[float] = None
    ml_confidence: Optional[float] = None
    ml_model_version: Optional[str] = None
    
    # AI reasoning adjustment
    ai_adjustment: float = 0.0
    ai_adjustment_reason: str = ""
    
    # Final hybrid price
    final_price: float
    price_components: Dict[str, float] = Field(default_factory=dict)
    
    # Metadata
    calculated_at: datetime = Field(default_factory=datetime.utcnow)
    calculation_method: str = "hybrid"


class DealScore(BaseModel):
    """Schema for deal scoring"""
    
    # Component scores
    market_deviation_score: float = Field(..., ge=0, le=10)
    ai_risk_score: float = Field(..., ge=0, le=10)
    vision_damage_score: float = Field(..., ge=0, le=10)
    price_anomaly_score: float = Field(..., ge=0, le=10)
    demand_signal_score: float = Field(..., ge=0, le=10)
    
    # Final score
    final_score: float = Field(..., ge=0, le=10)
    
    # Interpretation
    score_interpretation: str = Field(..., pattern="^(Exceptional Deal|Excellent Deal|Very Good Deal|Good Deal|Fair Deal|Poor Deal/Risk)$")
    recommended_action: str = Field(..., pattern="^(Immediate Alert|Alert|Monitor|No Action|Ignore)$")
    
    # Metadata
    calculated_at: datetime = Field(default_factory=datetime.utcnow)


class ValidationResult(BaseModel):
    """Schema for validation results"""
    
    is_valid: bool
    errors: List[str] = Field(default_factory=list)
    warnings: List[str] = Field(default_factory=list)
    missing_fields: List[str] = Field(default_factory=list)
    data_quality_score: float = Field(..., ge=0, le=1)
    
    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "is_valid": True,
                "errors": [],
                "warnings": ["KM field missing for car"],
                "missing_fields": ["km"],
                "data_quality_score": 0.8
            }
        }
    )

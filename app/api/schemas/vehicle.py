"""
Vehicle Schemas for API
Pydantic models for vehicle-related API requests and responses
"""
from __future__ import annotations
from typing import Optional, List
from pydantic import BaseModel, Field, ConfigDict
from datetime import datetime


class VehicleRequest(BaseModel):
    """Request schema for vehicle valuation"""
    brand: str = Field(..., description="Vehicle brand")
    model: str = Field(..., description="Vehicle model")
    year: int = Field(..., ge=1990, le=2026, description="Vehicle year")
    km: Optional[int] = Field(None, ge=0, description="Kilometers")
    price: float = Field(..., gt=0, description="Asking price")
    fuel_type: Optional[str] = Field(None, description="Fuel type")
    transmission: Optional[str] = Field(None, description="Transmission type")
    vehicle_type: str = Field(default="carros", description="Vehicle type (carros/motos)")
    description: Optional[str] = Field(None, description="Vehicle description")
    location: Optional[str] = Field(None, description="Vehicle location")


class ProcessVehicleRequest(BaseModel):
    """Request schema for processing a vehicle through the full pipeline"""
    source: str = Field(..., description="Source name (e.g. olx, standvirtual)")
    source_id: str = Field(..., description="Unique identifier from source")
    url: str = Field(..., description="Vehicle listing URL")
    title: str = Field(..., description="Vehicle title")
    brand: str = Field(..., description="Vehicle brand")
    model: str = Field(..., description="Vehicle model")
    year: int = Field(..., ge=1990, le=2026, description="Vehicle year")
    km: Optional[int] = Field(None, ge=0, description="Kilometers")
    price: float = Field(..., gt=0, description="Asking price")
    fuel_type: Optional[str] = Field(None, description="Fuel type")
    transmission: Optional[str] = Field(None, description="Transmission type")
    vehicle_type: str = Field(default="carros", description="Vehicle type (carros/motos)")
    description: Optional[str] = Field(None, description="Vehicle description")
    location: Optional[str] = Field(None, description="Vehicle location")
    district: Optional[str] = Field(None, description="Vehicle district")
    images: List[str] = Field(default_factory=list, description="Vehicle image URLs")


class VehicleResponse(BaseModel):
    """Response schema for vehicle data"""
    id: Optional[int] = None
    source: Optional[str] = None
    source_id: Optional[str] = None
    url: Optional[str] = None
    title: Optional[str] = None
    brand: Optional[str] = None
    model: Optional[str] = None
    year: Optional[int] = None
    km: Optional[int] = None
    price: Optional[float] = None
    estimated_value: Optional[float] = None
    deal_score: Optional[float] = None
    fuel_type: Optional[str] = None
    transmission: Optional[str] = None
    vehicle_type: Optional[str] = None
    location: Optional[str] = None
    description: Optional[str] = None
    images: List[str] = Field(default_factory=list)
    ai_risk_score: Optional[float] = None
    condition_score: Optional[float] = None
    ai_recommendation: Optional[str] = None
    first_seen: Optional[datetime] = None
    last_seen: Optional[datetime] = None
    is_active: Optional[bool] = None
    
    model_config = ConfigDict(from_attributes=True)


class VehicleFilter(BaseModel):
    """Filter schema for vehicle listing"""
    brand: Optional[str] = None
    model: Optional[str] = None
    year_min: Optional[int] = None
    year_max: Optional[int] = None
    price_min: Optional[float] = None
    price_max: Optional[float] = None
    km_min: Optional[int] = None
    km_max: Optional[int] = None
    fuel_type: Optional[str] = None
    transmission: Optional[str] = None
    vehicle_type: Optional[str] = None
    deal_score_min: Optional[float] = None
    source: Optional[str] = None
    limit: int = Field(default=50, ge=1, le=200)
    offset: int = Field(default=0, ge=0)

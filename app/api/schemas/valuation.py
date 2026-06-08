"""
Valuation Schemas for API
Pydantic models for valuation-related API requests and responses
"""
from __future__ import annotations
from typing import Optional
from pydantic import BaseModel, Field


class ValuationRequest(BaseModel):
    """Request schema for vehicle valuation"""
    brand: str = Field(..., description="Vehicle brand")
    model: str = Field(..., description="Vehicle model")
    year: int = Field(..., ge=1990, le=2026, description="Vehicle year")
    km: Optional[int] = Field(None, ge=0, description="Kilometers")
    price: float = Field(..., gt=0, description="Asking price")
    fuel_type: Optional[str] = Field(None, description="Fuel type")
    transmission: Optional[str] = Field(None, description="Transmission type")
    vehicle_type: str = Field(default="carros", description="Vehicle type (carros/motos)")


class ValuationResponse(BaseModel):
    """Response schema for vehicle valuation"""
    statistical_price: Optional[float] = Field(None, description="Statistical pricing (median of comparables)")
    statistical_comparables_count: Optional[int] = Field(None, description="Number of comparables used")
    comparable_price: Optional[float] = Field(None, description="Comparable clustering price")
    comparable_cluster_size: Optional[int] = Field(None, description="Cluster size")
    ml_price: Optional[float] = Field(None, description="ML model prediction")
    ml_confidence: Optional[float] = Field(None, description="ML confidence score")
    ml_model_version: Optional[str] = Field(None, description="ML model version")
    ai_adjustment: Optional[float] = Field(None, description="AI reasoning adjustment")
    ai_adjustment_reason: Optional[str] = Field(None, description="Reason for AI adjustment")
    final_price: Optional[float] = Field(None, description="Final hybrid price")
    calculation_method: Optional[str] = Field(None, description="Method used for calculation")
    calculated_at: Optional[str] = Field(None, description="Timestamp of calculation")

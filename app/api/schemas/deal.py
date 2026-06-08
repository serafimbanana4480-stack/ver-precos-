"""
Deal Schemas for API
Pydantic models for deal-related API responses
"""
from __future__ import annotations
from typing import Optional, List
from pydantic import BaseModel, Field, ConfigDict
from datetime import datetime


class DealResponse(BaseModel):
    """Response schema for deal data"""
    vehicle_id: Optional[int] = None
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
    price_savings: Optional[float] = None  # estimated_value - price
    price_savings_percent: Optional[float] = None  # (estimated_value - price) / estimated_value * 100
    ai_risk_score: Optional[float] = None
    condition_score: Optional[float] = None
    ai_recommendation: Optional[str] = None
    fuel_type: Optional[str] = None
    transmission: Optional[str] = None
    location: Optional[str] = None
    images: List[str] = Field(default_factory=list)
    first_seen: Optional[datetime] = None
    last_seen: Optional[datetime] = None
    
    model_config = ConfigDict(from_attributes=True)


class DealScoreBreakdown(BaseModel):
    """Breakdown of deal score components"""
    market_deviation_score: Optional[float] = None
    ai_risk_score: Optional[float] = None
    vision_damage_score: Optional[float] = None
    price_anomaly_score: Optional[float] = None
    demand_signal_score: Optional[float] = None
    final_score: Optional[float] = None
    score_interpretation: Optional[str] = None
    recommended_action: Optional[str] = None
    calculated_at: Optional[datetime] = None

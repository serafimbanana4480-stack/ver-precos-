"""
AI response validation models using pydantic
"""
from typing import Optional, List, Dict, Any
from pydantic import BaseModel, Field, field_validator, ConfigDict


class LLMReviewResponse(BaseModel):
    """Validation model for LLM review responses"""
    model_config = ConfigDict(extra='allow')
    
    recommendation: str
    confidence: float = Field(ge=0.0, le=1.0, description="Confidence must be between 0.0 and 1.0")
    issues: List[str] = Field(default_factory=list, description="List of detected issues")
    reasoning: Optional[str] = None
    
    @classmethod
    def with_overrides(cls, data: Dict[str, Any], overrides: Optional[Dict[str, Any]] = None) -> 'LLMReviewResponse':
        """Create instance with optional validation overrides"""
        if overrides:
            for key, value in overrides.items():
                if key in data:
                    data[key] = value
        return cls(**data)
    
    @field_validator('recommendation')
    @classmethod
    def validate_recommendation(cls, v):
        valid_recommendations = ["Approved", "Rejected", "Neutral"]
        if v not in valid_recommendations:
            raise ValueError(f"recommendation must be one of {valid_recommendations}")
        return v
    
    @field_validator('issues')
    @classmethod
    def validate_issues(cls, v):
        if not isinstance(v, list):
            raise ValueError("issues must be a list")
        return v


class VisionAnalysisResponse(BaseModel):
    """Validation model for vision analysis responses"""
    condition_score: int = Field(ge=0, le=10, description="Condition score must be between 0 and 10")
    damage_detected: List[str] = Field(default_factory=list, description="List of detected damages")
    confidence: Optional[float] = Field(default=None, ge=0.0, le=1.0, description="Confidence must be between 0.0 and 1.0")
    
    @field_validator('damage_detected')
    @classmethod
    def validate_damage_detected(cls, v):
        if not isinstance(v, list):
            raise ValueError("damage_detected must be a list")
        return v


class DealAnalysisResponse(BaseModel):
    """Validation model for deal analysis responses"""
    deal_score: float = Field(ge=0.0, le=10.0, description="Deal score must be between 0.0 and 10.0")
    profit_potential: Optional[float] = Field(default=None, ge=0, description="Profit potential must be >= 0")
    recommendation: str
    reasoning: Optional[str] = None
    
    @field_validator('recommendation')
    @classmethod
    def validate_recommendation(cls, v):
        valid_recommendations = ["Strong Buy", "Buy", "Hold", "Skip"]
        if v not in valid_recommendations:
            raise ValueError(f"recommendation must be one of {valid_recommendations}")
        return v

"""
Deal scoring configuration for AutoDeal IA Hunter.
"""
from pydantic import BaseModel
from typing import Dict, List


class DealScoringConfig(BaseModel):
    """Configuration for deal scoring settings."""
    
    enabled: bool = True
    
    # Scoring thresholds
    min_deal_score: float = 7.0
    min_profit_euros: int = 1500
    min_profit_percentage: float = 0.15
    
    # Scoring weights
    price_weight: float = 0.4
    condition_weight: float = 0.3
    mileage_weight: float = 0.2
    market_position_weight: float = 0.1
    
    # Scoring factors
    consider_location: bool = True
    consider_seller_rating: bool = True
    consider_listing_age: bool = True
    consider_price_history: bool = True
    
    # AI analysis weight
    ai_analysis_weight: float = 0.5
    
    # Risk factors
    risk_factor_enabled: bool = True
    accident_penalty: float = -2.0
    mechanical_issue_penalty: float = -1.5
    
    # Value factors
    value_factor_enabled: bool = True
    maintenance_bonus: float = 1.0
    extras_bonus: float = 0.5


deal_scoring_config = DealScoringConfig()

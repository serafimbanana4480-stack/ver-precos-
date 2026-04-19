import logging
from typing import List, Dict, Optional, Any
from sqlalchemy.orm import Session
from sqlalchemy import func
from database.models import Vehicle, PriceHistory
from datetime import datetime, timezone

logger = logging.getLogger(__name__)

class DealScorer:
    """Engine to calculate deal quality scores for vehicles"""
    
    def __init__(self, session: Session):
        self.session = session

    def calculate_market_average(self, brand: str, model: str, year: int) -> Optional[float]:
        """Calculate average market price for similar vehicles"""
        avg_price = self.session.query(func.avg(Vehicle.price)).filter(
            Vehicle.brand == brand,
            Vehicle.model == model,
            Vehicle.year == year
        ).scalar()
        
        return float(avg_price) if avg_price else None

    def score_vehicle(self, vehicle: Vehicle) -> Dict[str, Any]:
        """
        Assign a score from 0-100 based on price vs market.
        100 = Incredible deal (well below average)
        50 = Market average
        0 = Overpriced
        """
        avg = self.calculate_market_average(vehicle.brand, vehicle.model, vehicle.year)
        
        if not avg:
            return {"score": 50, "reason": "Insufficient market data"}
            
        diff_percent = ((avg - vehicle.price) / avg) * 100
        
        # Base score (50 is neutral)
        score = 50 + (diff_percent * 2) 
        
        # Adjustments
        if vehicle.km and vehicle.km < 50000:
             score += 10 # Low mileage bonus
        elif vehicle.km and vehicle.km > 200000:
             score -= 15 # High mileage penalty
             
        # Cap score
        score = max(0, min(100, score))
        
        return {
            "score": round(score, 2),
            "market_avg": round(avg, 2),
            "diff_percent": round(diff_percent, 2),
            "is_good_deal": score > 75
        }

    def process_pending_deals(self):
        """Scans vehicles without score and updates them"""
        # (To be implemented when we add score column to Vehicle model)
        pass

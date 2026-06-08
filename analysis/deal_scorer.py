import logging
from typing import List, Dict, Optional, Any
from sqlalchemy.orm import Session
from sqlalchemy import func
from database.models import Vehicle, PriceHistory
from datetime import datetime, timezone
import statistics

logger = logging.getLogger(__name__)

class DealScorer:
    """Engine to calculate deal quality scores for vehicles"""
    
    def __init__(self, session: Session):
        self.session = session

    def calculate_market_median(self, brand: str, model: str, year: int) -> Optional[float]:
        """
        Calculate MEDIAN market price for similar vehicles (±2 years).
        Uses median to be robust against outlier listings.
        Applies IQR filtering to remove extreme outliers before computing.
        """
        rows = self.session.query(Vehicle.price).filter(
            Vehicle.brand == brand,
            Vehicle.model == model,
            Vehicle.year.between(year - 2, year + 2),
            Vehicle.is_active == True,
            Vehicle.price.isnot(None),
            Vehicle.price > 0,
        ).all()

        prices = [r[0] for r in rows if r[0] and r[0] > 0]
        if len(prices) < 3:
            return None

        # IQR filter: remove extreme outliers that skew the estimate
        q1 = statistics.quantiles(prices, n=4)[0]   # 25th percentile
        q3 = statistics.quantiles(prices, n=4)[2]   # 75th percentile
        iqr = q3 - q1
        lower = q1 - 1.5 * iqr
        upper = q3 + 1.5 * iqr
        filtered = [p for p in prices if lower <= p <= upper]

        if not filtered:
            filtered = prices  # fallback: use all if IQR removes everything

        return statistics.median(filtered)

    # Keep old name as alias for backward compatibility
    def calculate_market_average(self, brand: str, model: str, year: int) -> Optional[float]:
        return self.calculate_market_median(brand, model, year)

    def score_vehicle(self, vehicle: Vehicle) -> Dict[str, Any]:
        """
        Assign a score from 0-10 based on price vs market median.
        10 = Incredible deal (well below median)
        5  = Market median price
        0  = Very overpriced
        """
        median = self.calculate_market_median(vehicle.brand, vehicle.model, vehicle.year or 0)
        
        if median is None:
            return {"score": 5.0, "reason": "Insufficient market data (< 3 comparables)"}
            
        diff_percent = ((median - vehicle.price) / median) * 100
        
        # Base score: 5.0 = neutral (at market median)
        # +15 per 100% below median (≈ +1.5 per 10% discount)
        score = 5.0 + (diff_percent * 0.15)

        # KM adjustments (tiered)
        km = vehicle.km or 0
        if km < 30000:
            score += 1.0   # Very low mileage premium
        elif km < 80000:
            score += 0.3   # Below-average mileage bonus
        elif km > 200000:
            score -= 2.0   # Very high mileage penalty
        elif km > 130000:
            score -= 1.0   # High mileage penalty
             
        # Cap score to 0-10
        score = max(0.0, min(10.0, score))
        
        return {
            "score": round(score, 2),
            "market_median": round(median, 2),
            "diff_percent": round(diff_percent, 2),
            "is_good_deal": score >= 7.5
        }

    def process_pending_deals(self):
        """Scans vehicles without score and updates them"""
        # (To be implemented when we add score column to Vehicle model)
        pass

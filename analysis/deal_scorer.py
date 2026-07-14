import logging
from typing import List, Dict, Optional, Any
from sqlalchemy.orm import Session
from sqlalchemy import func
from database.models import Vehicle
from datetime import datetime, timezone
import statistics

from valuation.deal_score import compute_market_median, score_deal

logger = logging.getLogger(__name__)


class DealScorer:
    """Engine to calculate deal quality scores for vehicles.

    Database-backed wrapper around the pure scoring utilities in
    :mod:`valuation.deal_score`. All pricing math lives in that module so it
    can be unit-tested without a database (see ``tests/unit/test_deal_score.py``).
    """

    def __init__(self, session: Session):
        self.session = session

    def calculate_market_median(self, brand: str, model: str, year: int) -> Optional[float]:
        """MEDIAN market price for similar vehicles (±2 years, IQR-filtered).

        Delegates to :func:`valuation.deal_score.compute_market_median`.
        Returns ``None`` when fewer than 3 comparable listings exist.
        """
        rows = self.session.query(Vehicle.price).filter(
            Vehicle.brand == brand,
            Vehicle.model == model,
            Vehicle.year.between(year - 2, year + 2),
            Vehicle.is_active == True,  # noqa: E712
            Vehicle.price.isnot(None),
            Vehicle.price > 0,
        ).all()

        prices = [r[0] for r in rows if r[0] and r[0] > 0]
        return compute_market_median(prices)

    # Backward-compatible alias
    def calculate_market_average(self, brand: str, model: str, year: int) -> Optional[float]:
        return self.calculate_market_median(brand, model, year)

    def score_vehicle(self, vehicle: Vehicle) -> Dict[str, Any]:
        """Score a vehicle (0-10) using the pure scoring module.

        10 = incredible deal (well below median), 5 = at median, 0 = overpriced.
        """
        median = self.calculate_market_median(vehicle.brand, vehicle.model, vehicle.year or 0)

        if median is None:
            return {"score": 5.0, "reason": "Insufficient market data (< 3 comparables)"}

        result = score_deal(vehicle.price or 0, median, vehicle.km or 0)
        return {
            "score": result.score,
            "market_median": result.market_median,
            "diff_percent": result.diff_percent,
            "is_good_deal": result.is_good_deal,
        }

    def process_pending_deals(self):
        """Scans vehicles without score and updates them."""
        # Implemented when a score column is added to the Vehicle model.
        pass

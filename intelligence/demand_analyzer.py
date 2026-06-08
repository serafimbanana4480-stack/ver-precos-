"""
Market Demand Analyzer — analyzes market demand signals for vehicles.
"""
from __future__ import annotations
import logging
from typing import Dict, List, Any, Optional
from datetime import datetime, timezone, timedelta
from sqlalchemy import func, desc

from database.db import get_db_context
from database.models import Vehicle, VehicleType

logger = logging.getLogger(__name__)


class DemandAnalyzer:
    """Analyze market demand signals for vehicles."""

    def get_demand_score(
        self, brand: str, model: Optional[str] = None, vehicle_type: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        Calculate demand score for a specific brand/model based on:
        - Average days on market (lower = higher demand)
        - Number of active listings
        - Price trends
        - Deal score distribution
        """
        with get_db_context() as db:
            conditions = [Vehicle.is_active == True]  # noqa: E712
            conditions.append(Vehicle.brand.ilike(f"%{brand}%"))
            if model:
                conditions.append(Vehicle.model.ilike(f"%{model}%"))
            if vehicle_type:
                try:
                    vt = VehicleType(vehicle_type)
                    conditions.append(Vehicle.vehicle_type == vt)
                except ValueError:
                    pass

            base = db.query(Vehicle).filter(*conditions)

            total = base.count()
            if total == 0:
                return {
                    "demand_score": 0,
                    "demand_level": "unknown",
                    "total_listings": 0,
                    "message": "No data available",
                }

            # Days on market
            now = datetime.now(timezone.utc)
            avg_days = base.with_entities(
                func.avg(
                    func.julianday(func.datetime(now)) -
                    func.julianday(Vehicle.first_seen)
                )
            ).scalar() or 0

            # Price stats
            avg_price = base.with_entities(func.avg(Vehicle.price)).scalar() or 0
            min_price = base.with_entities(func.min(Vehicle.price)).scalar() or 0
            max_price = base.with_entities(func.max(Vehicle.price)).scalar() or 0

            # Deal score stats
            avg_deal = base.with_entities(func.avg(Vehicle.deal_score)).scalar() or 0
            good_deals = base.filter(Vehicle.deal_score >= 7.0).count()

            # Calculate demand score (0-10)
            # Lower days on market = higher demand
            days_score = max(0, 10 - (avg_days / 10))  # 0 days = 10, 100 days = 0

            # Higher average deal score may indicate oversupply (lower demand)
            deal_factor = max(0, 10 - avg_deal * 1.5) if avg_deal else 5

            # More listings relative to market = potentially oversupplied
            listing_factor = min(10, max(1, 10 - (total / 20)))

            demand_score = round((days_score * 0.4 + deal_factor * 0.3 + listing_factor * 0.3), 1)

            # Demand level
            if demand_score >= 8:
                level = "very_high"
            elif demand_score >= 6:
                level = "high"
            elif demand_score >= 4:
                level = "moderate"
            elif demand_score >= 2:
                level = "low"
            else:
                level = "very_low"

            # Price trend (last 30 days vs previous 30)
            thirty_days_ago = now - timedelta(days=30)
            sixty_days_ago = now - timedelta(days=60)

            recent = base.filter(Vehicle.first_seen >= thirty_days_ago)
            recent_avg = recent.with_entities(func.avg(Vehicle.price)).scalar() or avg_price

            older = base.filter(
                Vehicle.first_seen >= sixty_days_ago,
                Vehicle.first_seen < thirty_days_ago,
            )
            older_avg = older.with_entities(func.avg(Vehicle.price)).scalar() or recent_avg

            if older_avg > 0:
                price_trend_pct = round(((recent_avg - older_avg) / older_avg) * 100, 1)
            else:
                price_trend_pct = 0

            trend_direction = "up" if price_trend_pct > 1 else "down" if price_trend_pct < -1 else "stable"

            return {
                "demand_score": demand_score,
                "demand_level": level,
                "total_listings": total,
                "avg_days_on_market": round(float(avg_days), 1),
                "avg_price": round(float(avg_price), 2),
                "min_price": round(float(min_price), 2),
                "max_price": round(float(max_price), 2),
                "avg_deal_score": round(float(avg_deal), 2),
                "good_deals_count": good_deals,
                "price_trend_30d_pct": price_trend_pct,
                "price_trend_direction": trend_direction,
            }

    def get_market_saturation(
        self, vehicle_type: Optional[str] = None
    ) -> List[Dict[str, Any]]:
        """Analyze market saturation by brand."""
        with get_db_context() as db:
            base = db.query(
                Vehicle.brand,
                func.count(Vehicle.id).label("count"),
                func.avg(Vehicle.price).label("avg_price"),
                func.avg(Vehicle.deal_score).label("avg_score"),
            ).filter(Vehicle.is_active == True)  # noqa: E712

            if vehicle_type:
                try:
                    vt = VehicleType(vehicle_type)
                    base = base.filter(Vehicle.vehicle_type == vt)
                except ValueError:
                    pass

            results = (
                base.group_by(Vehicle.brand)
                .order_by(desc("count"))
                .limit(20)
                .all()
            )

            return [
                {
                    "brand": r.brand,
                    "listings": r.count,
                    "avg_price": round(float(r.avg_price), 2) if r.avg_price else 0,
                    "avg_deal_score": round(float(r.avg_score), 2) if r.avg_score else 0,
                }
                for r in results
            ]

    def get_price_trends(
        self, brand: str, model: Optional[str] = None, days: int = 90
    ) -> List[Dict[str, Any]]:
        """Get price trend data for a specific vehicle over time."""
        with get_db_context() as db:
            since = datetime.now(timezone.utc) - timedelta(days=days)

            conditions = [
                Vehicle.first_seen >= since,
                Vehicle.brand.ilike(f"%{brand}%"),
            ]
            if model:
                conditions.append(Vehicle.model.ilike(f"%{model}%"))

            vehicles = db.query(Vehicle).filter(*conditions).order_by(Vehicle.first_seen).all()

            # Group by week
            trends: Dict[str, List[float]] = {}
            for v in vehicles:
                week_key = v.first_seen.strftime("%Y-%W") if v.first_seen else "unknown"
                if week_key not in trends:
                    trends[week_key] = []
                trends[week_key].append(v.price)

            return [
                {
                    "week": week,
                    "avg_price": round(sum(prices) / len(prices), 2),
                    "count": len(prices),
                    "min_price": round(min(prices), 2),
                    "max_price": round(max(prices), 2),
                }
                for week, prices in sorted(trends.items())
            ]
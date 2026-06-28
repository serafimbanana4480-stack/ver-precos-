"""
Statistical pricing engine - uses median prices by brand/model/year.
Better than ML when dataset is small (<5000 samples).
"""
from __future__ import annotations
import sys, os; sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))
import logging
from collections import defaultdict
from datetime import datetime
from typing import Any, Dict, List, Optional, Tuple

from database.db import get_db_context
from database.models import Vehicle, VehicleType

logger = logging.getLogger(__name__)


class StatisticalPricer:
    """Prices vehicles using statistical percentiles by brand/model/year."""

    def __init__(self):
        self._cache: Dict[str, Dict] = {}
        self._loaded = False

    def _ensure_loaded(self) -> None:
        if self._loaded:
            return
        self._build_price_index()
        self._loaded = True

    def _build_price_index(self) -> None:
        """Build price statistics grouped by brand+year and brand-only."""
        from sqlalchemy import func

        # Brand+Year index
        index_by: Dict[str, List[float]] = defaultdict(list)
        brand_index: Dict[str, List[float]] = defaultdict(list)
        age_index: Dict[int, List[float]] = defaultdict(list)

        with get_db_context() as db:
            vehicles = db.query(Vehicle).filter(
                Vehicle.is_active == True,
                Vehicle.price > 500,
                Vehicle.price < 500000,
                Vehicle.year.isnot(None),
                Vehicle.brand.isnot(None),
            ).all()

            for v in vehicles:
                age = datetime.now().year - v.year if v.year else 5
                brand_index[v.brand].append(v.price)
                key = f"{v.brand}|{v.year}"
                index_by[key].append(v.price)
                age_bucket = (age // 3) * 3
                age_index[age_bucket].append(v.price)

        self._cache = {}
        # Brand+Year groups
        for key, prices in index_by.items():
            if len(prices) >= 2:
                prices.sort()
                n = len(prices)
                self._cache[f"by:{key}"] = {
                    "median": prices[n // 2],
                    "mean": sum(prices) / n,
                    "count": n,
                }

        # Brand-only groups
        for brand, prices in brand_index.items():
            if len(prices) >= 3:
                prices.sort()
                n = len(prices)
                self._cache[f"brand:{brand}"] = {
                    "median": prices[n // 2],
                    "mean": sum(prices) / n,
                    "count": n,
                }

        # Age-based depreciation
        if age_index:
            all_prices = []
            for prices in age_index.values():
                all_prices.extend(prices)
            all_prices.sort()
            self._cache["_all"] = {
                "median": all_prices[len(all_prices) // 2],
                "mean": sum(all_prices) / len(all_prices),
                "count": len(all_prices),
            }

        logger.info(f"Built price index: {len(index_by)} brand+year + {len(brand_index)} brand groups")

    @staticmethod
    def _key(brand: str, model: str, year: Optional[int]) -> str:
        return f"{brand}|{model}|{year or 0}"

    def estimate(self, brand: str, model: str, year: Optional[int],
                 km: Optional[int] = None, vehicle_type: str = "carros") -> Optional[Dict[str, Any]]:
        self._ensure_loaded()

        result = None
        method = "unknown"

        # 1. Try brand+year exact match
        if year:
            by_key = f"by:{brand}|{year}"
            result = self._cache.get(by_key)
            if result:
                method = "brand_year"

        # 2. Try brand-only
        if result is None:
            brand_key = f"brand:{brand}"
            result = self._cache.get(brand_key)
            if result:
                method = "brand"

        # 3. Fallback to global median
        if result is None:
            result = self._cache.get("_all")
            if result:
                method = "global"

        if result is None:
            return None

        median_price = result.get("median", result.get("mean", 0))

        # Apply age-based adjustment for brand-only or global
        if method in ("brand", "global") and year:
            age = datetime.now().year - year
            if age > 0:
                # ~8% depreciation per year
                age_factor = 1.0 - min(0.8, age * 0.08)
                median_price *= age_factor

        # Adjust for KM
        km_adjustment = 1.0
        if km and km > 0:
            avg_km_per_year = 15000
            age = max(1, (datetime.now().year - (year or datetime.now().year)))
            expected_km = avg_km_per_year * age
            if expected_km > 0:
                km_ratio = km / expected_km
                if km_ratio > 1.5:
                    km_adjustment = max(0.7, 1.0 - (km_ratio - 1.5) * 0.1)
                elif km_ratio < 0.5:
                    km_adjustment = min(1.15, 1.0 + (0.5 - km_ratio) * 0.1)

        estimated = median_price * km_adjustment
        return {
            "estimated_value": round(estimated, 2),
            "median_price": round(median_price, 2),
            "km_adjustment": round(km_adjustment, 3),
            "confidence": result.get("count", 0),
            "method": "statistical",
        }

    def score_deal(self, vehicle_data: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        est = self.estimate(
            brand=vehicle_data.get("brand", ""),
            model=vehicle_data.get("model", ""),
            year=vehicle_data.get("year"),
            km=vehicle_data.get("km"),
        )
        if est is None:
            return None

        price = float(vehicle_data.get("price", 0))
        if price <= 0:
            return None

        ev = est["estimated_value"]
        savings = ev - price
        savings_pct = (savings / ev) * 100 if ev > 0 else 0

        score = min(10, max(0, 5 + savings_pct / 5))

        if score >= 9:
            grade = "exceptional"
        elif score >= 7.5:
            grade = "excellent"
        elif score >= 6:
            grade = "good"
        elif score >= 4:
            grade = "fair"
        else:
            grade = "poor"

        return {
            "estimated_value": ev,
            "deal_score": round(score, 1),
            "deal_grade": grade,
            "profit_potential": round(max(0, savings), 2),
            "profit_percentage": round(max(0, savings_pct), 1),
            "confidence": est["confidence"],
            "method": "statistical",
        }


def update_all_valuations() -> int:
    """Update estimated_value and deal_score for all active vehicles."""
    pricer = StatisticalPricer()
    updated = 0

    with get_db_context() as db:
        vehicles = db.query(Vehicle).filter(Vehicle.is_active == True).all()
        for v in vehicles:
            data = {"brand": v.brand, "model": v.model, "year": v.year,
                    "km": v.km, "price": v.price, "vehicle_type": v.vehicle_type.value if v.vehicle_type else "carros"}
            result = pricer.score_deal(data)
            if result:
                v.estimated_value = result["estimated_value"]
                v.deal_score = result["deal_score"]
                v.profit_potential = result["profit_potential"]
                v.profit_percentage = result["profit_percentage"]
                db.add(v)
                updated += 1
        db.commit()

    logger.info(f"Updated valuations for {updated} vehicles")
    return updated


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO, format="%(message)s")
    n = update_all_valuations()
    print(f"Updated {n} vehicles")

"""
Hybrid Vehicle Valuator
Combines ML model (when reliable) with segment-based averages (fallback).
This ensures reasonable valuations even with limited training data.
"""
from __future__ import annotations
import logging
from typing import Optional, Dict, Any
import numpy as np
import pandas as pd
from pathlib import Path
import json

from database.db import get_db_context
from database.models import Vehicle
from config import settings

logger = logging.getLogger(__name__)


class HybridValuator:
    """
    Hybrid valuation engine that uses:
    1. XGBoost ML model when R² > 0.5 and enough data
    2. Segment-based median prices as fallback
    3. Simple depreciation curve for very rare vehicles
    """

    def __init__(self):
        self.ml_model = None
        self.ml_available = False
        self.ml_r2 = 0.0
        self.segment_medians = {}
        self._load_ml_model()
        self._compute_segment_medians()

    def _load_ml_model(self):
        """Try to load the ML model using PricePredictor for carros and motos."""
        try:
            from valuation.predict import PricePredictor

            # Try carros first (more data, more reliable)
            predictor = PricePredictor("carros")
            if predictor.model is not None:
                self.ml_r2 = predictor.metrics.get("r2", 0)
                self.ml_available = self.ml_r2 >= 0.30
                self.ml_model = predictor
                logger.info(f"ML model loaded for carros (R²={self.ml_r2:.3f}, available={self.ml_available})")
                return

            # Fallback to motos (fewer samples, more lenient)
            predictor = PricePredictor("motos")
            if predictor.model is not None:
                self.ml_r2 = predictor.metrics.get("r2", 0)
                self.ml_available = self.ml_r2 >= 0.30
                self.ml_model = predictor
                logger.info(f"ML model loaded for motos (R²={self.ml_r2:.3f}, available={self.ml_available})")
                return

            logger.warning("No ML model could be loaded for carros or motos")
        except Exception as e:
            logger.warning(f"Could not load ML model: {e}")

    def _compute_segment_medians(self):
        """Compute median prices by brand/model/year segment."""
        with get_db_context() as db:
            vehicles = db.query(Vehicle).filter(
                Vehicle.is_active == True,
                Vehicle.price.isnot(None),
                Vehicle.year.isnot(None)
            ).all()

            data = []
            for v in vehicles:
                data.append({
                    "brand": str(v.brand).strip().lower() if v.brand else "unknown",
                    "model": str(v.model).strip().lower() if v.model else "unknown",
                    "year": int(v.year) if v.year else 0,
                    "price": float(v.price),
                    "km": int(v.km) if v.km else 0,
                    "fuel_type": v.fuel_type.value if v.fuel_type else "unknown",
                    "transmission": v.transmission.value if v.transmission else "unknown",
                })

        df = pd.DataFrame(data)
        if df.empty:
            logger.warning("No data for segment medians")
            return

        # Compute medians at different granularity levels
        # Level 1: brand + model + year
        self.segment_medians["bmy"] = df.groupby(["brand", "model", "year"])["price"].median().to_dict()
        # Level 2: brand + model (any year)
        self.segment_medians["bm"] = df.groupby(["brand", "model"])["price"].median().to_dict()
        # Level 3: brand only
        self.segment_medians["b"] = df.groupby("brand")["price"].median().to_dict()
        # Level 4: global median
        self.segment_medians["global"] = df["price"].median()

        # Compute depreciation curves by brand
        self.depreciation = {}
        for brand in df["brand"].unique():
            brand_df = df[df["brand"] == brand]
            if len(brand_df) >= 5:
                year_prices = brand_df.groupby("year")["price"].median().sort_index()
                if len(year_prices) >= 2:
                    # Simple linear depreciation per year
                    years = year_prices.index.values
                    prices = year_prices.values
                    # Avoid division by zero
                    age_range = max(years) - min(years)
                    if age_range > 0:
                        price_drop = max(prices) - min(prices)
                        self.depreciation[brand] = price_drop / age_range

        logger.info(f"Segment medians computed: {len(self.segment_medians.get('bmy', {}))} BMY, "
                   f"{len(self.segment_medians.get('bm', {}))} BM, {len(self.segment_medians.get('b', {}))} B segments")

    def _get_segment_price(self, vehicle_data: Dict[str, Any]) -> Optional[float]:
        """Get price from segment medians with depreciation adjustment."""
        brand = str(vehicle_data.get("brand", "")).strip().lower()
        model = str(vehicle_data.get("model", "")).strip().lower()
        year = int(vehicle_data.get("year", 0))
        km = int(vehicle_data.get("km", 0))

        # Try level 1: brand + model + year
        key = (brand, model, year)
        if key in self.segment_medians.get("bmy", {}):
            return float(self.segment_medians["bmy"][key])

        # Try level 2: brand + model (adjust for year)
        key = (brand, model)
        if key in self.segment_medians.get("bm", {}):
            base_price = float(self.segment_medians["bm"][key])
            # Adjust for year using depreciation
            dep = self.depreciation.get(brand, 1000)  # Default €1000/year
            bm_years = [y for (b, m, y) in self.segment_medians.get("bmy", {}).keys() if b == brand and m == model]
            if bm_years:
                median_year = int(np.median(bm_years))
                year_diff = year - median_year
                adjusted = base_price + (year_diff * dep)
                return max(adjusted, 500)
            return base_price

        # Try level 3: brand only
        if brand in self.segment_medians.get("b", {}):
            base_price = float(self.segment_medians["b"][brand])
            dep = self.depreciation.get(brand, 1000)
            b_years = [y for (b, m, y) in self.segment_medians.get("bmy", {}).keys() if b == brand]
            if b_years:
                median_year = int(np.median(b_years))
                year_diff = year - median_year
                adjusted = base_price + (year_diff * dep)
                return max(adjusted, 500)
            return base_price

        # Level 4: global median with rough depreciation
        global_median = self.segment_medians.get("global", 15000)
        current_year = pd.Timestamp.now().year
        age = current_year - year
        # Rough depreciation: 10% first year, then 8% per year
        depreciation_factor = max(0.2, 0.9 ** min(age, 1) * 0.92 ** max(0, age - 1))
        adjusted = global_median * depreciation_factor
        # KM adjustment: €0.05 per km
        km_adjustment = km * 0.05
        adjusted -= km_adjustment
        return max(adjusted, 500)

    def estimate_value(self, vehicle_data: Dict[str, Any]) -> Optional[float]:
        """
        Estimate vehicle value using hybrid approach.
        Returns estimated market value in EUR.
        """
        ml_price = None
        segment_price = None

        # Try ML model first
        if self.ml_available and self.ml_model:
            try:
                ml_price = self.ml_model.predict(vehicle_data)
                if ml_price and ml_price > 0:
                    logger.debug(f"ML estimate: €{ml_price:.0f}")
            except Exception as e:
                logger.debug(f"ML prediction failed: {e}")

        # Get segment-based estimate
        try:
            segment_price = self._get_segment_price(vehicle_data)
            if segment_price and segment_price > 0:
                logger.debug(f"Segment estimate: €{segment_price:.0f}")
        except Exception as e:
            logger.debug(f"Segment estimate failed: {e}")

        # Combine estimates
        if ml_price and segment_price:
            # Weight by model confidence (R²)
            ml_weight = max(0.3, min(0.7, self.ml_r2))
            seg_weight = 1 - ml_weight
            combined = ml_price * ml_weight + segment_price * seg_weight
            logger.debug(f"Combined estimate (ML w={ml_weight:.2f}): €{combined:.0f}")
            return round(combined, 2)
        elif ml_price:
            return round(ml_price, 2)
        elif segment_price:
            return round(segment_price, 2)
        else:
            # Ultimate fallback
            return 10000.0

    # Portugal vehicle transfer tax rates (simplified)
    TRANSFER_TAX_RATE = 0.155   # ISV(10%) + IMT(5%) + Selo(0.5%) ≈ 15.5%

    # Estimated repair costs by condition score bucket (EUR)
    _REPAIR_COST_BY_CONDITION = [
        (8.0, 0),      # condition >= 8: excellent — no repairs
        (6.0, 500),    # condition >= 6: good
        (4.0, 1500),   # condition >= 4: fair
        (2.0, 3000),   # condition >= 2: poor
        (0.0, 5000),   # condition < 2: very poor
    ]

    def _estimate_repair_costs(self, condition_score: float) -> float:
        """Estimate repair costs from condition score (0-10)."""
        for threshold, cost in self._REPAIR_COST_BY_CONDITION:
            if condition_score >= threshold:
                return float(cost)
        return 5000.0

    def calculate_deal_score(self, vehicle_data: Dict[str, Any]) -> Dict[str, Any]:
        """
        Calculate deal score based on estimated value vs asking price.

        Returns both:
        - profit_potential: gross spread (estimated_value - price), before any costs.
          Used for ranking / scoring.
        - net_profit_potential: spread after Portugal transfer taxes and estimated
          repairs. This is the realistic profit a reseller can expect.
        """
        price = float(vehicle_data.get("price", 0))
        estimated_value = self.estimate_value(vehicle_data)

        if not estimated_value or price <= 0:
            return {
                "deal_score": 0.0,
                "estimated_value": estimated_value or 0,
                "price": price,
                "profit_potential": 0.0,
                "net_profit_potential": 0.0,
            }

        # Portuguese market: asking prices are typically 10-15% above real transaction
        # Use 1.12 as consistent benchmark (v6 script uses 1.10, we add small buffer)
        market_margin = 1.12
        asking_benchmark = estimated_value * market_margin

        # Discount from benchmark (positive = cheaper than market)
        discount = (asking_benchmark - price) / asking_benchmark

        # Score 0-10: 5.0 = neutral, 8.0 = ~20% below benchmark, 10.0 = 33%+ below
        raw_score = 5.0 + (discount * 15.0)
        deal_score = max(0.0, min(10.0, raw_score))

        # --- Gross profit potential (spread before acquisition costs) ---
        gross_profit = max(0.0, estimated_value - price)
        profit_percentage = (gross_profit / price * 100.0) if price > 0 else 0.0

        # --- Net profit potential (after Portugal taxes + repairs) ---
        taxes = price * self.TRANSFER_TAX_RATE
        condition_score = float(vehicle_data.get("condition_score") or 6.0)
        repair_costs = self._estimate_repair_costs(condition_score)
        total_costs = taxes + repair_costs
        net_profit = max(0.0, gross_profit - total_costs)
        net_profit_pct = (net_profit / price * 100.0) if price > 0 else 0.0

        return {
            "deal_score": round(deal_score, 1),
            "estimated_value": round(estimated_value, 2),
            "asking_benchmark": round(asking_benchmark, 2),
            "price": price,
            "price_discount": round(discount, 3),
            # Gross: used for scoring / filtering (before acquisition costs)
            "profit_potential": round(gross_profit, 2),
            "profit_percentage": round(profit_percentage, 2),
            # Net: realistic reseller profit after Portugal taxes + repairs
            "net_profit_potential": round(net_profit, 2),
            "net_profit_percentage": round(net_profit_pct, 2),
            "transfer_taxes": round(taxes, 2),
            "estimated_repair_costs": round(repair_costs, 2),
            "valuation_method": "ml" if self.ml_available else "segment",
        }


# Global instance
_hybrid_valuator = None

def get_valuator() -> HybridValuator:
    """Get or create the global hybrid valuator instance."""
    global _hybrid_valuator
    if _hybrid_valuator is None:
        _hybrid_valuator = HybridValuator()
    return _hybrid_valuator


def estimate_market_value(vehicle_data: Dict[str, Any]) -> Optional[float]:
    """Convenience function for estimating market value."""
    return get_valuator().estimate_value(vehicle_data)


def calculate_deal_score(vehicle_data: Dict[str, Any]) -> Dict[str, Any]:
    """Convenience function for calculating deal score."""
    return get_valuator().calculate_deal_score(vehicle_data)

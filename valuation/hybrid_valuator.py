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
        self.segment_prices = {}  # price LISTS per segment (for leakage-safe median)
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
        """Compute median prices by brand/model/year segment (EXCLUDING each
        vehicle from its own segment to avoid circular/optimistic leakage)."""
        with get_db_context() as db:
            vehicles = db.query(Vehicle).filter(
                Vehicle.is_active == True,
                Vehicle.price.isnot(None),
                Vehicle.year.isnot(None)
            ).all()

            data = []
            for v in vehicles:
                data.append({
                    "id": int(v.id),
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

        # Compute medians at different granularity levels, EXCLUDING the
        # vehicle itself from its own (brand,model,year) bucket. We store
        # full sorted price lists so _get_segment_price can drop the self row.
        # Level 1: brand + model + year (list of prices)
        self.segment_prices["bmy"] = (
            df.groupby(["brand", "model", "year"])["price"].apply(list).to_dict()
        )
        # Level 2: brand + model
        self.segment_prices["bm"] = (
            df.groupby(["brand", "model"])["price"].apply(list).to_dict()
        )
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
                    years = year_prices.index.values
                    prices = year_prices.values
                    age_range = max(years) - min(years)
                    if age_range > 0:
                        price_drop = max(prices) - min(prices)
                        self.depreciation[brand] = price_drop / age_range

        logger.info(f"Segment medians computed: {len(self.segment_prices.get('bmy', {}))} BMY, "
                    f"{len(self.segment_prices.get('bm', {}))} BM, {len(self.segment_medians.get('b', {}))} B segments")

    def _median_excl_self(self, price_list, self_id=None, self_price=None):
        """Median of a price list, excluding the vehicle's own price (leakage fix)."""
        if self_id is None and self_price is None:
            return float(np.median(price_list)) if price_list else None
        arr = np.array(price_list, dtype=float)
        if self_price is not None:
            arr = arr[arr != self_price]
        if len(arr) == 0:
            return None
        return float(np.median(arr))

    def _get_segment_price(self, vehicle_data: Dict[str, Any]) -> Optional[float]:
        """Get price from segment medians with depreciation adjustment.
        LEAKAGE FIX: the vehicle's own price is excluded from its segment
        median so the estimate isn't circular/optimistic."""
        brand = str(vehicle_data.get("brand", "")).strip().lower()
        model = str(vehicle_data.get("model", "")).strip().lower()
        year = int(vehicle_data.get("year") or 0)
        km = int(vehicle_data.get("km") or 0)
        self_id = vehicle_data.get("id")
        self_price = float(vehicle_data.get("price")) if vehicle_data.get("price") else None

        # Try level 1: brand + model + year (exclude self)
        key = (brand, model, year)
        if key in self.segment_prices.get("bmy", {}):
            med = self._median_excl_self(self.segment_prices["bmy"][key], self_id, self_price)
            if med is not None:
                return med

        # Try level 2: brand + model (adjust for year)
        key = (brand, model)
        if key in self.segment_prices.get("bm", {}):
            prices = self.segment_prices["bm"][key]
            base_price = self._median_excl_self(prices, self_id, self_price)
            if base_price is None:
                return None
            dep = self.depreciation.get(brand, 1000)
            bm_years = [y for (b, m, y) in self.segment_prices.get("bmy", {}).keys() if b == brand and m == model]
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
            b_years = [y for (b, m, y) in self.segment_prices.get("bmy", {}).keys() if b == brand]
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
        depreciation_factor = max(0.2, 0.9 ** min(age, 1) * 0.92 ** max(0, age - 1))
        adjusted = global_median * depreciation_factor
        km_adjustment = km * 0.05
        adjusted -= km_adjustment
        return max(adjusted, 500)

    def estimate_value(self, vehicle_data: Dict[str, Any]) -> Optional[float]:
        """
        Estimate vehicle value using hybrid approach.
        Returns estimated market value in EUR.
        """

        # Auction sources: estimate directly from the auction price. This is
        # robust and independent of the retail segment median, which massively
        # overvalues auction vehicles (they sell "as-is", far below retail).
        _src = str(vehicle_data.get("source", "")).upper()
        if _src in ("LEILOSOC", "VPAUTO", "MANHEIM", "AUTOROLA", "BCA"):
            _ap = float(vehicle_data.get("price", 0) or 0)
            if _ap > 0:
                _yr = int(vehicle_data.get("year") or 2010)
                _km = int(vehicle_data.get("km") or 200000)
                _age = max(0, pd.Timestamp.now().year - _yr)
                if _age > 15 or _km > 250000:
                    _mult = 3.5
                elif _age > 10 or _km > 150000:
                    _mult = 2.5
                elif _age > 5:
                    _mult = 2.0
                else:
                    _mult = 1.6
                _rep = self._estimate_repair_costs(float(vehicle_data.get("condition_score") or 3.0))
                _est = _ap * _mult + _rep
                _est = min(_est, 60000.0)
                return round(max(_est, _ap), 2)

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

        # Combine estimates into a base value.
        # The segment median reflects the TRUE market price (grounded in real
        # listings) and is preferred; the ML model is only a light adjustment
        # because in this dataset it is systematically biased high, which made
        # every underpriced-looking listing look like a 100%+ "deal".
        if segment_price and ml_price:
            if self.ml_r2 >= 0.5:
                final = segment_price * 0.85 + ml_price * 0.15
            else:
                final = segment_price
            logger.debug(f"Combined estimate (segment-led): €{final:.0f}")
        elif ml_price:
            final = ml_price
        elif segment_price:
            final = segment_price
        else:
            # Ultimate fallback
            final = 10000.0

        # --- AUCTION ADJUSTMENT ---
        # Auction vehicles (LEILOSOC, etc.) are bought "as-is" far below
        # retail. A realistic resale estimate is the auction price scaled by a
        # typical auction->retail multiple, capped at a sane retail ceiling.
        # Using the raw retail segment median here massively overestimates
        # resale (5-20x) and produces fake "deals" / impossible profit %.
        source = str(vehicle_data.get("source", "")).upper()
        if source in ("LEILOSOC", "VPAUTO", "MANHEIM", "AUTOROLA", "BCA"):
            year = int(vehicle_data.get("year") or 2010)
            km = int(vehicle_data.get("km") or 200000)
            age = max(0, pd.Timestamp.now().year - year)

            # Typical auction->retail resale multiple by age/km
            if age > 15 or km > 250000:
                mult = 3.5
            elif age > 10 or km > 150000:
                mult = 2.5
            elif age > 5:
                mult = 2.0
            else:
                mult = 1.6

            auction_price = float(vehicle_data.get("price", 0) or 0)
            if auction_price > 0:
                repair_cost = self._estimate_repair_costs(
                    float(vehicle_data.get("condition_score") or 3.0)
                )
                est = auction_price * mult + repair_cost
                # Cap at a sane retail ceiling and €60K absolute.
                ceiling = min(final * 0.8, 60000.0) if final else 60000.0
                est = min(est, ceiling)
                final = max(est, auction_price)
                logger.debug(f"Auction adjustment: €{auction_price:.0f} -> €{final:.0f} "
                           f"(mult={mult}x, repairs=€{repair_cost:.0f})")
            else:
                final = final * 0.55

        # --- SMALL MOTORCYCLE ADJUSTMENT ---
        # Scooters and small bikes (125cc) are systematically overestimated
        # because the model was trained mostly on cars and large BMWs.
        # Simple rule: for known scooters, cap the estimate at 1.5x the asking price.
        vehicle_type = str(vehicle_data.get("vehicle_type", "")).lower()
        title = str(vehicle_data.get("title", "")).lower()
        model_str = str(vehicle_data.get("model", "")).lower()
        price = float(vehicle_data.get("price", 0))

        is_scooter = any(kw in (title + model_str) for kw in
            ['pcx', 'scooter', 'vespa', 'liberty', 'jet', 'nmax', 'xmax',
             'forza', 'sh125', 'sh150', 'medley', 'burgman', 'cygnus', 'dink',
             'msx', 'vision', 'tweet', 'agility', 'people', 'like',
             'sh125i', 'sh150i', 'nss', 'ww125', 'cbf125', 'cb125', 'cbr125'])
        has_125 = ('125' in title or '125' in model_str) and '1250' not in title and '1250' not in model_str
        is_scooter = is_scooter or has_125

        if vehicle_type == 'motos' and is_scooter and price > 100:
            # A PCX selling for E2500 is not worth E10000.
            # Cap realistic value at 1.8x asking price for scooters.
            final = min(final, price * 1.8)
            logger.debug(f"Scooter cap: E{final:.0f}")

        return round(final, 2)
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
        # CORREÇÃO ISV: carros nacionais NÃO pagam ISV (só IMT + Selo 0.6%).
        # Usa deal_scorer_unified.calculate_transfer_taxes que já aplica ISV
        # apenas quando is_national=False.
        from valuation.deal_scorer_unified import calculate_transfer_taxes
        is_national = vehicle_data.get("is_national", None)
        engine_cc = int(vehicle_data.get("engine_size") or 1500)
        co2 = float(vehicle_data.get("co2_gkm") or 120.0)
        age_years = max(0, pd.Timestamp.now().year - int(vehicle_data.get("year") or pd.Timestamp.now().year))
        tax_breakdown = calculate_transfer_taxes(
            price=price, engine_cc=engine_cc, co2_gkm=co2,
            fuel_type=str(vehicle_data.get("fuel_type") or "gasolina"),
            age_years=age_years, is_national=bool(is_national) if is_national is not None else True,
        )
        taxes = tax_breakdown["total"]
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

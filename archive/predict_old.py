"""
Price prediction and deal scoring — Statistical Market-Based Valuation

Instead of a broken XGBoost model (R²=-0.44, 89 samples), this module uses
a statistical approach based on actual market data from the database:

1. Find similar vehicles (same brand+model, ±2 years)
2. Calculate median market price from those comparables
3. Apply km-based depreciation adjustment
4. Enforce sanity bounds (estimate within 0.3x–3x of asking price)

The XGBoost model path is preserved for future use when enough data exists.
"""
from __future__ import annotations
import logging
import json
import math
from pathlib import Path
from typing import Optional, Dict, List
from datetime import datetime
import numpy as np

from config import settings
from database.models import Vehicle, VehicleType

logger = logging.getLogger(__name__)

# --- Constants ---
CURRENT_YEAR = datetime.now().year
MIN_COMPARABLES = 5  # Increased for better statistical reliability
SANITY_MIN_RATIO = 0.5  # Estimate must be >= 50% of asking price (tightened)
SANITY_MAX_RATIO = 1.5  # Estimate must be <= 150% of asking price (tightened)
MIN_CAR_PRICE = 500  # Minimum realistic car price in EUR
MIN_MOTO_PRICE = 200  # Minimum realistic moto price in EUR

# Premium brands that tend to have higher prices
PREMIUM_BRANDS = {
    "porsche", "ferrari", "lamborghini", "maserati", "bentley", "rolls-royce",
    "aston martin", "mclaren", "bugatti", "tesla", "bmw", "mercedes",
    "mercedes-benz", "audi", "land rover", "jaguar", "lexus", "volvo",
    "alfa romeo"
}

# Known deposit/reservation indicators in titles or prices
DEPOSIT_KEYWORDS = [
    "reserva", "sinal", "entrada", "deposit", "caução",
]


def estimate_market_value(vehicle: Vehicle) -> Optional[float]:
    """
    Estimate fair market value using statistical approach based on comparables.
    
    Strategy:
    1. Find vehicles with same brand+model (±2 years)
    2. If enough comparables, use median price adjusted for km
    3. If not enough, widen to same brand (±3 years)
    4. If still not enough, use brand category average
    5. Always enforce sanity bounds
    
    Args:
        vehicle: Vehicle object from database
    
    Returns:
        Estimated market value or None if cannot estimate
    """
    if not vehicle.price or vehicle.price <= 0:
        return None
    if not vehicle.year:
        return None
    
    # Check for deposit/reservation prices (suspiciously low)
    if _is_likely_deposit(vehicle):
        logger.info(f"[VALUATION] Skipping deposit-like price for {vehicle.brand} {vehicle.model}: €{vehicle.price}")
        return None
    
    from database.db import get_db_context
    
    with get_db_context() as db:
        # Strategy 1: Exact brand+model match (±2 years)
        comparables = _find_comparables(
            db, vehicle.brand, vehicle.model, vehicle.year,
            year_range=2, vehicle_type=vehicle.vehicle_type
        )
        
        if len(comparables) >= MIN_COMPARABLES:
            estimate = _calculate_estimate(comparables, vehicle)
            if estimate:
                return _apply_sanity_bounds(estimate, vehicle.price)
        
        # Strategy 2: Same brand, any model (±3 years)
        comparables = _find_comparables(
            db, vehicle.brand, None, vehicle.year,
            year_range=3, vehicle_type=vehicle.vehicle_type
        )
        
        if len(comparables) >= MIN_COMPARABLES:
            estimate = _calculate_estimate(comparables, vehicle)
            if estimate:
                # Apply wider sanity bounds for less precise estimates (tightened)
                return _apply_sanity_bounds(estimate, vehicle.price, min_ratio=0.6, max_ratio=1.4)
        
        # Strategy 3: Same vehicle type, similar price range (±30%)
        comparables = _find_by_price_range(
            db, vehicle.price, vehicle.vehicle_type, range_pct=0.3
        )
        
        if len(comparables) >= MIN_COMPARABLES:
            estimate = _calculate_estimate(comparables, vehicle)
            if estimate:
                return _apply_sanity_bounds(estimate, vehicle.price, min_ratio=0.7, max_ratio=1.3)
    
    # Strategy 4: If all else fails, assume market value ≈ asking price
    # (no data to say otherwise)
    logger.debug(f"[VALUATION] No comparables found for {vehicle.brand} {vehicle.model}, using asking price")
    return None


def _is_likely_deposit(vehicle: Vehicle) -> bool:
    """Detect if a listing price is likely a deposit/reservation, not the full price."""
    if not vehicle.price or not vehicle.brand:
        return False
    
    brand_lower = vehicle.brand.lower()
    
    # Premium brand with suspiciously low price
    if brand_lower in PREMIUM_BRANDS and vehicle.price < 2000:
        return True
    
    # Any car under €500 is suspicious
    if vehicle.vehicle_type == VehicleType.CAR and vehicle.price < MIN_CAR_PRICE:
        return True
    
    # Check title for deposit keywords
    title = (vehicle.title or "").lower()
    for keyword in DEPOSIT_KEYWORDS:
        if keyword in title:
            return True
    
    return False


def _find_comparables(
    db, brand: str, model: Optional[str], year: int,
    year_range: int = 2, vehicle_type=None
) -> List[Vehicle]:
    """Find comparable vehicles in the database."""
    if not brand:
        return []
    
    query = db.query(Vehicle).filter(
        Vehicle.is_active == True,
        Vehicle.price > 0,
        Vehicle.brand.ilike(f"%{brand}%"),
        Vehicle.year >= year - year_range,
        Vehicle.year <= year + year_range,
    )
    
    if model:
        # Use first significant word of model for matching
        model_key = model.split()[0] if model else ""
        if len(model_key) >= 2:
            query = query.filter(Vehicle.model.ilike(f"%{model_key}%"))
    
    if vehicle_type:
        query = query.filter(Vehicle.vehicle_type == vehicle_type)
    
    return query.all()


def _find_by_price_range(db, price: float, vehicle_type, range_pct: float = 0.3) -> List[Vehicle]:
    """Find vehicles in a similar price range."""
    min_price = price * (1 - range_pct)
    max_price = price * (1 + range_pct)
    
    query = db.query(Vehicle).filter(
        Vehicle.is_active == True,
        Vehicle.price >= min_price,
        Vehicle.price <= max_price,
    )
    
    if vehicle_type:
        query = query.filter(Vehicle.vehicle_type == vehicle_type)
    
    return query.limit(50).all()


def _calculate_estimate(comparables: List[Vehicle], target: Vehicle) -> Optional[float]:
    """
    Calculate estimated value from comparables with km adjustment.
    
    Uses median price of comparables, adjusted for km difference.
    """
    if not comparables:
        return None
    
    prices = [v.price for v in comparables if v.price and v.price > 0]
    if not prices:
        return None
    
    # Use median (robust to outliers)
    median_price = float(np.median(prices))
    
    # Apply km-based depreciation adjustment
    if target.km is not None and target.km > 0:
        comparable_kms = [v.km for v in comparables if v.km and v.km > 0]
        if comparable_kms:
            median_km = float(np.median(comparable_kms))
            km_diff = target.km - median_km
            
            # Depreciation: roughly 5% per 10,000 km difference
            depreciation_rate = 0.005  # 0.5% per 1000 km
            km_adjustment = 1 - (km_diff * depreciation_rate / 1000)
            km_adjustment = max(0.5, min(1.5, km_adjustment))  # Clamp adjustment
            
            median_price *= km_adjustment
    
    # Apply age adjustment relative to comparables
    if target.year:
        comparable_years = [v.year for v in comparables if v.year]
        if comparable_years:
            median_year = float(np.median(comparable_years))
            year_diff = target.year - median_year
            
            # Newer = more valuable: ~3% per year
            age_adjustment = 1 + (year_diff * 0.03)
            age_adjustment = max(0.7, min(1.3, age_adjustment))
            
            median_price *= age_adjustment
    
    return round(median_price, 2)


def _apply_sanity_bounds(
    estimate: float, asking_price: float,
    min_ratio: float = SANITY_MIN_RATIO,
    max_ratio: float = SANITY_MAX_RATIO
) -> float:
    """
    Ensure estimated value is within sane bounds relative to asking price.
    
    This prevents absurd estimates like €91,000 for a €7,000 scooter.
    """
    lower_bound = asking_price * min_ratio
    upper_bound = asking_price * max_ratio
    
    clamped = max(lower_bound, min(upper_bound, estimate))
    
    if abs(clamped - estimate) > 1:
        logger.debug(
            f"[VALUATION] Clamped estimate from €{estimate:.0f} to €{clamped:.0f} "
            f"(asking: €{asking_price:.0f}, bounds: {min_ratio}x–{max_ratio}x)"
        )
    
    return round(clamped, 2)


def calculate_deal_score(
    asked_price: float,
    estimated_value: float,
    km: Optional[int] = None,
    year: Optional[int] = None,
    condition_score: Optional[float] = None
) -> float:
    """
    Calculate deal score (0-10) based on price difference and other factors.
    
    More conservative than the previous version — no more 10.0/10 scores
    for broken model predictions.
    
    Args:
        asked_price: Current asking price
        estimated_value: Estimated fair market value
        km: Vehicle kilometers
        year: Vehicle year
        condition_score: Condition score from vision analysis (0-10)
    
    Returns:
        Deal score from 0 to 9.5 (nothing is a "perfect" deal)
    """
    if estimated_value <= 0 or asked_price <= 0:
        return 0.0
    
    # Calculate price difference percentage
    price_diff_percent = (estimated_value - asked_price) / estimated_value * 100
    
    # Base score from price difference (conservative scoring)
    if price_diff_percent <= -20:
        # Significantly overpriced
        base_score = 1.0
    elif price_diff_percent <= -10:
        # Moderately overpriced
        base_score = 2.0
    elif price_diff_percent <= 0:
        # At or slightly above market value
        base_score = 3.5
    elif price_diff_percent < 5:
        # Slightly below market
        base_score = 5.0
    elif price_diff_percent < 10:
        # Good deal
        base_score = 6.0
    elif price_diff_percent < 15:
        # Very good deal
        base_score = 7.0
    elif price_diff_percent < 20:
        # Excellent deal
        base_score = 7.5
    elif price_diff_percent < 30:
        # Amazing deal
        base_score = 8.0
    else:
        # Suspiciously good — might be a problem (too good to be true)
        base_score = 8.5
    
    # Adjust for km (lower km is better)
    if km is not None:
        if km < 20000:
            km_adjustment = 0.3
        elif km < 50000:
            km_adjustment = 0.1
        elif km < 100000:
            km_adjustment = 0.0
        elif km < 150000:
            km_adjustment = -0.1
        elif km < 200000:
            km_adjustment = -0.2
        else:
            km_adjustment = -0.4
        base_score += km_adjustment
    
    # Adjust for year (newer is slightly better)
    if year is not None:
        age = CURRENT_YEAR - year
        if age <= 1:
            year_adjustment = 0.2
        elif age <= 3:
            year_adjustment = 0.1
        elif age <= 6:
            year_adjustment = 0.0
        elif age <= 10:
            year_adjustment = -0.1
        else:
            year_adjustment = -0.2
        base_score += year_adjustment
    
    # Adjust for condition (mild effect)
    if condition_score is not None:
        condition_adjustment = (condition_score - 5) / 20  # -0.25 to +0.25
        base_score += condition_adjustment
    
    # Cap at 9.5 — no "perfect" deals
    return max(0.0, min(9.5, round(base_score, 1)))


def calculate_profit_potential(
    asked_price: float,
    estimated_value: float,
    margin_percent: float = 15.0
) -> Dict[str, float]:
    """
    Calculate potential profit from resale.
    
    Args:
        asked_price: Current asking price
        estimated_value: Estimated fair market value
        margin_percent: Expected resale margin (default 15%)
    
    Returns:
        Dictionary with profit calculations
    """
    if estimated_value <= 0 or asked_price <= 0:
        return {
            "profit_potential": 0.0,
            "profit_percentage": 0.0,
            "resale_price": 0.0
        }
    
    # Calculate realistic resale price (with margin)
    resale_price = estimated_value * (1 - margin_percent / 100)
    
    # Calculate profit
    profit = resale_price - asked_price
    profit_percentage = (profit / asked_price) * 100 if asked_price > 0 else 0
    
    return {
        "profit_potential": round(profit, 2),
        "profit_percentage": round(profit_percentage, 2),
        "resale_price": round(resale_price, 2)
    }


def update_vehicle_valuations(batch_size: int = 500):
    """
    Update valuations for all vehicles in database using statistical approach.
    
    Args:
        batch_size: Number of vehicles to process at once
    """
    logger.info("Updating vehicle valuations using statistical market analysis")
    
    from database.db import get_db_context
    
    updated = 0
    skipped = 0
    
    with get_db_context() as db:
        # Get all active vehicles
        vehicles = db.query(Vehicle).filter(
            Vehicle.is_active == True,
            Vehicle.price > 0,
        ).limit(batch_size).all()
        
        logger.info(f"Processing {len(vehicles)} vehicles for valuation")
        
        for vehicle in vehicles:
            try:
                # Estimate market value
                estimated = estimate_market_value(vehicle)
                
                if estimated:
                    vehicle.estimated_value = estimated
                    
                    # Calculate deal score
                    vehicle.deal_score = calculate_deal_score(
                        vehicle.price,
                        estimated,
                        vehicle.km,
                        vehicle.year,
                        vehicle.condition_score
                    )
                    
                    # Calculate profit potential
                    profit_calc = calculate_profit_potential(
                        vehicle.price,
                        estimated
                    )
                    vehicle.profit_potential = profit_calc["profit_potential"]
                    vehicle.profit_percentage = profit_calc["profit_percentage"]
                    
                    updated += 1
                else:
                    # Clear any stale values
                    vehicle.estimated_value = None
                    vehicle.deal_score = None
                    vehicle.profit_potential = None
                    vehicle.profit_percentage = None
                    skipped += 1
                    
            except Exception as e:
                logger.warning(f"Error updating vehicle {vehicle.id}: {e}")
                skipped += 1
                continue
        
        db.commit()
        logger.info(f"Valuations updated: {updated} estimated, {skipped} skipped (insufficient data)")


# --- Legacy XGBoost support (for future use) ---

def load_model():
    """Load trained XGBoost model (if available and valid)."""
    try:
        import xgboost as xgb
        
        if not settings.model_path.exists():
            return None
        
        # Check model quality
        metrics_path = settings.models_dir / "model_metrics.json"
        if metrics_path.exists():
            with open(metrics_path, 'r') as f:
                metrics = json.load(f)
            r2 = metrics.get("r2", -1)
            if r2 < 0.3:
                logger.warning(f"XGBoost model has poor R²={r2:.3f}, not using it")
                return None
        
        model = xgb.XGBRegressor()
        model.load_model(str(settings.model_path))
        logger.info("XGBoost model loaded (R² check passed)")
        return model
    except Exception as e:
        logger.debug(f"XGBoost model not available: {e}")
        return None


if __name__ == "__main__":
    # Run valuation update
    update_vehicle_valuations()

"""
Calibrate synthetic-trained model using real listing data.

The synthetic model learns general structure (depreciation, fuel premiums, etc.)
but may have systematic bias vs. real Portuguese market prices.
This script computes a calibration factor from real data and saves it.
"""
import json
import logging
from pathlib import Path

import numpy as np
import pandas as pd
from joblib import load

from config import settings
from database.db import get_db_context
from database.models import Vehicle
from valuation.predict_v3 import predict_price_v3

logger = logging.getLogger(__name__)


def compute_calibration_factor():
    """
    Compute median ratio between real asking prices and model predictions.
    Returns a factor >1.0 if model underpredicts, <1.0 if overpredicts.
    """
    logger.info("Computing calibration factor from real data...")

    # Load synthetic model
    models_dir = settings.models_dir
    pipeline_path = models_dir / "pipeline_v3.joblib"
    if not pipeline_path.exists():
        logger.error(f"No pipeline found at {pipeline_path}")
        return None

    pipeline = load(pipeline_path)

    # Fetch real listings
    records = []
    with get_db_context() as db:
        vehicles = db.query(Vehicle).filter(
            Vehicle.price > 0,
            Vehicle.year > 1900,
            Vehicle.is_active == True,
        ).all()
        for v in vehicles:
            records.append({
                "price": float(v.price),
                "year": int(v.year) if v.year else 2015,
                "km": int(v.km) if v.km else 50000,
                "brand": str(v.brand) if v.brand else "unknown",
                "model": str(v.model) if v.model else "unknown",
                "fuel_type": str(v.fuel_type.value) if v.fuel_type else "gasolina",
                "transmission": str(v.transmission.value) if v.transmission else "manual",
                "location": str(v.location) if v.location else "Lisboa",
                "district": str(v.district) if v.district else "Lisboa",
                "vehicle_type": str(v.vehicle_type.value) if v.vehicle_type else "carros",
            })

    if len(records) < 20:
        logger.warning(f"Insufficient real data for calibration: {len(records)}")
        return None

    ratios = []
    errors = 0
    for r in records:
        try:
            pred = predict_price_v3({
                "brand": r["brand"],
                "model": r["model"],
                "year": r["year"],
                "km": r["km"],
                "fuel_type": r["fuel_type"],
                "transmission": r["transmission"],
                "location": r["location"],
                "district": r["district"],
                "vehicle_type": r["vehicle_type"],
            })
            if pred is None:
                errors += 1
                if errors <= 5:
                    logger.warning(f"Prediction returned None for {r['brand']} {r['model']} {r['year']}")
                continue
            if pred.get("predicted_price") and pred["predicted_price"] > 0:
                ratio = r["price"] / pred["predicted_price"]
                if 0.3 <= ratio <= 3.0:  # Sanity bounds
                    ratios.append(ratio)
            else:
                errors += 1
                if errors <= 5:
                    logger.warning(f"Prediction returned invalid price for {r['brand']} {r['model']}: {pred}")
        except Exception as e:
            errors += 1
            if errors <= 5:
                logger.warning(f"Prediction failed for {r['brand']} {r['model']}: {e}")
            continue

    logger.info(f"Predictions: {len(records)} total, {len(ratios)} valid, {errors} errors")

    if len(ratios) < 10:
        logger.warning(f"Insufficient valid predictions for calibration: {len(ratios)}")
        return None

    median_ratio = float(np.median(ratios))
    mean_ratio = float(np.mean(ratios))
    std_ratio = float(np.std(ratios))

    logger.info(f"Calibration ratios: n={len(ratios)}, median={median_ratio:.3f}, mean={mean_ratio:.3f}, std={std_ratio:.3f}")

    # Save calibration
    calibration = {
        "median_ratio": median_ratio,
        "mean_ratio": mean_ratio,
        "std_ratio": std_ratio,
        "n_samples": len(ratios),
        "computed_at": pd.Timestamp.now().isoformat(),
    }
    cal_path = models_dir / "calibration_v3.json"
    with open(cal_path, "w") as f:
        json.dump(calibration, f, indent=2)
    logger.info(f"Saved calibration to {cal_path}")

    return calibration


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    compute_calibration_factor()

"""
Vehicle Valuation Prediction Module v3
========================================
Production-ready inference using the v3 sklearn Pipeline.

Features:
- Loads the full preprocessing + XGBoost pipeline from disk.
- Replicates exact feature preparation used during training.
- Returns None if the model failed the quality gate.
- Provides a confidence interval based on MAPE from training metrics.
"""
from __future__ import annotations

import json
import logging
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

import numpy as np
import pandas as pd
from joblib import load

from config import settings

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Constants (must match train_model_v3.py)
# ---------------------------------------------------------------------------

LOCATION_PREMIUM_PT: Dict[str, float] = {
    "lisboa": 1.15,
    "porto": 1.10,
    "faro": 1.05,
    "braga": 1.03,
    "coimbra": 1.02,
    "aveiro": 1.02,
    "setubal": 1.02,
    "leiria": 1.00,
    "santarem": 0.98,
    "viseu": 0.98,
    "evora": 0.97,
    "castelo branco": 0.96,
    "portalegre": 0.95,
    "braganca": 0.95,
    "vila real": 0.96,
    "viana do castelo": 0.98,
    "guarda": 0.95,
    "beja": 0.95,
}

DEPRECIATION_BY_AGE: Dict[int, float] = {
    0: 1.00, 1: 0.85, 2: 0.75, 3: 0.68, 4: 0.62, 5: 0.57,
    6: 0.53, 7: 0.49, 8: 0.46, 9: 0.43, 10: 0.40,
    11: 0.38, 12: 0.36, 13: 0.34, 14: 0.32, 15: 0.30,
    16: 0.29, 17: 0.28, 18: 0.27, 19: 0.26, 20: 0.25,
}

FUEL_MARKET_PREMIUM_PT: Dict[str, float] = {
    "eletrico": 1.25,
    "hibrido": 1.12,
    "gasolina": 1.00,
    "gpl": 0.92,
    "diesel": 0.88,
    "gas natural": 0.90,
    "unknown": 1.00,
}

# ---------------------------------------------------------------------------
# Artifact loading
# ---------------------------------------------------------------------------

class ModelArtifactsV3:
    """Holds all loaded v3 artifacts for inference."""

    def __init__(self) -> None:
        self.pipeline: Optional[Any] = None
        self.metrics: Optional[Dict[str, Any]] = None
        self.feature_meta: Optional[Dict[str, Any]] = None
        self.imputation_tables: Optional[Dict[str, Any]] = None
        self._loaded = False

    def load(self, models_dir: Optional[Path] = None) -> bool:
        """Load pipeline, metrics, feature metadata and imputation tables."""
        if self._loaded and self.pipeline is not None:
            return True

        models_dir = models_dir or settings.models_dir
        required_files = {
            "pipeline": models_dir / "pipeline_v3.joblib",
            "metrics": models_dir / "metrics_v3.json",
            "features": models_dir / "features_v3.json",
            "imputation": models_dir / "imputation_v3.joblib",
        }

        # Check existence
        missing = [name for name, path in required_files.items() if not path.exists()]
        if missing:
            logger.warning(f"Missing v3 artifacts: {missing}")
            return False

        # Quality gate check
        try:
            with open(required_files["metrics"], "r", encoding="utf-8") as f:
                self.metrics = json.load(f)
        except Exception as e:
            logger.warning(f"Failed to load metrics: {e}")
            return False

        if not self.metrics.get("passed_gate", False):
            logger.warning(
                "v3 model did NOT pass quality gate — inference disabled. "
                f"Reasons: {self.metrics.get('rejection_reasons', 'unknown')}"
            )
            return False

        # Load pipeline
        try:
            self.pipeline = load(required_files["pipeline"])
        except Exception as e:
            logger.error(f"Failed to load pipeline: {e}")
            return False

        # Load feature metadata
        try:
            with open(required_files["features"], "r", encoding="utf-8") as f:
                self.feature_meta = json.load(f)
        except Exception as e:
            logger.warning(f"Failed to load feature metadata: {e}")
            return False

        # Load imputation tables
        try:
            self.imputation_tables = load(required_files["imputation"])
        except Exception as e:
            logger.warning(f"Failed to load imputation tables: {e}")
            self.imputation_tables = {"brand_median_hp": {}, "brand_median_cc": {}}

        self._loaded = True
        logger.info("v3 model artifacts loaded successfully")
        return True

    @property
    def mape(self) -> float:
        """Return training MAPE for confidence-interval calculation."""
        if self.metrics is None:
            return 15.0  # conservative default
        return float(self.metrics.get("test_mape", 15.0))

    @property
    def feature_names(self) -> List[str]:
        if self.feature_meta is None:
            return []
        return self.feature_meta.get("feature_names", [])

    @property
    def numeric_features(self) -> List[str]:
        if self.feature_meta is None:
            return []
        return self.feature_meta.get("numeric_features", [])

    @property
    def categorical_features(self) -> List[str]:
        if self.feature_meta is None:
            return []
        return self.feature_meta.get("categorical_features", [])


# Singleton cache
_ARTIFACTS: Optional[ModelArtifactsV3] = None


def _get_artifacts() -> Optional[ModelArtifactsV3]:
    """Return cached artifacts, loading if necessary."""
    global _ARTIFACTS
    if _ARTIFACTS is None:
        _ARTIFACTS = ModelArtifactsV3()
        if not _ARTIFACTS.load():
            _ARTIFACTS = None
    return _ARTIFACTS


def clear_artifact_cache() -> None:
    """Clear the singleton artifact cache (useful for testing)."""
    global _ARTIFACTS
    _ARTIFACTS = None
    logger.info("v3 artifact cache cleared")


# ---------------------------------------------------------------------------
# Feature preparation (must match train_model_v3.py exactly)
# ---------------------------------------------------------------------------

def _safe_str(val: Any, default: str = "unknown") -> str:
    if val is None:
        return default
    s = str(val).strip().lower()
    return s if s else default


def _safe_int(val: Any, default: int = 0) -> int:
    try:
        return int(val) if val is not None else default
    except (ValueError, TypeError):
        return default


def _get_depreciation_factor(age: int) -> float:
    if age < 0:
        return 1.0
    if age > 20:
        return 0.20
    return DEPRECIATION_BY_AGE.get(age, 0.25)


def _get_fuel_market_premium(fuel_type: str) -> float:
    return FUEL_MARKET_PREMIUM_PT.get(fuel_type.lower().strip(), 1.0)


def _get_location_premium(district: str) -> float:
    return LOCATION_PREMIUM_PT.get(district.lower().strip(), 1.0)


def _impute_horsepower(row: pd.Series, tables: Dict[str, Any]) -> float:
    val = row.get("horsepower")
    if pd.notna(val) and val > 0:
        return float(val)
    brand = row.get("brand", "unknown")
    median = tables.get("brand_median_hp", {}).get(brand)
    if median is not None and median > 0:
        return float(median)
    return 0.0


def _impute_engine_size(row: pd.Series, tables: Dict[str, Any]) -> float:
    val = row.get("engine_size")
    if pd.notna(val) and val > 0:
        return float(val)
    brand = row.get("brand", "unknown")
    median = tables.get("brand_median_cc", {}).get(brand)
    if median is not None and median > 0:
        return float(median)
    return 0.0


def prepare_features(
    vehicle_data: Dict[str, Any],
    artifacts: Optional[ModelArtifactsV3] = None,
) -> Optional[pd.DataFrame]:
    """
    Prepare a single-row DataFrame with the exact feature schema expected
    by the v3 pipeline.

    Parameters
    ----------
    vehicle_data : dict
        Raw vehicle dictionary from the API / scraper.
    artifacts : ModelArtifactsV3, optional
        Pre-loaded artifacts (avoids re-loading from disk).

    Returns
    -------
    pd.DataFrame or None
        One-row DataFrame ready for pipeline.predict(), or None on error.
    """
    artifacts = artifacts or _get_artifacts()
    if artifacts is None:
        return None

    current_year = datetime.now().year

    # Raw fields
    year = _safe_int(vehicle_data.get("year"), 2015)
    km = _safe_int(vehicle_data.get("km"), 0)
    age = max(0, current_year - year)

    brand = _safe_str(vehicle_data.get("brand"))
    model_name = _safe_str(vehicle_data.get("model"))
    fuel_type = _safe_str(vehicle_data.get("fuel_type"))
    transmission = _safe_str(vehicle_data.get("transmission"))
    district = _safe_str(vehicle_data.get("district"))
    vehicle_type = _safe_str(vehicle_data.get("vehicle_type"), "carros")

    horsepower = _safe_int(vehicle_data.get("horsepower"), 0)
    engine_size = _safe_int(vehicle_data.get("engine_size"), 0)

    # Build base row
    row: Dict[str, Any] = {
        "year": year,
        "km": km,
        "age": age,
        "km_per_year": km / max(age, 1),
        "horsepower": horsepower,
        "engine_size": engine_size,
        "brand": brand,
        "model": model_name,
        "fuel_type": fuel_type,
        "transmission": transmission,
        "vehicle_type": vehicle_type,
        "district": district,
    }

    df = pd.DataFrame([row])

    # Fixed market features (deterministic — same as training)
    df["depreciation_factor"] = df["age"].apply(_get_depreciation_factor)
    df["fuel_market_premium"] = df["fuel_type"].apply(_get_fuel_market_premium)
    df["location_premium"] = df["district"].apply(_get_location_premium)
    df["is_moto"] = df["vehicle_type"].apply(
        lambda x: 1 if str(x).lower() in {"moto", "motos", "scooter", "quad"} else 0
    )
    df["log_km"] = np.log1p(df["km"].clip(lower=0))

    # Impute missing HP / CC using brand medians from training
    tables = artifacts.imputation_tables or {"brand_median_hp": {}, "brand_median_cc": {}}
    df["horsepower"] = df.apply(lambda r: _impute_horsepower(r, tables), axis=1)
    df["engine_size"] = df.apply(lambda r: _impute_engine_size(r, tables), axis=1)

    # Ensure exact column order and fill missing
    feature_names = artifacts.feature_names
    for col in feature_names:
        if col not in df.columns:
            df[col] = 0.0 if col in artifacts.numeric_features else "unknown"

    return df[feature_names]


# ---------------------------------------------------------------------------
# Prediction API
# ---------------------------------------------------------------------------

def predict_price_v3(
    vehicle_data: Dict[str, Any],
    return_interval: bool = True,
) -> Optional[Dict[str, Any]]:
    """
    Predict vehicle price using the v3 production pipeline.

    Parameters
    ----------
    vehicle_data : dict
        Vehicle dictionary with keys: brand, model, year, km, fuel_type,
        transmission, district, vehicle_type, horsepower, engine_size, etc.
    return_interval : bool
        If True, include a confidence interval based on training MAPE.

    Returns
    -------
    dict or None
        {
            "predicted_price": float,
            "confidence_interval": (low, high) | None,
            "confidence_level": 0.80,
            "model_version": "v3",
            "model_mape": float,
        }
        Returns None if model is not available or failed quality gate.
    """
    artifacts = _get_artifacts()
    if artifacts is None or artifacts.pipeline is None:
        logger.debug("v3 model not available — returning None")
        return None

    try:
        X = prepare_features(vehicle_data, artifacts=artifacts)
        if X is None or X.empty:
            logger.warning("Feature preparation failed for vehicle")
            return None

        prediction = float(artifacts.pipeline.predict(X)[0])
        prediction = max(prediction, 500.0)  # floor at €500

        result: Dict[str, Any] = {
            "predicted_price": round(prediction, 2),
            "model_version": "v3",
            "model_mape": round(artifacts.mape, 2),
        }

        if return_interval:
            mape = artifacts.mape / 100.0
            # 80% confidence interval ≈ ±1.28 * MAPE (normal approx)
            # Use a slightly conservative multiplier for pricing safety
            margin = 1.5 * mape
            low = prediction * (1 - margin)
            high = prediction * (1 + margin)
            result["confidence_interval"] = (round(low, 2), round(high, 2))
            result["confidence_level"] = 0.80

        logger.info(
            f"v3 prediction: €{result['predicted_price']:,.2f} "
            f"(MAPE={artifacts.mape:.1f}%)"
        )
        return result

    except Exception as e:
        logger.error(f"Prediction error: {e}")
        return None


def predict_price_v3_simple(vehicle_data: Dict[str, Any]) -> Optional[float]:
    """
    Convenience wrapper that returns only the predicted price (or None).

    Parameters
    ----------
    vehicle_data : dict
        Raw vehicle dictionary.

    Returns
    -------
    float or None
        Predicted price in EUR.
    """
    result = predict_price_v3(vehicle_data, return_interval=False)
    if result is None:
        return None
    return result.get("predicted_price")


def predict_batch_v3(vehicles: List[Dict[str, Any]]) -> List[Optional[Dict[str, Any]]]:
    """
    Predict prices for a batch of vehicles.

    Parameters
    ----------
    vehicles : list of dict
        List of vehicle dictionaries.

    Returns
    -------
    list of dict or None
        Same length as input; None for vehicles that could not be predicted.
    """
    return [predict_price_v3(v) for v in vehicles]


# ---------------------------------------------------------------------------
# Legacy compatibility
# ---------------------------------------------------------------------------

def estimate_market_value_v3(vehicle_data: Dict[str, Any]) -> Optional[float]:
    """Legacy alias for predict_price_v3_simple."""
    return predict_price_v3_simple(vehicle_data)


# ---------------------------------------------------------------------------
# Module-level helpers for engine integration
# ---------------------------------------------------------------------------

def get_model_status() -> Dict[str, Any]:
    """Return diagnostic information about the v3 model."""
    artifacts = _get_artifacts()
    if artifacts is None:
        return {
            "available": False,
            "version": "v3",
            "reason": "Artifacts missing or quality gate failed",
        }
    return {
        "available": True,
        "version": "v3",
        "metrics": artifacts.metrics,
        "feature_count": len(artifacts.feature_names),
        "numeric_features": artifacts.numeric_features,
        "categorical_features": artifacts.categorical_features,
    }


if __name__ == "__main__":
    # Simple CLI smoke-test
    logging.basicConfig(level=logging.INFO)
    sample = {
        "brand": "Volkswagen",
        "model": "Golf",
        "year": 2018,
        "km": 80_000,
        "fuel_type": "gasolina",
        "transmission": "manual",
        "district": "Lisboa",
        "vehicle_type": "carros",
        "horsepower": 110,
        "engine_size": 1395,
    }
    print(predict_price_v3(sample))

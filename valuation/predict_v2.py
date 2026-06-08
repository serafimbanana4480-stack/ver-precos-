"""
Vehicle Valuation Prediction Module v2
Uses the improved XGBoost model with proper feature engineering.
"""

import logging
from typing import Optional, Dict, Any
import pandas as pd
import numpy as np
from pathlib import Path
from joblib import load
import json

from config import settings

logger = logging.getLogger(__name__)


class VehicleValuationModelV2:
    """Improved XGBoost-based vehicle valuation model."""

    def __init__(self):
        self.model = None
        self.encoders = None
        self.feature_names = None
        self.models_dir = settings.models_dir
        self._load_artifacts()

    def _load_artifacts(self) -> bool:
        """Load model, encoders and feature names."""
        try:
            import xgboost as xgb

            model_path = self.models_dir / "xgboost_carros.json"
            encoders_path = self.models_dir / "encoders_carros.joblib"
            features_path = self.models_dir / "feature_names.json"

            if not model_path.exists():
                logger.warning(f"Model not found at {model_path}")
                return False

            self.model = xgb.XGBRegressor()
            self.model.load_model(str(model_path))

            if encoders_path.exists():
                self.encoders = load(encoders_path)

            if features_path.exists():
                with open(features_path) as f:
                    self.feature_names = json.load(f)

            logger.info(f"Model v2 loaded from {model_path}")
            return True

        except Exception as e:
            logger.error(f"Error loading model artifacts: {e}")
            return False

    def _prepare_features(self, vehicle_data: Dict[str, Any]) -> pd.DataFrame:
        """Prepare features matching the training pipeline."""
        current_year = pd.Timestamp.now().year

        # Base features
        year = int(vehicle_data.get("year", 2015))
        km = int(vehicle_data.get("km", 0))
        age = current_year - year

        # Categorical features with defaults
        brand = str(vehicle_data.get("brand", "unknown")).strip().lower()
        model_name = str(vehicle_data.get("model", "unknown")).strip().lower()
        fuel_type = str(vehicle_data.get("fuel_type", "unknown")).strip().lower()
        transmission = str(vehicle_data.get("transmission", "unknown")).strip().lower()
        district = str(vehicle_data.get("district", "unknown")).strip().lower()
        vehicle_type = str(vehicle_data.get("vehicle_type", "carros")).strip().lower()
        source = str(vehicle_data.get("source", "unknown")).strip().lower()

        # Brand tier
        luxury_brands = {"bmw", "mercedes-benz", "audi", "lexus", "jaguar", "porsche", "volvo", "land rover"}
        economy_brands = {"dacia", "fiat", "hyundai", "kia", "suzuki", "chevrolet"}
        brand_tier = "luxury" if brand in luxury_brands else ("economy" if brand in economy_brands else "standard")

        # Vehicle type flags
        is_suv = 1 if any(x in model_name for x in ["suv", "cross", "x5", "x3", "q5", "q7", "glc", "gle"]) else 0
        is_sedan = 1 if any(x in model_name for x in ["sedan", "berlina"]) else 0

        # Encode categoricals
        row = {
            "year": year,
            "km": km,
            "age": age,
            "km_per_year": km / max(age, 1),
            "log_km": np.log1p(km),
            "is_suv": is_suv,
            "is_sedan": is_sedan,
            "source_premium": 1.0,
            "district_premium": 1.0,
            "fuel_premium": 1.0,
        }

        # Apply encoders
        if self.encoders:
            for col in ["brand", "model", "fuel_type", "transmission", "district", "vehicle_type", "source", "brand_tier"]:
                le = self.encoders.get(col)
                val = locals().get(col, "unknown")
                if le is not None:
                    if val in le.classes_:
                        row[f"{col}_encoded"] = le.transform([val])[0]
                    else:
                        row[f"{col}_encoded"] = 0
                else:
                    row[f"{col}_encoded"] = 0

        df = pd.DataFrame([row])

        # Ensure all expected features exist
        if self.feature_names:
            for feat in self.feature_names:
                if feat not in df.columns:
                    df[feat] = 0
            df = df[self.feature_names]

        return df

    def predict_price(self, vehicle_data: Dict[str, Any]) -> Optional[float]:
        """Predict vehicle price."""
        if self.model is None:
            if not self._load_artifacts():
                return None

        try:
            X = self._prepare_features(vehicle_data)
            prediction = self.model.predict(X)[0]
            return float(max(prediction, 500))  # Minimum realistic price
        except Exception as e:
            logger.error(f"Prediction error: {e}")
            return None

    def predict_batch(self, vehicles: list) -> list:
        """Predict prices for multiple vehicles."""
        return [self.predict_price(v) for v in vehicles]


def estimate_market_value_v2(vehicle_data: Dict[str, Any]) -> Optional[float]:
    """Estimate market value using the v2 model."""
    model = VehicleValuationModelV2()
    return model.predict_price(vehicle_data)


# Legacy compatibility
def estimate_market_value(vehicle: Any) -> Optional[float]:
    """Legacy compatibility - tries v2 first, falls back to v1."""
    if isinstance(vehicle, dict):
        result = estimate_market_value_v2(vehicle)
        if result is not None:
            return result
        # Fallback to old model
        from valuation.predict import VehicleValuationModel
        m = VehicleValuationModel()
        return m.predict_price(vehicle)
    return None

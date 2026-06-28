"""
Unified vehicle valuation prediction module.
Uses FeatureStore for consistent feature computation with dynamic brand index.
"""
from __future__ import annotations
import json
import logging
import numpy as np
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

from joblib import load
from core.settings import settings
from valuation.feature_store import FeatureStore

logger = logging.getLogger(__name__)


class PricePredictor:
    """Production inference pipeline. Loads best model + brand index from disk."""

    def __init__(self, vehicle_type: str = "carros"):
        self.vehicle_type = vehicle_type
        self.model = None
        self.model_name = None
        self.scaler = None
        self.feature_names: List[str] = []
        self.metrics: Dict[str, float] = {}
        self.fs = FeatureStore()
        self._load_model()

    def _load_model(self) -> None:
        model_dir = Path(settings.models_dir)
        metadata_path = model_dir / f"best_model_{self.vehicle_type}.json"
        if not metadata_path.exists():
            logger.warning(f"No model metadata at {metadata_path}")
            return
        try:
            with open(metadata_path) as f:
                meta = json.load(f)
            self.model_name = meta.get("model_type", "xgboost")
            self.metrics = meta.get("metrics", {})
            self.feature_names = meta.get("feature_names", [])

            self.fs.load_index(model_dir / meta.get("brand_index_path", f"brand_index_{self.vehicle_type}.json"))

            import_path = model_dir / meta["model_path"]
            if self.model_name == "xgboost":
                import xgboost as xgb
                self.model = xgb.XGBRegressor()
                self.model.load_model(str(import_path))
            elif self.model_name == "lightgbm":
                import lightgbm as lgb
                self.model = lgb.Booster(model_file=str(import_path))
            elif self.model_name == "catboost":
                from catboost import CatBoostRegressor
                self.model = CatBoostRegressor()
                self.model.load_model(str(import_path))
            else:
                logger.error(f"Unknown model type: {self.model_name}")
                return

            scaler_path = model_dir / meta.get("scaler_path", f"scaler_{self.vehicle_type}.joblib")
            if scaler_path.exists():
                self.scaler = load(str(scaler_path))

            logger.info(f"Loaded {self.model_name} for {self.vehicle_type} (R²={self.metrics.get('r2', 'N/A')})")
        except Exception as e:
            logger.error(f"Failed to load model: {e}")

    def predict(self, vehicle_data: Dict[str, Any]) -> Optional[float]:
        if self.model is None:
            return None
        try:
            features = self.fs.compute_features(vehicle_data)
            X = np.array([[features.get(f, 0.0) for f in self.feature_names]])
            if self.scaler:
                X = self.scaler.transform(X)
            pred = float(self.model.predict(X)[0])
            return max(pred, 0.0)
        except Exception as e:
            logger.error(f"Prediction error: {e}")
            return None

    def predict_with_interval(self, vehicle_data: Dict[str, Any]) -> Optional[Tuple[float, float, float]]:
        pred = self.predict(vehicle_data)
        if pred is None:
            return None
        mape = self.metrics.get("mape_pct", 30.0) / 100.0
        margin = pred * mape
        return (pred - margin, pred, pred + margin)


def update_vehicle_valuations(batch_size: int = 100) -> int:
    from database.db import get_db_context
    from database.models import Vehicle

    predictor_car = PricePredictor("carros")
    predictor_moto = PricePredictor("motos")
    updated = 0

    with get_db_context() as db:
        vehicles = db.query(Vehicle).filter(Vehicle.estimated_value.is_(None)).limit(batch_size).all()
        for v in vehicles:
            ft = v.fuel_type.value if v.fuel_type else "unknown"
            tr = v.transmission.value if v.transmission else "unknown"
            data = {
                "year": v.year, "km": v.km, "horsepower": v.horsepower,
                "engine_size": v.engine_size, "doors": v.doors,
                "fuel_type": ft, "transmission": tr,
                "brand": v.brand or "Unknown", "location": v.location or "",
            }
            predictor = predictor_car if v.vehicle_type.value == "carros" else predictor_moto
            pred = predictor.predict(data)
            if pred is not None:
                v.estimated_value = round(pred, 2)
                updated += 1
        db.commit()

    logger.info(f"Updated {updated} vehicle valuations")
    return updated

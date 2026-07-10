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
        # Segmented (low-end) model for two-stage routing
        self.low_model = None
        self.low_scaler = None
        self.low_threshold: Optional[float] = None
        # Segmented (high-end) CatBoost model for three-way routing
        self.high_model = None
        self.high_scaler = None
        self.high_threshold: Optional[float] = None
        self.high_log_target: bool = False
        self.high_cat_features: List[int] = []
        self.full_log_target: bool = False
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
            self.low_threshold = meta.get("low_threshold")
            self.high_threshold = meta.get("high_threshold")
            self.high_log_target = meta.get("high_log_target", False)
            self.high_cat_features = meta.get("high_cat_features", [])
            self.full_log_target = meta.get("full_log_target", False)

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

            # --- Load optional LOW-end model for two-stage routing ---
            low_model_path = meta.get("low_model_path")
            if low_model_path:
                low_path = model_dir / low_model_path
                if low_path.exists():
                    import xgboost as xgb
                    self.low_model = xgb.XGBRegressor()
                    self.low_model.load_model(str(low_path))
                    low_scaler_path = model_dir / meta.get("low_scaler_path", f"scaler_{self.vehicle_type}_low.joblib")
                    if low_scaler_path.exists():
                        self.low_scaler = load(str(low_scaler_path))

            # --- Load optional HIGH-end model (CatBoost) for three-way routing ---
            high_model_path = meta.get("high_model_path")
            if high_model_path:
                high_path = model_dir / high_model_path
                if high_path.exists():
                    from catboost import CatBoostRegressor
                    self.high_model = CatBoostRegressor()
                    high_fmt = "json" if str(high_path).endswith(".json") else "cbm"
                    self.high_model.load_model(str(high_path), format=high_fmt)
                    high_scaler_path = model_dir / meta.get("high_scaler_path", f"scaler_{self.vehicle_type}_high.joblib")
                    if high_scaler_path.exists():
                        self.high_scaler = load(str(high_scaler_path))

            logger.info(f"Loaded {self.model_name} for {self.vehicle_type} (R²={self.metrics.get('r2', 'N/A')})"
                        f"{' + LOW model' if self.low_model else ''}"
                        f"{' + HIGH model' if self.high_model else ''}")
        except Exception as e:
            logger.error(f"Failed to load model: {e}")

    def predict(self, vehicle_data: Dict[str, Any]) -> Optional[float]:
        if self.model is None:
            return None
        try:
            features = self.fs.compute_features(vehicle_data)
            X = np.array([[features.get(f, 0.0) for f in self.feature_names]])

            # --- Three-way routing (LOW / FULL / HIGH) ---
            if self.scaler:
                X_full = self.scaler.transform(X)
            else:
                X_full = X
            full_pred = float(self.model.predict(X_full)[0])
            if self.full_log_target:
                full_pred = float(np.expm1(full_pred))
            full_pred = max(full_pred, 0.0)

            # High-end: use CatBoost dedicated model for expensive cars.
            # This model uses native categorical features (string cols) and an
            # optional log-target; no scaler. Falls back to scaler if configured.
            if self.high_model is not None and self.high_threshold and full_pred >= self.high_threshold:
                if self.high_cat_features:
                    X_high = X.astype(object)
                    for c in self.high_cat_features:
                        X_high[0, c] = str(int(X_high[0, c]))
                elif self.high_scaler is not None:
                    X_high = self.high_scaler.transform(X)
                else:
                    X_high = X
                high_pred = float(self.high_model.predict(X_high)[0])
                if self.high_log_target:
                    high_pred = float(np.expm1(high_pred))
                return max(high_pred, 0.0)

            # Low-end: use dedicated model for cheap cars (< low_threshold)
            if (self.low_model is not None and self.low_scaler is not None
                    and self.low_threshold and full_pred < self.low_threshold):
                X_low = self.low_scaler.transform(X)
                low_pred = float(self.low_model.predict(X_low)[0])
                return max(low_pred, 0.0)

            return full_pred
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
    from valuation.hybrid_valuator import get_valuator

    valuator = get_valuator()
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
                "brand": v.brand or "Unknown", "model": v.model or "",
                "location": v.location or "",
                "source": v.source.value if v.source else "",
                "vehicle_type": v.vehicle_type.value if v.vehicle_type else "carros",
                "title": v.title or "",
                "price": v.price or 0,
                "condition_score": v.condition_score or 3.0,
            }
            pred = valuator.estimate_value(data)
            if pred is not None:
                v.estimated_value = round(pred, 2)
                updated += 1
        db.commit()

    logger.info(f"Updated {updated} vehicle valuations")
    return updated

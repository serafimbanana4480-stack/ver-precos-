"""
Unified ML training pipeline.
Supports XGBoost, LightGBM, CatBoost with auto-selection of best model.
Uses TimeSeriesSplit to prevent data leakage.
"""
from __future__ import annotations
import json
import logging
from datetime import datetime
from pathlib import Path
from typing import Dict, Optional

import numpy as np
import pandas as pd
from sklearn.model_selection import TimeSeriesSplit
from sklearn.preprocessing import StandardScaler
from sklearn.metrics import mean_absolute_error, r2_score, mean_absolute_percentage_error
from joblib import dump

from core.settings import settings
from valuation.feature_store import FeatureStore

logger = logging.getLogger(__name__)


def _val_str(val) -> str:
    if val is None:
        return "unknown"
    if hasattr(val, "value"):
        return val.value
    return str(val)


def load_raw_data(vehicle_type: str = "carros") -> pd.DataFrame:
    from database.db import get_db_context
    from database.models import Vehicle, VehicleType

    with get_db_context() as db:
        query = db.query(Vehicle).filter(
            Vehicle.vehicle_type == VehicleType(vehicle_type),
            Vehicle.price > 500,
            Vehicle.price < 500000,
            Vehicle.year.isnot(None),
        )
        # For cars, require KM data (essential); for motorcycles be more lenient
        if vehicle_type == "carros":
            query = query.filter(Vehicle.km.isnot(None), Vehicle.km > 0)
        
        rows = query.all()

        records = [{
            "year": v.year, "km": v.km or 0,
            "horsepower": v.horsepower or 0, "engine_size": v.engine_size or 0,
            "doors": v.doors or 4,
            "fuel_type": _val_str(v.fuel_type),
            "transmission": _val_str(v.transmission),
            "brand": v.brand or "Unknown",
            "model": v.model or "",
            "location": v.location or "",
            "price": v.price,
            "first_seen": v.first_seen,
        } for v in rows]

    df = pd.DataFrame(records)
    logger.info(f"Loaded {len(df)} rows for {vehicle_type}")
    return df


def train_model(vehicle_type: str = "carros", force_retrain: bool = False) -> Optional[Dict]:
    raw = load_raw_data(vehicle_type)
    if len(raw) < settings.ml_min_samples:
        logger.warning(f"Only {len(raw)} samples for {vehicle_type}, need {settings.ml_min_samples}")
        return None

    fs = FeatureStore()
    fs.build_brand_index(raw["brand"].tolist())
    fs.build_model_index(raw["model"].tolist())

    records = []
    for r in raw.to_dict("records"):
        feat = fs.compute_features(r)
        feat["price"] = r["price"]
        records.append(feat)
    df = pd.DataFrame(records).dropna(subset=["price"]).fillna(0)

    feature_cols = FeatureStore.ALLOWED_FEATURES
    X = df[feature_cols].values
    y = df["price"].values

    if np.any(y <= 0):
        logger.warning(f"Removing {int((y <= 0).sum())} rows with non-positive price")
        mask = y > 0
        X, y = X[mask], y[mask]

    scaler = StandardScaler()
    X_scaled = scaler.fit_transform(X)

    tscv = TimeSeriesSplit(n_splits=5)
    results = {}

    models = {}

    try:
        import xgboost as xgb
        xgb_model = xgb.XGBRegressor(
            n_estimators=500, max_depth=8, learning_rate=0.03,
            subsample=0.8, colsample_bytree=0.8,
            min_child_weight=3, reg_lambda=2.0, reg_alpha=1.0,
            random_state=42,
        )
        models["xgboost"] = xgb_model
    except ImportError:
        logger.warning("XGBoost not installed")

    try:
        import lightgbm as lgb
        lgb_model = lgb.LGBMRegressor(
            n_estimators=500, max_depth=8, learning_rate=0.03,
            subsample=0.8, colsample_bytree=0.8,
            min_child_samples=5, reg_lambda=2.0, reg_alpha=1.0,
            random_state=42, verbose=-1,
        )
        models["lightgbm"] = lgb_model
    except ImportError:
        logger.warning("LightGBM not installed")

    try:
        from catboost import CatBoostRegressor
        cat_model = CatBoostRegressor(
            iterations=500, depth=8, learning_rate=0.03,
            subsample=0.8, random_seed=42, verbose=False,
            l2_leaf_reg=2.0,
        )
        models["catboost"] = cat_model
    except ImportError:
        logger.warning("CatBoost not installed")

    if not models:
        logger.error("No ML framework available. Install xgboost, lightgbm, or catboost.")
        return None

    best_r2 = -1e9
    best_model = None
    best_name = None

    for name, model in models.items():
        cv_r2 = []
        cv_mae = []
        cv_mape = []

        for train_idx, test_idx in tscv.split(X_scaled):
            X_train, X_test = X_scaled[train_idx], X_scaled[test_idx]
            y_train, y_test = y[train_idx], y[test_idx]

            model.fit(X_train, y_train)
            y_pred = model.predict(X_test)

            cv_r2.append(r2_score(y_test, y_pred))
            cv_mae.append(mean_absolute_error(y_test, y_pred))
            cv_mape.append(mean_absolute_percentage_error(y_test, y_pred) * 100)

        avg_r2 = np.mean(cv_r2)
        avg_mae = np.mean(cv_mae)
        avg_mape = np.mean(cv_mape)

        results[name] = {"r2": float(avg_r2), "mae": float(avg_mae), "mape_pct": float(avg_mape)}

        logger.info(f"{name} CV R²={avg_r2:.4f} MAE=€{avg_mae:.0f} MAPE={avg_mape:.1f}%")

        if avg_r2 > best_r2 and avg_r2 >= settings.ml_min_r2:
            best_r2 = avg_r2
            best_model = model
            best_name = name

    if best_model is None:
        if not models:
            return {"metrics": results, "status": "failed", "best_r2": float(best_r2)}
        best_name = max(results, key=lambda k: results[k]["r2"])
        best_model = models[best_name]
        best_r2 = results[best_name]["r2"]
        logger.warning(f"No model met R²>={settings.ml_min_r2}. "
                       f"Saving best: {best_name} (R²={best_r2:.4f})")

    logger.info(f"Training final {best_name} model on all data...")
    best_model.fit(X_scaled, y)
    model_dir = Path(settings.models_dir)
    model_dir.mkdir(exist_ok=True)

    ext_map = {"xgboost": "json", "lightgbm": "txt", "catboost": "cbm"}
    ext = ext_map.get(best_name, "json")
    model_path = f"model_{vehicle_type}.{ext}"

    if best_name == "xgboost":
        best_model.save_model(str(model_dir / model_path))
    elif best_name == "lightgbm":
        best_model.booster_.save_model(str(model_dir / model_path))
    elif best_name == "catboost":
        best_model.save_model(str(model_dir / model_path))

    dump(scaler, str(model_dir / f"scaler_{vehicle_type}.joblib"))

    fs.save_index(model_dir / f"brand_index_{vehicle_type}.json")

    metadata = {
        "model_type": best_name,
        "model_path": model_path,
        "scaler_path": f"scaler_{vehicle_type}.joblib",
        "brand_index_path": f"brand_index_{vehicle_type}.json",
        "vehicle_type": vehicle_type,
        "feature_names": feature_cols,
        "metrics": results[best_name],
        "n_samples": len(df),
        "trained_at": datetime.now().isoformat(),
    }

    with open(model_dir / f"best_model_{vehicle_type}.json", "w") as f:
        json.dump(metadata, f, indent=2)

    logger.info(f"{best_name} model for {vehicle_type}: R²={best_r2:.4f}, MAE=€{results[best_name]['mae']:.0f}")
    return metadata


def train_all_models(force_retrain: bool = False) -> Dict[str, Optional[Dict]]:
    results = {}
    for vtype in ["carros", "motos"]:
        logger.info(f"Training {vtype} model...")
        results[vtype] = train_model(vtype, force_retrain)
    return results


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    results = train_all_models(force_retrain=True)
    print(json.dumps({k: v.get("metrics") if v else None for k, v in results.items()}, indent=2))

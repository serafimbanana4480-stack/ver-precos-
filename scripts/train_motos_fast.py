"""Fast motos re-train (no Optuna) for the ~230-sample motos set.

The full valuation.train pipeline runs 50 Optuna trials x3 models which is
overkill for ~230 samples and takes >1h. This produces a documented, honest
R2 on a held-out test split in seconds, using the existing FeatureStore API.
"""
from __future__ import annotations
import json
import logging
import sys
from datetime import datetime
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import numpy as np
import pandas as pd
from sklearn.model_selection import train_test_split
from sklearn.preprocessing import StandardScaler
from sklearn.metrics import mean_absolute_error, r2_score, mean_absolute_percentage_error
from joblib import dump

from valuation.feature_store import FeatureStore
from valuation.train import load_raw_data, remove_outliers_isolation_forest

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("train_motos_fast")

MODEL_DIR = Path(__file__).resolve().parent.parent / "models"


def main():
    raw = load_raw_data("motos")
    logger.info("Loaded %d raw rows for motos", len(raw))

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
    mask = y > 0
    X, y = X[mask], y[mask]

    X, y = remove_outliers_isolation_forest(X, y, contamination=0.1)
    logger.info("Motos samples after cleaning: %d", len(X))

    X_train, X_test, y_train, y_test = train_test_split(
        X, y, test_size=0.2, random_state=42
    )
    scaler = StandardScaler().fit(X_train)
    X_train_s = scaler.transform(X_train)
    X_test_s = scaler.transform(X_test)

    import xgboost as xgb

    model = xgb.XGBRegressor(
        n_estimators=400, max_depth=5, learning_rate=0.05,
        subsample=0.8, colsample_bytree=0.8, reg_lambda=1.0,
        n_jobs=-1, random_state=42,
    )
    model.fit(X_train_s, y_train)
    y_pred = model.predict(X_test_s)

    r2 = r2_score(y_test, y_pred)
    mae = mean_absolute_error(y_test, y_pred)
    mape = mean_absolute_percentage_error(y_test, y_pred) * 100
    logger.info("MOTOS test R2=%.4f MAE=%.0f MAPE=%.1f%%", r2, mae, mape)

    model.save_model(str(MODEL_DIR / "model_motos.json"))
    dump(scaler, str(MODEL_DIR / "scaler_motos.joblib"))
    fs.save_index(MODEL_DIR / "brand_index_motos.json")

    metadata = {
        "model_type": "xgboost",
        "model_path": "model_motos.json",
        "scaler_path": "scaler_motos.joblib",
        "brand_index_path": "brand_index_motos.json",
        "vehicle_type": "motos",
        "feature_names": list(feature_cols),
        "metrics": {"r2": float(r2), "mae": float(mae), "mape_pct": float(mape)},
        "n_samples": int(len(X)),
        "trained_at": datetime.now().isoformat(),
        "optimizations": {"optuna_tuning": False, "fast_retrain": True,
                           "isolation_forest": True},
    }
    with open(MODEL_DIR / "best_model_motos.json", "w") as f:
        json.dump(metadata, f, indent=2)
    logger.info("Saved best_model_motos.json")


if __name__ == "__main__":
    main()

"""
Train a secondary XGBoost model on REAL data only (asking prices).
This model captures the real market distribution and can be ensemble'd
with the synthetic-trained model for better real-world performance.
"""
import json
import logging
from datetime import datetime, timezone
from pathlib import Path

import numpy as np
import pandas as pd
import xgboost as xgb
from joblib import dump
from sklearn.compose import ColumnTransformer
from sklearn.impute import SimpleImputer
from sklearn.metrics import mean_absolute_error, mean_squared_error, r2_score
from sklearn.model_selection import train_test_split
from sklearn.pipeline import Pipeline
from sklearn.preprocessing import OrdinalEncoder, StandardScaler

from config import settings
from database.db import get_db_context
from database.models import Vehicle

logger = logging.getLogger(__name__)

# Same feature engineering as train_model_v3
from valuation.train_model_v3 import (
    clean_outliers,
    engineer_features,
    _build_brand_imputation_tables,
    _impute_horsepower,
    _impute_engine_size,
    LOCATION_PREMIUM_PT,
    DEPRECIATION_BY_AGE,
    FUEL_MARKET_PREMIUM_PT,
)


def fetch_real_training_data():
    """Fetch only real listing data (asking prices) from the database."""
    records = []
    with get_db_context() as db:
        vehicles = db.query(Vehicle).filter(
            Vehicle.price > 0,
            Vehicle.year > 1900,
            Vehicle.is_active == True,
        ).all()
        for v in vehicles:
            records.append({
                "target_price": float(v.price),
                "target_source": "listing_asking",
                "year": int(v.year) if v.year else 2015,
                "km": int(v.km) if v.km else 50000,
                "horsepower": int(v.horsepower) if v.horsepower else 0,
                "engine_size": int(v.engine_size) if v.engine_size else 0,
                "brand": str(v.brand) if v.brand else "unknown",
                "model": str(v.model) if v.model else "unknown",
                "fuel_type": str(v.fuel_type.value) if v.fuel_type else "gasolina",
                "transmission": str(v.transmission.value) if v.transmission else "manual",
                "location": str(v.location) if v.location else "Lisboa",
                "district": str(v.district) if v.district else "Lisboa",
                "vehicle_type": str(v.vehicle_type.value) if v.vehicle_type else "carros",
                "condition_grade": None,
                "has_damage": bool(v.has_damage) if v.has_damage is not None else None,
            })
    logger.info(f"Fetched {len(records)} real listing entries")
    return records


def train_real_only_model():
    """Train XGBoost on real data only."""
    logger.info("=" * 70)
    logger.info("Training REAL-ONLY XGBoost Model")
    logger.info("=" * 70)

    records = fetch_real_training_data()
    if len(records) < 50:
        logger.warning(f"Insufficient real data: {len(records)} samples (minimum 50)")
        return None

    df = pd.DataFrame(records)
    df = clean_outliers(df)
    df = engineer_features(df, fit=False)

    numeric_features = [
        "year", "km", "age", "km_per_year", "horsepower", "engine_size",
        "log_km", "depreciation_factor", "fuel_market_premium",
        "location_premium", "is_moto",
    ]
    categorical_features = ["brand", "model", "fuel_type", "transmission", "vehicle_type"]

    for col in numeric_features + categorical_features:
        if col not in df.columns:
            df[col] = 0 if col in numeric_features else "unknown"

    df = df.dropna(subset=["target_price"])
    if len(df) < 50:
        logger.warning(f"Insufficient data after cleaning: {len(df)}")
        return None

    feature_names = numeric_features + categorical_features
    X = df[feature_names].copy()
    y = df["target_price"].values.astype(np.float64)

    # Train/test split
    if len(df) < 100:
        # For small datasets, use 90/10 split
        X_train, X_test, y_train, y_test = train_test_split(
            X, y, test_size=0.1, random_state=42
        )
    else:
        X_train, X_test, y_train, y_test = train_test_split(
            X, y, test_size=0.2, random_state=42
        )

    logger.info(f"Real-only split: {len(X_train)} train / {len(X_test)} test")

    # Brand imputation
    train_df_for_impute = X_train[["brand", "horsepower", "engine_size"]].copy()
    train_df_for_impute = train_df_for_impute.replace(0, np.nan)
    _build_brand_imputation_tables(train_df_for_impute)

    for split_df in (X_train, X_test):
        split_df["horsepower"] = split_df.apply(_impute_horsepower, axis=1)
        split_df["engine_size"] = split_df.apply(_impute_engine_size, axis=1)

    for col in numeric_features:
        X_train[col] = pd.to_numeric(X_train[col], errors="coerce").fillna(0)
        X_test[col] = pd.to_numeric(X_test[col], errors="coerce").fillna(0)

    # Build pipeline with lighter regularization for small dataset
    numeric_transformer = Pipeline([
        ("imputer", SimpleImputer(strategy="median")),
        ("scaler", StandardScaler()),
    ])
    categorical_transformer = Pipeline([
        ("imputer", SimpleImputer(strategy="constant", fill_value="unknown")),
        ("encoder", OrdinalEncoder(handle_unknown="use_encoded_value", unknown_value=-1)),
    ])
    preprocessor = ColumnTransformer([
        ("num", numeric_transformer, numeric_features),
        ("cat", categorical_transformer, categorical_features),
    ])

    regressor = xgb.XGBRegressor(
        n_estimators=500,
        max_depth=4,
        learning_rate=0.05,
        subsample=0.8,
        colsample_bytree=0.8,
        min_child_weight=5,
        gamma=0.1,
        reg_alpha=0.1,
        reg_lambda=1.0,
        random_state=42,
        n_jobs=-1,
        objective="reg:squarederror",
        early_stopping_rounds=50,
    )

    pipeline = Pipeline([
        ("preprocessor", preprocessor),
        ("regressor", regressor),
    ])

    preprocessor.fit(X_train)
    X_test_processed = preprocessor.transform(X_test)
    pipeline.fit(
        X_train,
        y_train,
        regressor__eval_set=[(X_test_processed, y_test)],
        regressor__verbose=False,
    )

    y_pred = pipeline.predict(X_test)
    r2 = r2_score(y_test, y_pred)
    mae = mean_absolute_error(y_test, y_pred)
    rmse = np.sqrt(mean_squared_error(y_test, y_pred))

    logger.info(f"Real-only model -> R²={r2:.4f}, MAE=€{mae:.2f}, RMSE=€{rmse:.2f}")

    # Save
    models_dir = settings.models_dir
    models_dir.mkdir(parents=True, exist_ok=True)
    dump(pipeline, models_dir / "pipeline_real_only.joblib")
    logger.info(f"Saved real-only model to {models_dir / 'pipeline_real_only.joblib'}")

    metrics = {
        "r2": float(r2),
        "mae": float(mae),
        "rmse": float(rmse),
        "n_samples": len(df),
        "training_date": datetime.now(timezone.utc).isoformat(),
    }
    with open(models_dir / "metrics_real_only.json", "w") as f:
        json.dump(metrics, f, indent=2)

    return pipeline


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    train_real_only_model()

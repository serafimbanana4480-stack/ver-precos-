"""
XGBoost Model Training v2 - Improved Pipeline
Addresses: missing features, outlier handling, better feature engineering,
cross-validation, and proper encoding persistence.
"""
from __future__ import annotations
import logging
import json
from pathlib import Path
from datetime import datetime, timezone
from typing import Optional, Dict, List, Tuple
import numpy as np
import pandas as pd
import xgboost as xgb
from sklearn.model_selection import train_test_split, cross_val_score, KFold
from sklearn.preprocessing import LabelEncoder, StandardScaler
from sklearn.metrics import mean_absolute_error, mean_squared_error, r2_score
from joblib import dump, load

from config import settings
from database.db import get_db_context
from database.models import Vehicle

logger = logging.getLogger(__name__)

# Constants
MIN_TRAINING_SAMPLES = 50
MIN_R2_THRESHOLD = 0.50
MAX_PRICE_OUTLIER = 150_000  # Remove cars above 150k EUR (very rare)
MIN_PRICE = 500  # Remove cars below 500 EUR (likely junk/error)
MAX_AGE = 40  # Remove cars older than 40 years (classic cars are different market)


def fetch_training_data() -> pd.DataFrame:
    """Fetch all usable vehicle data from database."""
    with get_db_context() as db:
        vehicles = db.query(Vehicle).filter(
            Vehicle.is_active == True,
            Vehicle.price.isnot(None),
            Vehicle.year.isnot(None),
            Vehicle.km.isnot(None),
            Vehicle.brand.isnot(None),
            Vehicle.model.isnot(None)
        ).all()

        records = []
        for v in vehicles:
            records.append({
                "price": float(v.price),
                "year": int(v.year) if v.year else None,
                "km": int(v.km) if v.km else 0,
                "brand": str(v.brand).strip() if v.brand else "unknown",
                "model": str(v.model).strip() if v.model else "unknown",
                "fuel_type": v.fuel_type.value if v.fuel_type else "unknown",
                "transmission": v.transmission.value if v.transmission else "unknown",
                "district": str(v.district).strip() if v.district else "unknown",
                "vehicle_type": v.vehicle_type.value if v.vehicle_type else "carros",
                "source": v.source.value if v.source else "unknown",
                "deal_score": float(v.deal_score) if v.deal_score else None,
                "condition_score": float(v.condition_score) if v.condition_score else None,
                "doors": int(v.doors) if v.doors else None,
                "horsepower": int(v.horsepower) if v.horsepower else None,
                "engine_size": int(v.engine_size) if v.engine_size else None,
            })

    df = pd.DataFrame(records)
    logger.info(f"Fetched {len(df)} raw records from database")
    return df


def clean_outliers(df: pd.DataFrame) -> pd.DataFrame:
    """Remove price and age outliers that would hurt model training."""
    n_before = len(df)

    # Price outliers
    df = df[(df["price"] >= MIN_PRICE) & (df["price"] <= MAX_PRICE_OUTLIER)]

    # Age outliers
    current_year = datetime.now().year
    df["age"] = current_year - df["year"]
    df = df[(df["age"] >= 0) & (df["age"] <= MAX_AGE)]

    # KM outliers (cars with > 1M km are likely errors)
    df = df[df["km"] <= 1_000_000]

    n_after = len(df)
    logger.info(f"Outlier cleaning: {n_before} -> {n_after} records ({n_before - n_after} removed)")
    return df


def engineer_features(df: pd.DataFrame) -> pd.DataFrame:
    """Create new features from existing data."""
    current_year = datetime.now().year

    # Basic features
    df["age"] = current_year - df["year"]
    df["km_per_year"] = df["km"] / df["age"].replace(0, 1)
    df["log_km"] = np.log1p(df["km"])
    df["log_price"] = np.log1p(df["price"])  # Target transformation option

    # Brand tier (luxury vs economy)
    luxury_brands = {"bmw", "mercedes-benz", "audi", "lexus", "jaguar", "porsche", "volvo", "land rover"}
    economy_brands = {"dacia", "fiat", "hyundai", "kia", "suzuki", "chevrolet"}
    df["brand_tier"] = df["brand"].str.lower().apply(
        lambda x: "luxury" if x in luxury_brands else ("economy" if x in economy_brands else "standard")
    )

    # Vehicle size proxy from model name
    df["is_suv"] = df["model"].str.lower().str.contains(r"suv|cross|x5|x3|q5|q7|glc|gle", regex=True, na=False).astype(int)
    df["is_sedan"] = df["model"].str.lower().str.contains(r"sedan|berlina|limousine", regex=True, na=False).astype(int)

    # Price per km (market efficiency indicator)
    df["price_per_km"] = df["price"] / df["km"].replace(0, 1)

    # Source premium (some sources have higher prices)
    source_premiums = df.groupby("source")["price"].median().to_dict()
    median_price = df["price"].median()
    df["source_premium"] = df["source"].map(lambda s: source_premiums.get(s, median_price) / median_price)

    # District premium
    district_premiums = df.groupby("district")["price"].median().to_dict()
    df["district_premium"] = df["district"].map(lambda d: district_premiums.get(d, median_price) / median_price)

    # Fuel type premium
    fuel_premiums = df.groupby("fuel_type")["price"].median().to_dict()
    df["fuel_premium"] = df["fuel_type"].map(lambda f: fuel_premiums.get(f, median_price) / median_price)

    return df


def encode_categoricals(df: pd.DataFrame, encoders: Optional[Dict] = None, fit: bool = True) -> Tuple[pd.DataFrame, Dict]:
    """Encode categorical variables with persistent encoders."""
    if encoders is None:
        encoders = {}

    categorical_cols = ["brand", "model", "fuel_type", "transmission", "district",
                        "vehicle_type", "source", "brand_tier"]

    for col in categorical_cols:
        if col not in df.columns:
            continue

        # Fill NaN
        df[col] = df[col].fillna("unknown").astype(str)

        if fit:
            le = LabelEncoder()
            df[f"{col}_encoded"] = le.fit_transform(df[col])
            encoders[col] = le
        else:
            le = encoders.get(col)
            if le is None:
                df[f"{col}_encoded"] = 0
                continue
            # Handle unseen categories
            known_classes = set(le.classes_)
            df[col] = df[col].apply(lambda x: x if x in known_classes else "unknown")
            # Ensure "unknown" is in classes
            if "unknown" not in known_classes:
                df[f"{col}_encoded"] = 0
            else:
                df[f"{col}_encoded"] = le.transform(df[col])

    return df, encoders


def get_feature_columns() -> List[str]:
    """Return the list of feature columns used for training."""
    return [
        "year", "km", "age", "km_per_year", "log_km",
        "brand_encoded", "model_encoded", "fuel_type_encoded",
        "transmission_encoded", "district_encoded",
        "vehicle_type_encoded", "source_encoded", "brand_tier_encoded",
        "is_suv", "is_sedan",
        "source_premium", "district_premium", "fuel_premium",
    ]


def prepare_features(df: pd.DataFrame, encoders: Optional[Dict] = None, fit: bool = True) -> Tuple[pd.DataFrame, Dict]:
    """Full feature preparation pipeline."""
    df = df.copy()

    # Clean outliers
    df = clean_outliers(df)

    if len(df) < MIN_TRAINING_SAMPLES:
        logger.warning(f"Not enough data after cleaning: {len(df)} < {MIN_TRAINING_SAMPLES}")
        return df, encoders or {}

    # Engineer features
    df = engineer_features(df)

    # Encode categoricals
    df, encoders = encode_categoricals(df, encoders, fit=fit)

    # Get feature columns
    feature_cols = get_feature_columns()
    available_features = [col for col in feature_cols if col in df.columns]

    # Ensure all numeric
    for col in available_features:
        df[col] = pd.to_numeric(df[col], errors="coerce").fillna(0)

    logger.info(f"Features used: {available_features}")
    return df, encoders


def train_model_v2(force_retrain: bool = True) -> Optional[xgb.XGBRegressor]:
    """
    Train improved XGBoost model with better feature engineering.
    """
    logger.info("=" * 60)
    logger.info("Starting XGBoost Model Training v2")
    logger.info("=" * 60)

    # Fetch data
    df = fetch_training_data()
    if len(df) < MIN_TRAINING_SAMPLES:
        logger.warning(f"Insufficient data: {len(df)} samples")
        return None

    # Prepare features
    df, encoders = prepare_features(df, fit=True)
    if len(df) < MIN_TRAINING_SAMPLES:
        logger.warning(f"Insufficient data after preprocessing: {len(df)}")
        return None

    feature_cols = get_feature_columns()
    available_features = [col for col in feature_cols if col in df.columns]

    X = df[available_features]
    y = df["price"]

    logger.info(f"Training with {len(df)} samples, {len(available_features)} features")
    logger.info(f"Price range: {y.min():.0f}€ - {y.max():.0f}€, median: {y.median():.0f}€")

    # Train/test split
    X_train, X_test, y_train, y_test = train_test_split(
        X, y, test_size=0.2, random_state=42, stratify=pd.qcut(y, q=5, duplicates="drop")
    )

    # Try log-transform target for better R² (price has high variance)
    y_train_log = np.log1p(y_train)
    y_test_log = np.log1p(y_test)

    # Model with tuned hyperparameters for small datasets
    model = xgb.XGBRegressor(
        n_estimators=500,
        max_depth=3,
        learning_rate=0.03,
        subsample=0.7,
        colsample_bytree=0.7,
        colsample_bylevel=0.7,
        min_child_weight=5,
        gamma=0.2,
        reg_alpha=0.5,
        reg_lambda=2.0,
        random_state=42,
        n_jobs=-1,
        objective="reg:squarederror",
        early_stopping_rounds=50,
    )

    logger.info("Training model (log target)...")
    model.fit(
        X_train, y_train_log,
        eval_set=[(X_test, y_test_log)],
        verbose=False
    )
    
    # Predictions: convert back from log
    y_pred_log = model.predict(X_test)
    y_pred = np.expm1(y_pred_log)
    
    # Also train a model on raw prices for comparison
    model_raw = xgb.XGBRegressor(
        n_estimators=500,
        max_depth=3,
        learning_rate=0.03,
        subsample=0.7,
        colsample_bytree=0.7,
        colsample_bylevel=0.7,
        min_child_weight=5,
        gamma=0.2,
        reg_alpha=0.5,
        reg_lambda=2.0,
        random_state=42,
        n_jobs=-1,
        objective="reg:squarederror",
        early_stopping_rounds=50,
    )
    model_raw.fit(X_train, y_train, eval_set=[(X_test, y_test)], verbose=False)
    y_pred_raw = model_raw.predict(X_test)
    
    # Use whichever model performs better
    r2_log = r2_score(y_test, y_pred)
    r2_raw = r2_score(y_test, y_pred_raw)
    logger.info(f"R² comparison - Log model: {r2_log:.4f}, Raw model: {r2_raw:.4f}")
    
    if r2_log > r2_raw:
        logger.info("Using log-target model (better R²)")
        model = model
        y_pred = y_pred
        use_log = True
    else:
        logger.info("Using raw-target model (better R²)")
        model = model_raw
        y_pred = y_pred_raw
        use_log = False
    
    # Clone model for CV
    cv_model = xgb.XGBRegressor(
        n_estimators=500,
        max_depth=3,
        learning_rate=0.03,
        subsample=0.7,
        colsample_bytree=0.7,
        colsample_bylevel=0.7,
        min_child_weight=5,
        gamma=0.2,
        reg_alpha=0.5,
        reg_lambda=2.0,
        random_state=42,
        n_jobs=-1,
        objective="reg:squarederror",
    )

    # Evaluate
    mae = mean_absolute_error(y_test, y_pred)
    rmse = np.sqrt(mean_squared_error(y_test, y_pred))
    r2 = r2_score(y_test, y_pred)

    # Cross-validation (use cv_model without early stopping callbacks)
    kf = KFold(n_splits=5, shuffle=True, random_state=42)
    cv_scores = cross_val_score(cv_model, X, y, cv=kf, scoring="r2", n_jobs=-1)
    cv_r2_mean = cv_scores.mean()
    cv_r2_std = cv_scores.std()

    logger.info(f"Test set - MAE: €{mae:.2f}, RMSE: €{rmse:.2f}, R²: {r2:.4f}")
    logger.info(f"CV R²: {cv_r2_mean:.4f} (+/- {cv_r2_std:.4f})")

    # Feature importance
    importance = model.feature_importances_
    feature_importance = sorted(
        zip(available_features, importance),
        key=lambda x: x[1], reverse=True
    )
    logger.info("Top 10 feature importances:")
    for feat, imp in feature_importance[:10]:
        logger.info(f"  {feat}: {imp:.4f}")

    # Save metrics
    metrics = {
        "mae": float(mae),
        "rmse": float(rmse),
        "r2": float(r2),
        "cv_r2_mean": float(cv_r2_mean),
        "cv_r2_std": float(cv_r2_std),
        "n_samples": len(df),
        "n_features": len(available_features),
        "features": available_features,
        "feature_importance": {k: float(v) for k, v in feature_importance},
        "training_date": datetime.now(timezone.utc).isoformat(),
        "rejected": False,
        "use_log_transform": use_log,
    }

    if r2 < MIN_R2_THRESHOLD:
        logger.warning(f"R² {r2:.4f} below threshold {MIN_R2_THRESHOLD}")
        metrics["rejected"] = True
        metrics["reason"] = f"R² {r2:.4f} < {MIN_R2_THRESHOLD}"

    # Save everything
    models_dir = settings.models_dir
    models_dir.mkdir(parents=True, exist_ok=True)

    # Save model (use booster directly to avoid sklearn mixin issues)
    model_path = models_dir / "xgboost_carros.json"
    model.get_booster().save_model(str(model_path))

    # Save metrics
    with open(models_dir / "metrics_carros.json", "w") as f:
        json.dump(metrics, f, indent=2)

    # Save feature names
    with open(models_dir / "feature_names.json", "w") as f:
        json.dump(available_features, f)

    # Save encoders
    dump(encoders, models_dir / "encoders_carros.joblib")

    logger.info(f"Model saved to {model_path}")
    logger.info(f"Metrics: R²={r2:.4f}, MAE=€{mae:.2f}, CV_R²={cv_r2_mean:.4f}")

    return model


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    train_model_v2(force_retrain=True)

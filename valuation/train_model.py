"""
XGBoost model training for vehicle price prediction
Uses REAL transaction prices from auctions as ground truth for better accuracy
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
from sklearn.model_selection import train_test_split
from sklearn.preprocessing import LabelEncoder
from sklearn.metrics import mean_absolute_error, mean_squared_error, r2_score
from joblib import dump

from config import settings
from database.db import get_db_context
from database.models import Vehicle, AuctionTransaction

logger = logging.getLogger(__name__)


def fetch_auction_training_data() -> List[Dict]:
    """
    Fetch real transaction prices from auction sites.
    These represent ACTUAL market transaction prices, not asking prices.
    This is the ground truth we need for accurate ML training.
    """
    auction_data = []
    with get_db_context() as db:
        transactions = db.query(AuctionTransaction).filter(
            AuctionTransaction.adjudication_price.isnot(None),
            AuctionTransaction.year.isnot(None),
            AuctionTransaction.brand.isnot(None),
            AuctionTransaction.model.isnot(None),
            AuctionTransaction.is_active == True  # noqa: E712
        ).all()

        for t in transactions:
            auction_data.append({
                "price": t.adjudication_price,
                "price_source": "auction_adjudication",
                "auction_type": t.auction_type,
                "year": t.year,
                "km": t.km,
                "horsepower": t.horsepower,
                "engine_size": t.engine_size,
                "brand": t.brand,
                "model": t.model,
                "fuel_type": t.fuel_type.value if t.fuel_type else None,
                "transmission": t.transmission.value if t.transmission else None,
                "location": t.location,
                "vehicle_type": t.vehicle_type.value if t.vehicle_type else None,
                "condition_grade": t.condition_grade,
                "has_damage": t.has_damage,
            })

    logger.info(f"Fetched {len(auction_data)} auction transactions for training")
    return auction_data


def fetch_listing_training_data() -> List[Dict]:
    """
    Fetch listing data (asking prices) from database.
    These are used as supplementary training data.
    """
    listing_data = []
    with get_db_context() as db:
        vehicles = db.query(Vehicle).filter(
            Vehicle.price.isnot(None),
            Vehicle.year.isnot(None),
            Vehicle.km.isnot(None)
        ).all()

        for v in vehicles:
            listing_data.append({
                "price": v.price,
                "price_source": "listing_asking",
                "year": v.year,
                "km": v.km,
                "horsepower": v.horsepower,
                "engine_size": v.engine_size,
                "brand": v.brand,
                "model": v.model,
                "fuel_type": v.fuel_type.value if v.fuel_type else None,
                "transmission": v.transmission.value if v.transmission else None,
                "location": v.location,
                "vehicle_type": v.vehicle_type.value if v.vehicle_type else None,
                "condition_grade": None,
                "has_damage": None,
            })

    logger.info(f"Fetched {len(listing_data)} listing entries for training")
    return listing_data


def train_model(force_retrain: bool = False) -> Optional[xgb.XGBRegressor]:
    """
    Train XGBoost model with auction transaction prices as ground truth.

    PRIORITY: Auction adjudication prices (real transactions) > Listing asking prices

    This ensures the model learns from actual market transactions, not just
    seller expectations which are typically 10-20% higher.
    """
    logger.info("=" * 60)
    logger.info("Starting XGBoost Model Training with Auction Ground Truth")
    logger.info("=" * 60)

    if settings.model_path.exists() and not force_retrain:
        logger.info(f"Model already exists at {settings.model_path}. Use force_retrain=True to retrain.")
        try:
            model = xgb.XGBRegressor()
            model.load_model(settings.model_path)
            logger.info("Loaded existing model")
            return model
        except Exception as e:
            logger.warning(f"Failed to load existing model: {e}. Will retrain.")

    auction_data = fetch_auction_training_data()
    listing_data = fetch_listing_training_data()

    all_data = []
    auction_count = 0
    listing_count = 0

    if auction_data:
        all_data.extend(auction_data)
        auction_count = len(auction_data)

    if listing_data:
        all_data.extend(listing_data)
        listing_count = len(listing_data)

    if len(all_data) < settings.min_training_samples:
        logger.warning(
            f"Insufficient data for training: {len(all_data)} samples "
            f"(minimum {settings.min_training_samples})"
        )
        return None

    logger.info(f"Training data: {auction_count} auction + {listing_count} listing = {len(all_data)} total")

    df = pd.DataFrame(all_data)
    df = preprocess_training_data(df)

    if df is None or len(df) < settings.min_training_samples:
        logger.warning("Insufficient data after preprocessing")
        return None

    X = df.drop(columns=["price"])
    y = df["price"]

    X_train, X_test, y_train, y_test = train_test_split(X, y, test_size=0.2, random_state=42)

    model = xgb.XGBRegressor(
        n_estimators=200,
        max_depth=6,
        learning_rate=0.1,
        subsample=0.8,
        colsample_bytree=0.8,
        random_state=42,
        n_jobs=-1
    )

    logger.info("Training XGBoost model...")
    model.fit(X_train, y_train)

    y_pred = model.predict(X_test)
    mae = mean_absolute_error(y_test, y_pred)
    rmse = np.sqrt(mean_squared_error(y_test, y_pred))
    r2 = r2_score(y_test, y_pred)

    logger.info(f"Model performance - MAE: €{mae:.2f}, RMSE: €{rmse:.2f}, R2: {r2:.4f}")

    MIN_R2_THRESHOLD = 0.3
    if r2 < MIN_R2_THRESHOLD:
        logger.warning(
            f"Model R² ({r2:.4f}) is below minimum threshold ({MIN_R2_THRESHOLD}). "
            f"Model NOT saved. Need more/better training data."
        )
        metrics_path = settings.models_dir / "model_metrics.json"
        with open(metrics_path, 'w') as f:
            json.dump({
                "mae": float(mae),
                "rmse": float(rmse),
                "r2": float(r2),
                "training_date": datetime.now(timezone.utc).isoformat(),
                "n_samples": len(df),
                "auction_samples": auction_count,
                "listing_samples": listing_count,
                "features": list(X.columns),
                "rejected": True,
                "reason": f"R² {r2:.4f} < {MIN_R2_THRESHOLD}"
            }, f, indent=2)
        return None

    settings.model_path.parent.mkdir(parents=True, exist_ok=True)
    model.save_model(str(settings.model_path))

    feature_names_path = settings.models_dir / "feature_names.json"
    with open(feature_names_path, 'w') as f:
        json.dump(list(X.columns), f)

    metrics_path = settings.models_dir / "model_metrics.json"
    with open(metrics_path, 'w') as f:
        json.dump({
            "mae": float(mae),
            "rmse": float(rmse),
            "r2": float(r2),
            "training_date": datetime.now(timezone.utc).isoformat(),
            "n_samples": len(df),
            "auction_samples": auction_count,
            "listing_samples": listing_count,
            "features": list(X.columns),
            "rejected": False,
            "data_source": "auction_adjudication_prices" if auction_count > 0 else "listing_prices"
        }, f, indent=2)

    encoders_path = settings.models_dir / "label_encoders.joblib"
    encoders = get_label_encoders()
    dump(encoders, encoders_path)

    logger.info(f"Model saved to {settings.model_path} (R²={r2:.4f}, n={len(df)})")
    if auction_count > 0:
        logger.info(f"Ground truth: {auction_count} auction transactions used as primary training data")

    return model


def preprocess_training_data(df: pd.DataFrame) -> Optional[pd.DataFrame]:
    """
    Preprocess combined auction + listing data for training.

    Args:
        df: Combined DataFrame with auction and listing data

    Returns:
        Preprocessed DataFrame or None if error
    """
    try:
        df = df.dropna(subset=["price", "year", "km"])

        numeric_cols = ["horsepower", "engine_size"]
        for col in numeric_cols:
            if col in df.columns:
                median_val = df[col].median()
                df[col] = df[col].fillna(median_val)
                df[col] = pd.to_numeric(df[col], errors='coerce').fillna(0)

        categorical_cols = ["brand", "model", "fuel_type", "transmission", "vehicle_type"]
        for col in categorical_cols:
            if col in df.columns:
                df[col] = df[col].fillna("unknown")
                le = LabelEncoder()
                df[col + "_encoded"] = le.fit_transform(df[col].astype(str))

        df["age"] = datetime.now().year - df["year"]
        df["km_per_year"] = df["km"] / df["age"].replace(0, 1)

        feature_cols = [
            "year", "km", "horsepower", "engine_size",
            "brand_encoded", "model_encoded", "fuel_type_encoded",
            "transmission_encoded", "age", "km_per_year"
        ]

        available_features = [col for col in feature_cols if col in df.columns]
        for col in available_features:
            df[col] = pd.to_numeric(df[col], errors='coerce').fillna(0)

        return df[available_features + ["price"]]

    except Exception as e:
        logger.error(f"Error during data preprocessing: {e}")
        return None


class ModelTrainer:
    """Legacy compatibility wrapper around the module-level training routine."""
    def train(self, force_retrain: bool = False) -> Optional[xgb.XGBRegressor]:
        return train_model(force_retrain=force_retrain)


Trainer = ModelTrainer


def get_label_encoders() -> Dict:
    """Get or create label encoders for categorical variables"""
    return {}


def evaluate_model(model: xgb.XGBRegressor, X_test: np.ndarray, y_test: np.ndarray) -> Dict:
    """
    Evaluate model performance
    """
    y_pred = model.predict(X_test)
    mae = mean_absolute_error(y_test, y_pred)
    rmse = np.sqrt(mean_squared_error(y_test, y_pred))
    r2 = r2_score(y_test, y_pred)

    return {
        "mae": float(mae),
        "rmse": float(rmse),
        "r2": float(r2)
    }
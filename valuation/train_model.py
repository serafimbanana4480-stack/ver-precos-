"""
XGBoost model training for vehicle price prediction
"""
from __future__ import annotations
import logging
import json
from pathlib import Path
from datetime import datetime, timezone
from typing import Optional, Dict, List
import numpy as np
import pandas as pd
import xgboost as xgb
from sklearn.model_selection import train_test_split
from sklearn.preprocessing import LabelEncoder
from sklearn.metrics import mean_absolute_error, mean_squared_error, r2_score
from joblib import dump

from config import settings
from database.db import get_db_context
from database.models import Vehicle

logger = logging.getLogger(__name__)


def train_model(force_retrain: bool = False) -> Optional[xgb.XGBRegressor]:
    """
    Train XGBoost model on vehicle data from database
    
    Args:
        force_retrain: Force retraining even if model exists
    
    Returns:
        Trained XGBoost model or None if insufficient data
    """
    logger.info("Starting XGBoost model training")
    
    # Check if model already exists
    if settings.model_path.exists() and not force_retrain:
        logger.info(f"Model already exists at {settings.model_path}. Use force_retrain=True to retrain.")
        try:
            model = xgb.XGBRegressor()
            model.load_model(settings.model_path)
            logger.info("Loaded existing model")
            return model
        except Exception as e:
            logger.warning(f"Failed to load existing model: {e}. Will retrain.")
    
    # Fetch data from database
    data = []
    with get_db_context() as db:
        vehicles = db.query(Vehicle).filter(
            Vehicle.price.isnot(None),
            Vehicle.year.isnot(None),
            Vehicle.km.isnot(None)
        ).all()
        
        if len(vehicles) < settings.min_training_samples:
            logger.warning(f"Insufficient data for training: {len(vehicles)} samples (minimum {settings.min_training_samples})")
            return None
        
        logger.info(f"Training with {len(vehicles)} samples")
        
        # Convert to DataFrame within session context
        for v in vehicles:
            data.append({
                "price": v.price,
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
                "doors": v.doors,
                "seats": v.seats,
            })
    
    df = pd.DataFrame(data)
    
    # Data preprocessing
    df = preprocess_data(df)
    
    if df is None or len(df) < settings.min_training_samples:
        logger.warning("Insufficient data after preprocessing")
        return None
    
    # Prepare features and target
    X = df.drop(columns=["price"])
    y = df["price"]
    
    # Split data
    X_train, X_test, y_train, y_test = train_test_split(
        X, y, test_size=0.2, random_state=42
    )
    
    # Train XGBoost model
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
    
    # Evaluate model
    y_pred = model.predict(X_test)
    mae = mean_absolute_error(y_test, y_pred)
    rmse = np.sqrt(mean_squared_error(y_test, y_pred))
    r2 = r2_score(y_test, y_pred)
    
    logger.info(f"Model performance - MAE: €{mae:.2f}, RMSE: €{rmse:.2f}, R2: {r2:.4f}")
    
    # Save model
    settings.model_path.parent.mkdir(parents=True, exist_ok=True)
    model.save_model(str(settings.model_path))

    # Save feature names
    feature_names_path = settings.models_dir / "feature_names.json"
    with open(feature_names_path, 'w') as f:
        json.dump(list(X.columns), f)

    # Save model metrics
    metrics_path = settings.models_dir / "model_metrics.json"
    with open(metrics_path, 'w') as f:
        json.dump({
            "mae": float(mae),
            "rmse": float(rmse),
            "r2": float(r2),
            "training_date": datetime.now(timezone.utc).isoformat(),
            "n_samples": len(df),
            "features": list(X.columns)
        }, f, indent=2)

    # Save label encoders
    encoders_path = settings.models_dir / "label_encoders.joblib"
    encoders = get_label_encoders()
    dump(encoders, encoders_path)

    logger.info(f"Model saved to {settings.model_path}")
    
    return model


def preprocess_data(df: pd.DataFrame) -> Optional[pd.DataFrame]:
    """
    Preprocess vehicle data for training
    
    Args:
        df: Raw vehicle DataFrame
    
    Returns:
        Preprocessed DataFrame or None if error
    """
    try:
        # Drop rows with missing critical values
        df = df.dropna(subset=["price", "year", "km"])
        
        # Fill missing numeric values with median
        numeric_cols = ["horsepower", "engine_size", "doors", "seats"]
        for col in numeric_cols:
            if col in df.columns:
                median_val = df[col].median()
                df[col] = df[col].fillna(median_val)
                # Convert to numeric type
                df[col] = pd.to_numeric(df[col], errors='coerce').fillna(0)
        
        # Encode categorical variables
        categorical_cols = ["brand", "model", "fuel_type", "transmission", "location", "vehicle_type"]
        
        for col in categorical_cols:
            if col in df.columns:
                df[col] = df[col].fillna("unknown")
                le = LabelEncoder()
                df[col + "_encoded"] = le.fit_transform(df[col].astype(str))
        
        # Calculate derived features
        df["age"] = 2024 - df["year"]
        df["km_per_year"] = df["km"] / df["age"].replace(0, 1)
        df["log_price"] = np.log1p(df["price"])
        
        # Select features for training
        feature_cols = [
            "year", "km", "horsepower", "engine_size", "doors", "seats",
            "brand_encoded", "model_encoded", "fuel_type_encoded",
            "transmission_encoded", "age", "km_per_year"
        ]
        
        # Ensure all features exist and convert to numeric
        available_features = [col for col in feature_cols if col in df.columns]
        for col in available_features:
            df[col] = pd.to_numeric(df[col], errors='coerce').fillna(0)
        
        return df[available_features + ["price"]]
        
    except Exception as e:
        logger.error(f"Error preprocessing data: {e}")
        return None


def get_label_encoders() -> Dict:
    """Get or create label encoders for categorical variables"""
    # This would be saved/loaded in production
    return {}


def evaluate_model(model: xgb.XGBRegressor, X_test: np.ndarray, y_test: np.ndarray) -> Dict:
    """
    Evaluate model performance
    
    Args:
        model: Trained XGBoost model
        X_test: Test features
        y_test: Test target
    
    Returns:
        Dictionary of metrics
    """
    y_pred = model.predict(X_test)
    
    return {
        "mae": float(mean_absolute_error(y_test, y_pred)),
        "rmse": float(np.sqrt(mean_squared_error(y_test, y_pred))),
        "r2": float(r2_score(y_test, y_pred)),
        "mean_absolute_percentage_error": float(np.mean(np.abs((y_test - y_pred) / y_test)) * 100)
    }


def get_feature_importance(model: xgb.XGBRegressor, feature_names: List[str]) -> Dict:
    """
    Get feature importance from trained model
    
    Args:
        model: Trained XGBoost model
        feature_names: List of feature names
    
    Returns:
        Dictionary of feature importance scores
    """
    importance = model.feature_importances_
    
    return dict(zip(feature_names, importance))


if __name__ == "__main__":
    # Train model when run directly
    model = train_model(force_retrain=True)
    if model:
        print("Model trained successfully!")
    else:
        print("Failed to train model")

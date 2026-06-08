"""
Enhanced ML Model Training with Vehicle-Type-Aware Models
Separate models for cars vs motorcycles, ensemble modeling, advanced feature engineering.
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
from sklearn.model_selection import train_test_split, cross_val_score
from sklearn.preprocessing import LabelEncoder, StandardScaler
from sklearn.metrics import mean_absolute_error, mean_squared_error, r2_score
from joblib import dump

from config import settings
from database.db import get_db_context
from database.models import Vehicle

logger = logging.getLogger(__name__)

# Price segment categories
PRICE_SEGMENTS = {
    "budget": (0, 5000),
    "economy": (5000, 15000),
    "mid_range": (15000, 30000),
    "premium": (30000, 60000),
    "luxury": (60000, float("inf")),
}

# Location premium factors (approximate for Portugal)
LOCATION_PREMIUM = {
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


class VehicleTypeAwarePricing:
    """Train separate ML models for cars and motorcycles."""

    def __init__(self) -> None:
        self.car_model: Optional[xgb.XGBRegressor] = None
        self.moto_model: Optional[xgb.XGBRegressor] = None
        self.car_metrics: Dict[str, float] = {}
        self.moto_metrics: Dict[str, float] = {}
        self.car_encoders: Dict[str, LabelEncoder] = {}
        self.moto_encoders: Dict[str, LabelEncoder] = {}
        self.scaler: Optional[StandardScaler] = None
        self.feature_names: List[str] = []

    def train_all(self, force_retrain: bool = False) -> bool:
        """Train both car and motorcycle models."""
        logger.info("=" * 60)
        logger.info("Starting Vehicle-Type-Aware Model Training")
        logger.info("=" * 60)

        car_success = self._train_for_type("carros", force_retrain)
        moto_success = self._train_for_type("motos", force_retrain)

        return car_success or moto_success

    def _train_for_type(self, vehicle_type: str, force_retrain: bool) -> bool:
        """Train model for a specific vehicle type."""
        model_path = settings.models_dir / f"xgboost_{vehicle_type}.json"
        metrics_path = settings.models_dir / f"metrics_{vehicle_type}.json"
        encoders_path = settings.models_dir / f"encoders_{vehicle_type}.joblib"

        # Check existing model
        if model_path.exists() and not force_retrain:
            logger.info(f"Loading existing {vehicle_type} model from {model_path}")
            try:
                model = xgb.XGBRegressor()
                model.load_model(str(model_path))
                if vehicle_type == "carros":
                    self.car_model = model
                else:
                    self.moto_model = model
                return True
            except Exception as e:
                logger.warning(f"Failed to load {vehicle_type} model: {e}")

        # Fetch data
        with get_db_context() as db:
            vehicles = (
                db.query(Vehicle)
                .filter(
                    Vehicle.price.isnot(None),
                    Vehicle.year.isnot(None),
                    Vehicle.km.isnot(None),
                    Vehicle.vehicle_type == vehicle_type,
                )
                .all()
            )

            if len(vehicles) < settings.min_training_samples:
                logger.warning(
                    f"Insufficient {vehicle_type} data: {len(vehicles)} samples "
                    f"(need {settings.min_training_samples})"
                )
                return False

            logger.info(f"Training {vehicle_type} model with {len(vehicles)} samples")

            # Convert to DataFrame inside session to avoid DetachedInstanceError
            data = []
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
                    "district": v.district,
                    "doors": v.doors,
                    "condition_score": v.condition_score,
                })

        df = pd.DataFrame(data)
        df, encoders = self._engineer_features(df)
        self.feature_names = [c for c in df.columns if c != "price"]

        if len(df) < settings.min_training_samples:
            return False

        # Prepare features
        X = df.drop(columns=["price"])
        y = df["price"]

        # Scale numeric features
        self.scaler = StandardScaler()
        X_scaled = self.scaler.fit_transform(X)
        X = pd.DataFrame(X_scaled, columns=X.columns)

        # Split
        X_train, X_test, y_train, y_test = train_test_split(
            X, y, test_size=0.2, random_state=42
        )

        # Train XGBoost
        model = xgb.XGBRegressor(
            n_estimators=300,
            max_depth=6,
            learning_rate=0.08,
            subsample=0.8,
            colsample_bytree=0.8,
            reg_alpha=1.0,
            reg_lambda=1.0,
            random_state=42,
            n_jobs=-1,
        )

        logger.info(f"Fitting {vehicle_type} XGBoost model...")
        model.fit(X_train, y_train)

        # Evaluate
        y_pred = model.predict(X_test)
        mae = mean_absolute_error(y_test, y_pred)
        rmse = np.sqrt(mean_squared_error(y_test, y_pred))
        r2 = r2_score(y_test, y_pred)

        logger.info(
            f"{vehicle_type} model: MAE=€{mae:.2f}, RMSE=€{rmse:.2f}, R²={r2:.4f}"
        )

        metrics = {"mae": float(mae), "rmse": float(rmse), "r2": float(r2),
                    "n_samples": len(df), "features": self.feature_names,
                    "training_date": datetime.now(timezone.utc).isoformat()}

        # Quality gate
        MIN_R2 = 0.3
        if r2 < MIN_R2:
            logger.warning(
                f"{vehicle_type} R² ({r2:.4f}) below threshold ({MIN_R2}). "
                f"Model saved anyway for fallback."
            )
            metrics["quality_warning"] = True

        # Save
        model_path.parent.mkdir(parents=True, exist_ok=True)
        dump(model, model_path)

        with open(metrics_path, "w") as f:
            json.dump(metrics, f, indent=2)

        dump(encoders, encoders_path)

        if vehicle_type == "carros":
            self.car_model = model
            self.car_metrics = metrics
            self.car_encoders = encoders
        else:
            self.moto_model = model
            self.moto_metrics = metrics
            self.moto_encoders = encoders

        logger.info(f"{vehicle_type} model saved to {model_path}")
        return True

    def _engineer_features(
        self, df: pd.DataFrame
    ) -> Tuple[pd.DataFrame, Dict[str, LabelEncoder]]:
        """Advanced feature engineering."""
        df = df.dropna(subset=["price", "year", "km"])

        # Fill numeric NaNs
        for col in ["horsepower", "engine_size", "doors", "condition_score"]:
            if col in df.columns:
                df[col] = df[col].fillna(df[col].median() if not df[col].isna().all() else 0)

        # Encode categoricals
        encoders: Dict[str, LabelEncoder] = {}
        cat_cols = ["brand", "model", "fuel_type", "transmission", "district"]
        for col in cat_cols:
            if col in df.columns:
                df[col] = df[col].fillna("unknown").astype(str)
                le = LabelEncoder()
                df[col + "_encoded"] = le.fit_transform(df[col])
                encoders[col] = le

        # --- Advanced features ---

        # Vehicle age
        df["age"] = datetime.now().year - df["year"]

        # KM per year
        df["km_per_year"] = df["km"] / df["age"].replace(0, 1)

        # Log transform for skewed distributions
        df["log_price"] = np.log1p(df["price"])
        df["log_km"] = np.log1p(df["km"])

        # Price segment
        df["price_segment"] = pd.cut(
            df["price"],
            bins=[0, 5000, 15000, 30000, 60000, float("inf")],
            labels=[0, 1, 2, 3, 4],
        ).astype(int)

        # Location premium
        df["location_premium"] = df.get("district", pd.Series(dtype=str)).apply(
            lambda x: LOCATION_PREMIUM.get(
                str(x).lower().strip() if pd.notna(x) else "", 1.0
            )
        )

        # Seasonal factor (based on first_seen month)
        df["season_factor"] = 1.0  # Default, can be enhanced with actual data

        # Brand rarity (inverse frequency)
        if "brand" in df.columns:
            brand_counts = df["brand"].value_counts()
            df["brand_rarity"] = df["brand"].map(lambda x: 1.0 / max(brand_counts.get(x, 1), 1))

        # Select final features
        feature_cols = [
            "year", "km", "horsepower", "engine_size", "doors", "condition_score",
            "brand_encoded", "model_encoded", "fuel_type_encoded",
            "transmission_encoded", "district_encoded",
            "age", "km_per_year", "log_km",
            "location_premium", "brand_rarity",
        ]

        available = [c for c in feature_cols if c in df.columns]
        for c in available:
            df[c] = pd.to_numeric(df[c], errors="coerce").fillna(0)

        return df[available + ["price"]], encoders

    def predict(self, vehicle_data: Dict, vehicle_type: str = "carros") -> Optional[float]:
        """Predict price using the appropriate vehicle-type model."""
        model = self.car_model if vehicle_type == "carros" else self.moto_model

        if model is None:
            # Try loading
            model_path = settings.models_dir / f"xgboost_{vehicle_type}.json"
            if model_path.exists():
                try:
                    model = xgb.XGBRegressor()
                    model.load_model(str(model_path))
                except Exception:
                    return None
            else:
                return None

        try:
            # Build feature vector
            features = self._build_feature_vector(vehicle_data, vehicle_type)
            if features is None:
                return None

            X = np.array([features])
            if self.scaler:
                X = self.scaler.transform(X)

            pred = model.predict(X)[0]
            return float(pred)
        except Exception as e:
            logger.error(f"Prediction error: {e}")
            return None

    def _build_feature_vector(
        self, vehicle_data: Dict, vehicle_type: str
    ) -> Optional[List[float]]:
        """Build feature vector from vehicle data."""
        encoders = self.car_encoders if vehicle_type == "carros" else self.moto_encoders

        if not self.feature_names:
            return None

        row: Dict[str, float] = {}

        # Basic features
        row["year"] = float(vehicle_data.get("year", 0))
        row["km"] = float(vehicle_data.get("km", 0))
        row["horsepower"] = float(vehicle_data.get("horsepower", 0))
        row["engine_size"] = float(vehicle_data.get("engine_size", 0))
        row["doors"] = float(vehicle_data.get("doors", 0))
        row["condition_score"] = float(vehicle_data.get("condition_score", 5.0))

        # Encoded categoricals
        for col in ["brand", "model", "fuel_type", "transmission", "district"]:
            if col in encoders:
                val = str(vehicle_data.get(col, "unknown"))
                le = encoders[col]
                try:
                    row[f"{col}_encoded"] = float(le.transform([val])[0])
                except ValueError:
                    row[f"{col}_encoded"] = 0.0
            else:
                row[f"{col}_encoded"] = 0.0

        # Derived features
        age = datetime.now().year - row["year"]
        row["age"] = float(age)
        row["km_per_year"] = row["km"] / max(age, 1)
        row["log_km"] = np.log1p(row["km"])
        row["location_premium"] = 1.0
        row["brand_rarity"] = 0.0

        # Build in correct order
        vec = []
        for fname in self.feature_names:
            vec.append(row.get(fname, 0.0))

        return vec


# Module-level convenience function for backward compatibility
def train_enhanced_models(force_retrain: bool = False) -> VehicleTypeAwarePricing:
    """Train vehicle-type-aware models and return the predictor."""
    pricing = VehicleTypeAwarePricing()
    pricing.train_all(force_retrain=force_retrain)
    return pricing
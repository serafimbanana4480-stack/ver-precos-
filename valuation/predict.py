"""
Price prediction and deal scoring using trained XGBoost model
"""
import logging
import json
from pathlib import Path
from typing import Optional, Dict, List
import numpy as np
import pandas as pd
import xgboost as xgb
from joblib import load

from config import MODEL_PATH, MODELS_DIR, MIN_PROFIT_MARGIN_EUR, MAX_PROFIT_MARGIN_PERCENT
from database.models import Vehicle

logger = logging.getLogger(__name__)


def load_model() -> Optional[xgb.XGBRegressor]:
    """
    Load trained XGBoost model
    
    Returns:
        Loaded model or None if not found
    """
    if not MODEL_PATH.exists():
        logger.warning(f"Model not found at {MODEL_PATH}")
        return None
    
    try:
        model = xgb.XGBRegressor()
        model.load_model(str(MODEL_PATH))
        logger.info("Model loaded successfully")
        return model
    except Exception as e:
        logger.error(f"Error loading model: {e}")
        return None


def load_feature_names() -> List[str]:
    """Load feature names from file"""
    feature_names_path = MODELS_DIR / "feature_names.json"
    
    if not feature_names_path.exists():
        logger.warning("Feature names file not found")
        return []
    
    try:
        with open(feature_names_path, 'r') as f:
            return json.load(f)
    except Exception as e:
        logger.error(f"Error loading feature names: {e}")
        return []


def predict_price(vehicle: Vehicle, model: Optional[xgb.XGBRegressor] = None) -> Optional[float]:
    """
    Predict fair market price for a vehicle
    
    Args:
        vehicle: Vehicle object
        model: Pre-loaded model (will load if not provided)
    
    Returns:
        Predicted price or None if prediction fails
    """
    if model is None:
        model = load_model()
        if model is None:
            return None
    
    try:
        # Prepare features
        features = prepare_features(vehicle)
        
        if features is None:
            return None
        
        # Create DataFrame with correct feature order
        feature_names = load_feature_names()
        if not feature_names:
            logger.warning("No feature names available")
            return None
        
        # Ensure all features exist
        feature_dict = {}
        for feat in feature_names:
            feature_dict[feat] = features.get(feat, 0)
        
        df = pd.DataFrame([feature_dict])
        
        # Predict
        prediction = model.predict(df)[0]
        
        return float(prediction)
        
    except Exception as e:
        logger.error(f"Error predicting price: {e}")
        return None


def prepare_features(vehicle: Vehicle) -> Optional[Dict]:
    """
    Prepare feature dictionary from vehicle object
    
    Args:
        vehicle: Vehicle object
    
    Returns:
        Feature dictionary or None if critical data missing
    """
    try:
        # Calculate derived features
        current_year = 2024
        age = current_year - vehicle.year if vehicle.year else 0
        km_per_year = vehicle.km / age if age > 0 and vehicle.km else 0
        
        # Simple encoding for categorical variables (in production, use saved encoders)
        brand_encoded = hash(vehicle.brand.lower()) % 1000 if vehicle.brand else 0
        model_encoded = hash(vehicle.model.lower()) % 1000 if vehicle.model else 0
        
        fuel_type_map = {
            "gasolina": 1,
            "diesel": 2,
            "eletrico": 3,
            "hibrido": 4,
            "gpl": 5,
            None: 0
        }
        fuel_type_encoded = fuel_type_map.get(
            vehicle.fuel_type.value if vehicle.fuel_type else None, 0
        )
        
        transmission_map = {
            "manual": 1,
            "automatico": 2,
            "semi-automatico": 3,
            None: 0
        }
        transmission_encoded = transmission_map.get(
            vehicle.transmission.value if vehicle.transmission else None, 0
        )
        
        location_encoded = hash(vehicle.location.lower()) % 100 if vehicle.location else 0
        
        features = {
            "year": vehicle.year or 2020,
            "km": vehicle.km or 50000,
            "horsepower": vehicle.horsepower or 100,
            "engine_size": vehicle.engine_size or 1500,
            "doors": vehicle.doors or 5,
            "seats": vehicle.seats or 5,
            "brand_encoded": brand_encoded,
            "model_encoded": model_encoded,
            "fuel_type_encoded": fuel_type_encoded,
            "transmission_encoded": transmission_encoded,
            "age": max(0, age),
            "km_per_year": km_per_year
        }
        
        return features
        
    except Exception as e:
        logger.error(f"Error preparing features: {e}")
        return None


def calculate_deal_score(
    asked_price: float,
    estimated_value: float,
    km: Optional[int] = None,
    year: Optional[int] = None,
    condition_score: Optional[float] = None
) -> float:
    """
    Calculate deal score (0-10) based on price difference and other factors
    
    Args:
        asked_price: Current asking price
        estimated_value: Estimated fair market value
        km: Vehicle kilometers
        year: Vehicle year
        condition_score: Condition score from vision analysis (0-10)
    
    Returns:
        Deal score from 0 to 10
    """
    if estimated_value <= 0:
        return 0.0
    
    # Calculate price difference percentage
    price_diff_percent = (estimated_value - asked_price) / estimated_value * 100
    
    # Base score from price difference
    if price_diff_percent <= 0:
        # Price is above or at market value
        base_score = 0.0
    elif price_diff_percent < 5:
        base_score = 3.0
    elif price_diff_percent < 10:
        base_score = 5.0
    elif price_diff_percent < 15:
        base_score = 7.0
    elif price_diff_percent < 20:
        base_score = 8.5
    else:
        base_score = 9.5
    
    # Adjust for km (lower km is better)
    if km is not None:
        if km < 50000:
            km_adjustment = 0.5
        elif km < 100000:
            km_adjustment = 0.0
        elif km < 150000:
            km_adjustment = -0.3
        else:
            km_adjustment = -0.5
        base_score += km_adjustment
    
    # Adjust for year (newer is better)
    if year is not None:
        age = 2024 - year
        if age < 3:
            year_adjustment = 0.3
        elif age < 5:
            year_adjustment = 0.0
        elif age < 10:
            year_adjustment = -0.2
        else:
            year_adjustment = -0.4
        base_score += year_adjustment
    
    # Adjust for condition
    if condition_score is not None:
        condition_adjustment = (condition_score - 5) / 10  # -0.5 to +0.5
        base_score += condition_adjustment
    
    # Ensure score is between 0 and 10
    return max(0.0, min(10.0, base_score))


def calculate_profit_potential(
    asked_price: float,
    estimated_value: float,
    margin_percent: float = 15.0
) -> Dict[str, float]:
    """
    Calculate potential profit from resale
    
    Args:
        asked_price: Current asking price
        estimated_value: Estimated fair market value
        margin_percent: Expected resale margin (default 15%)
    
    Returns:
        Dictionary with profit calculations
    """
    if estimated_value <= 0:
        return {
            "profit_potential": 0.0,
            "profit_percentage": 0.0,
            "resale_price": 0.0
        }
    
    # Calculate realistic resale price (with margin)
    resale_price = estimated_value * (1 - margin_percent / 100)
    
    # Calculate profit
    profit = resale_price - asked_price
    profit_percentage = (profit / asked_price) * 100 if asked_price > 0 else 0
    
    return {
        "profit_potential": round(profit, 2),
        "profit_percentage": round(profit_percentage, 2),
        "resale_price": round(resale_price, 2)
    }


def update_vehicle_valuations(batch_size: int = 100):
    """
    Update valuations for all vehicles in database
    
    Args:
        batch_size: Number of vehicles to process at once
    """
    logger.info("Updating vehicle valuations")
    
    model = load_model()
    if model is None:
        logger.error("Cannot update valuations: model not loaded")
        return
    
    from database.db import get_db_context
    
    with get_db_context() as db:
        # Get vehicles without estimated value
        vehicles = db.query(Vehicle).filter(
            Vehicle.estimated_value.is_(None)
        ).limit(batch_size).all()
        
        logger.info(f"Updating {len(vehicles)} vehicles")
        
        for vehicle in vehicles:
            try:
                # Predict price
                estimated = predict_price(vehicle, model)
                
                if estimated:
                    vehicle.estimated_value = estimated
                    
                    # Calculate deal score
                    vehicle.deal_score = calculate_deal_score(
                        vehicle.price,
                        estimated,
                        vehicle.km,
                        vehicle.year,
                        vehicle.condition_score
                    )
                    
                    # Calculate profit potential
                    profit_calc = calculate_profit_potential(
                        vehicle.price,
                        estimated
                    )
                    vehicle.profit_potential = profit_calc["profit_potential"]
                    vehicle.profit_percentage = profit_calc["profit_percentage"]
                    
            except Exception as e:
                logger.warning(f"Error updating vehicle {vehicle.id}: {e}")
                continue
        
        db.commit()
        logger.info("Valuations updated successfully")


if __name__ == "__main__":
    # Test prediction
    model = load_model()
    if model:
        print("Model loaded successfully")
        update_vehicle_valuations()
    else:
        print("No model found")

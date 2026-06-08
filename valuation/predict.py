"""
Vehicle Valuation Prediction Module
XGBoost model for price prediction and valuation
"""

import logging
from typing import Optional, Dict, Any
import pandas as pd
import numpy as np
from pathlib import Path

from config import settings

logger = logging.getLogger(__name__)

class VehicleValuationModel:
    """XGBoost-based vehicle valuation model"""
    
    def __init__(self):
        self.model = None
        self.model_path = settings.model_path
        self._booster = None
        self.feature_columns = [
            'year', 'km', 'horsepower', 'engine_size', 'fuel_type',
            'transmission', 'brand', 'model', 'location'
        ]
    
    def load_model(self):
        """Load trained model from disk (JSON via XGBoost or PKL via joblib)."""
        json_path = settings.models_dir / "xgboost_model.json"
        pkl_path = settings.models_dir / "xgboost_model.pkl"
        try:
            if json_path.exists():
                import xgboost as xgb
                self._booster = xgb.Booster()
                self._booster.load_model(str(json_path))
                self.model_path = json_path
                logger.info(f"Model loaded from {json_path}")
                return True
            import joblib
            if pkl_path.exists():
                self.model = joblib.load(pkl_path)
                self.model_path = pkl_path
                logger.info(f"Model loaded from {pkl_path}")
                return True
            logger.warning("No model file found at %s or %s", json_path, pkl_path)
            return False
        except Exception as e:
            logger.error(f"Error loading model: {e}")
            return False

    def predict(self, vehicle_data: Dict[str, Any]) -> Optional[float]:
        """Alias for predict_price (tests and legacy callers)."""
        return self.predict_price(vehicle_data)
    
    def predict_price(self, vehicle_data: Dict[str, Any]) -> Optional[float]:
        """
        Predict vehicle price based on features
        
        Args:
            vehicle_data: Dictionary with vehicle features
            
        Returns:
            Predicted price or None if prediction fails
        """
        if self.model is None and self._booster is None:
            if not self.load_model():
                logger.error("Model not available for prediction")
                return None

        try:
            if self._booster is not None:
                import xgboost as xgb
                feature_names_file = settings.models_dir / "feature_names.json"
                feature_names: list = []
                if feature_names_file.exists():
                    import json
                    with open(feature_names_file) as f:
                        feature_names = json.load(f)
                features = []
                for fname in feature_names or self.feature_columns:
                    val = vehicle_data.get(fname, 0)
                    features.append(float(val) if isinstance(val, (int, float)) else 0.0)
                dmatrix = xgb.DMatrix([features], feature_names=feature_names or None)
                return float(self._booster.predict(dmatrix)[0])

            df = pd.DataFrame([vehicle_data])
            for col in self.feature_columns:
                if col not in df.columns:
                    df[col] = 0
            X = df[self.feature_columns]
            prediction = self.model.predict(X)[0]
            return float(prediction)
            
        except Exception as e:
            logger.error(f"Error predicting price: {e}")
            return None
    
    def predict_batch(self, vehicles: list) -> list:
        """
        Predict prices for multiple vehicles
        
        Args:
            vehicles: List of vehicle data dictionaries
            
        Returns:
            List of predicted prices
        """
        predictions = []
        for vehicle in vehicles:
            price = self.predict_price(vehicle)
            predictions.append(price)
        return predictions


# Legacy compatibility alias.
Predictor = VehicleValuationModel


def estimate_market_value(vehicle: Any) -> Optional[float]:
    """Legacy compatibility helper that delegates to the valuation model."""
    model = VehicleValuationModel()
    if isinstance(vehicle, dict):
        return model.predict_price(vehicle)
    return model.predict_price(getattr(vehicle, "__dict__", {}))


def calculate_deal_score(listing: Dict[str, Any]) -> Dict[str, Any]:
    """Calculate realistic deal score for Portuguese used car market.
    
    In Portugal, asking prices are typically 15-25% above transaction prices.
    We apply a market margin to the estimated_value (transaction price) to get
    a realistic asking price benchmark, then score based on how the actual
    asking price compares to that benchmark.
    """
    price = float(listing.get("price") or 0)
    estimated_value = float(listing.get("estimated_value") or price)
    if estimated_value <= 0 or price <= 0:
        return {"deal_score": 0.0, "estimated_value": estimated_value, "price": price}
    
    # Apply Portuguese market margin: transaction price -> asking price benchmark
    # Typical margin: 15% (stands) to 20% (particulares)
    market_margin = 1.18  # 18% margin = typical PT market
    asking_benchmark = estimated_value * market_margin
    
    # Calculate how much below the market benchmark this listing is
    # discount > 0 means price is below benchmark (good deal)
    # discount < 0 means price is above benchmark (overpriced)
    discount = (asking_benchmark - price) / asking_benchmark
    
    # Score: 0-10 scale
    # discount = 0.20 (20% below benchmark) -> score 10 (exceptional)
    # discount = 0.10 (10% below benchmark) -> score 8 (excellent)
    # discount = 0.00 (at benchmark) -> score 6 (fair)
    # discount = -0.10 (10% above benchmark) -> score 4 (poor)
    # discount = -0.20 (20% above benchmark) -> score 2 (very poor)
    raw_score = 6.0 + (discount * 20.0)  # 6 base + 20*discount
    deal_score = max(0.0, min(10.0, raw_score))
    
    return {
        "deal_score": round(deal_score, 1),
        "estimated_value": estimated_value,
        "asking_benchmark": round(asking_benchmark, 2),
        "price": price,
        "price_discount": round(discount, 3),
    }


def calculate_profit_potential(listing: Dict[str, Any]) -> Dict[str, Any]:
    """Legacy compatibility helper for dashboard imports."""
    price = float(listing.get("price") or 0)
    estimated_value = float(listing.get("estimated_value") or price)
    profit_potential = max(0.0, estimated_value - price)
    profit_percentage = (profit_potential / price * 100.0) if price > 0 else 0.0
    return {
        "profit_potential": profit_potential,
        "profit_percentage": profit_percentage,
        "estimated_value": estimated_value,
        "price": price,
    }


def update_vehicle_valuations(batch_size: int = 100):
    """
    Update valuations for vehicles in database using the hybrid pricing engine.
    """
    from database.db import SessionLocal
    from database.models import Vehicle
    from intelligence.pricing.engine import pricing_engine

    logger.info(f"Starting valuation update with batch size {batch_size}")

    db = SessionLocal()
    try:
        vehicles = db.query(Vehicle).filter(
            Vehicle.is_active == True,
            ~Vehicle.source_id.like("demo_%"),
        ).limit(batch_size).all()

        logger.info(f"Found {len(vehicles)} vehicles to valuate")
        updated_count = 0
        skipped_count = 0

        for vehicle in vehicles:
            vehicle_data = {
                'source': vehicle.source.value if hasattr(vehicle.source, 'value') else str(vehicle.source),
                'brand': vehicle.brand or '',
                'model': vehicle.model or '',
                'year': vehicle.year,
                'km': vehicle.km,
                'price': vehicle.price,
                'vehicle_type': vehicle.vehicle_type.value if hasattr(vehicle.vehicle_type, 'value') else vehicle.vehicle_type,
                'ai_risk_score': getattr(vehicle, 'ai_risk_score', 5.0),
                'condition_score': getattr(vehicle, 'condition_score', 6.0),
            }
            pricing = pricing_engine.calculate_price(vehicle_data)
            if pricing.get('insufficient_data') or pricing.get('final_price') is None:
                skipped_count += 1
                continue

            estimated_price = pricing['final_price']
            vehicle.estimated_value = estimated_price
            updated_count += 1

            if vehicle.price:
                profit_potential = estimated_price - vehicle.price
                profit_percentage = (profit_potential / vehicle.price) * 100 if vehicle.price > 0 else 0
                vehicle.profit_potential = max(0, profit_potential)
                vehicle.profit_percentage = profit_percentage

        db.commit()
        logger.info(f"Updated {updated_count} valuations, skipped {skipped_count} (insufficient data)")

    except Exception as e:
        logger.error(f"Error updating valuations: {e}")
        db.rollback()
    finally:
        db.close()


def get_vehicle_valuation(vehicle_data: Dict[str, Any]) -> Dict[str, Any]:
    """
    Get complete valuation for a vehicle
    
    Args:
        vehicle_data: Vehicle data dictionary
        
    Returns:
        Dictionary with valuation information
    """
    model = VehicleValuationModel()
    if not model.load_model():
        return {'error': 'Model not available'}
    
    estimated_price = model.predict_price(vehicle_data)
    
    if estimated_price and vehicle_data.get('price'):
        current_price = vehicle_data['price']
        profit_potential = estimated_price - current_price
        profit_percentage = (profit_potential / current_price) * 100 if current_price > 0 else 0
        
        # Calculate deal score
        deal_score = min(10, max(0, (profit_percentage / 20) * 10))
        
        return {
            'estimated_price': estimated_price,
            'current_price': current_price,
            'profit_potential': max(0, profit_potential),
            'profit_percentage': profit_percentage,
            'deal_score': deal_score,
            'is_good_deal': deal_score >= 7.0
        }
    
    return {'error': 'Could not calculate valuation'}

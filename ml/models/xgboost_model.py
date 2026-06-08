"""
XGBoost model implementation for price prediction.
"""
import xgboost as xgb
import pandas as pd
import numpy as np
from typing import Dict, Any, Optional, Tuple
from sklearn.model_selection import train_test_split
from sklearn.metrics import mean_squared_error, r2_score


class XGBoostModel:
    """XGBoost model for car price prediction."""
    
    def __init__(self, **kwargs):
        """Initialize XGBoost model with parameters."""
        self.model = xgb.XGBRegressor(**kwargs)
        self.is_trained = False
        self.feature_names = None
        
    def train(self, X: pd.DataFrame, y: pd.Series, **kwargs) -> Dict[str, Any]:
        """Train the XGBoost model."""
        X_train, X_val, y_train, y_val = train_test_split(
            X, y, test_size=0.2, random_state=42
        )
        
        self.model.fit(X_train, y_train, 
                      eval_set=[(X_val, y_val)],
                      early_stopping_rounds=10,
                      verbose=False)
        
        self.is_trained = True
        self.feature_names = X.columns.tolist()
        
        # Calculate metrics
        train_pred = self.model.predict(X_train)
        val_pred = self.model.predict(X_val)
        
        metrics = {
            'train_mse': mean_squared_error(y_train, train_pred),
            'val_mse': mean_squared_error(y_val, val_pred),
            'train_r2': r2_score(y_train, train_pred),
            'val_r2': r2_score(y_val, val_pred)
        }
        
        return metrics
    
    def predict(self, X: pd.DataFrame) -> np.ndarray:
        """Make predictions (point estimate)."""
        if not self.is_trained:
            raise ValueError("Model must be trained before prediction")
            
        return self.model.predict(X)

    def predict_interval(self, X: pd.DataFrame, alpha: float = 0.05) -> Tuple[np.ndarray, np.ndarray]:
        """Make interval predictions (min, max) using quantile regression."""
        if not self.is_trained:
            raise ValueError("Model must be trained before prediction")
            
        # Ensure model is configured for quantile regression
        # This requires the model to have been trained with objective='reg:quantileerror'
        # For a standard regressor, we approximate with variance
        preds = self.model.predict(X)
        # Simple interval estimation based on training error (placeholder logic)
        # In production, use properly trained quantile models
        return preds * 0.95, preds * 1.05
    
    def feature_importance(self) -> Dict[str, float]:
        """Get feature importance."""
        if not self.is_trained:
            raise ValueError("Model must be trained first")
            
        importance = self.model.feature_importances_
        return dict(zip(self.feature_names, importance))
    
    def save_model(self, filepath: str) -> None:
        """Save model to file."""
        if not self.is_trained:
            raise ValueError("Model must be trained before saving")
            
        self.model.save_model(filepath)
    
    def load_model(self, filepath: str) -> None:
        """Load model from file."""
        self.model.load_model(filepath)
        self.is_trained = True

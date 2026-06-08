"""
Random Forest model implementation for price prediction.
"""
import pandas as pd
import numpy as np
from typing import Dict, Any, Optional
from sklearn.ensemble import RandomForestRegressor
from sklearn.model_selection import train_test_split
from sklearn.metrics import mean_squared_error, r2_score


class RandomForestModel:
    """Random Forest model for car price prediction."""
    
    def __init__(self, n_estimators: int = 100, random_state: int = 42, **kwargs):
        """Initialize Random Forest model."""
        self.model = RandomForestRegressor(
            n_estimators=n_estimators,
            random_state=random_state,
            **kwargs
        )
        self.is_trained = False
        self.feature_names = None
        
    def train(self, X: pd.DataFrame, y: pd.Series) -> Dict[str, Any]:
        """Train the Random Forest model."""
        X_train, X_val, y_train, y_val = train_test_split(
            X, y, test_size=0.2, random_state=42
        )
        
        self.model.fit(X_train, y_train)
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
        """Make predictions."""
        if not self.is_trained:
            raise ValueError("Model must be trained before prediction")
            
        return self.model.predict(X)
    
    def feature_importance(self) -> Dict[str, float]:
        """Get feature importance."""
        if not self.is_trained:
            raise ValueError("Model must be trained first")
            
        importance = self.model.feature_importances_
        return dict(zip(self.feature_names, importance))

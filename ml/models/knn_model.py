"""
KNN model implementation for price prediction.
"""
import pandas as pd
import numpy as np
from typing import Dict, Any
from sklearn.neighbors import KNeighborsRegressor
from sklearn.model_selection import train_test_split
from sklearn.metrics import mean_squared_error, r2_score
from sklearn.preprocessing import StandardScaler


class KNNModel:
    """KNN model for car price prediction."""
    
    def __init__(self, n_neighbors: int = 5, **kwargs):
        """Initialize KNN model."""
        self.model = KNeighborsRegressor(n_neighbors=n_neighbors, **kwargs)
        self.scaler = StandardScaler()
        self.is_trained = False
        self.feature_names = None
        
    def train(self, X: pd.DataFrame, y: pd.Series) -> Dict[str, Any]:
        """Train the KNN model."""
        X_train, X_val, y_train, y_val = train_test_split(
            X, y, test_size=0.2, random_state=42
        )
        
        # Scale features
        X_train_scaled = self.scaler.fit_transform(X_train)
        X_val_scaled = self.scaler.transform(X_val)
        
        self.model.fit(X_train_scaled, y_train)
        self.is_trained = True
        self.feature_names = X.columns.tolist()
        
        # Calculate metrics
        train_pred = self.model.predict(X_train_scaled)
        val_pred = self.model.predict(X_val_scaled)
        
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
            
        X_scaled = self.scaler.transform(X)
        return self.model.predict(X_scaled)

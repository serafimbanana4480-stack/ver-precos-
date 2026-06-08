"""
Model trainer for ML models.
"""
import pandas as pd
import numpy as np
from typing import Dict, Any, List, Optional
import joblib
import os
from datetime import datetime
import json

from ..models import XGBoostModel, RandomForestModel, LinearRegressionModel, NeuralNetworkModel, SVMModel, KNNModel


class ModelTrainer:
    """Trainer class for ML models."""
    
    def __init__(self, models_dir: str = "models"):
        """Initialize trainer."""
        self.models_dir = models_dir
        self.trained_models = {}
        self.training_history = {}
        
        # Create models directory if it doesn't exist
        os.makedirs(models_dir, exist_ok=True)
        
    def train_all_models(self, X: pd.DataFrame, y: pd.Series, **kwargs) -> Dict[str, Dict[str, Any]]:
        """Train models separated by vehicle type."""
        # Assume 'vehicle_type' exists in X
        results = {}
        vehicle_types = X['vehicle_type'].unique()
        
        for v_type in vehicle_types:
            X_v = X[X['vehicle_type'] == v_type].drop(columns=['vehicle_type'])
            y_v = y[X['vehicle_type'] == v_type]
            
            # Train model for this vehicle type (e.g., car or motorcycle)
            print(f"Training models for: {v_type}")
            # ... training logic ...
            
        return results
    
    def get_best_model(self, metric: str = 'val_r2') -> tuple:
        """Get the best performing model based on specified metric."""
        best_model_name = None
        best_score = float('-inf') if 'r2' in metric else float('inf')
        
        for name, metrics in self.training_history.items():
            if 'error' in metrics:
                continue
                
            score = metrics.get(metric)
            if score is None:
                continue
                
            if 'r2' in metric and score > best_score:
                best_score = score
                best_model_name = name
            elif 'mse' in metric and score < best_score:
                best_score = score
                best_model_name = name
        
        return best_model_name, best_score
    
    def save_model(self, name: str, model) -> None:
        """Save trained model to disk."""
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        filepath = os.path.join(self.models_dir, f"{name}_{timestamp}.pkl")
        joblib.dump(model, filepath)
        
        # Also save as latest
        latest_filepath = os.path.join(self.models_dir, f"{name}_latest.pkl")
        joblib.dump(model, latest_filepath)
    
    def load_model(self, name: str, version: str = 'latest') -> Any:
        """Load trained model from disk."""
        filepath = os.path.join(self.models_dir, f"{name}_{version}.pkl")
        return joblib.load(filepath)
    
    def save_training_history(self, results: Dict[str, Dict[str, Any]]) -> None:
        """Save training history to JSON file."""
        self.training_history = results
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        filepath = os.path.join(self.models_dir, f"training_history_{timestamp}.json")
        
        with open(filepath, 'w') as f:
            json.dump(results, f, indent=2, default=str)
    
    def predict_with_model(self, model_name: str, X: pd.DataFrame) -> np.ndarray:
        """Make predictions using a specific trained model."""
        if model_name not in self.trained_models:
            raise ValueError(f"Model {model_name} not found in trained models")
        
        return self.trained_models[model_name].predict(X)


# Legacy compatibility alias.
Trainer = ModelTrainer

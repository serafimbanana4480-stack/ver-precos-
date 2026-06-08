"""
ML predictor for price prediction inference.
"""
import pandas as pd
import numpy as np
from typing import Dict, Any, List, Optional, Union
import joblib
import os
from datetime import datetime

from ..models import XGBoostModel, RandomForestModel, LinearRegressionModel, NeuralNetworkModel, SVMModel, KNNModel


class Predictor:
    """ML predictor for car price prediction."""
    
    def __init__(self, model_dir: str = "models"):
        """Initialize predictor."""
        self.model_dir = model_dir
        self.loaded_models = {}
        self.default_model = None
        self.feature_columns = None
        
        # Create models directory if it doesn't exist
        os.makedirs(model_dir, exist_ok=True)
    
    def load_model(self, model_name: str, version: str = 'latest') -> Any:
        """Load a trained model from disk."""
        if model_name in self.loaded_models:
            return self.loaded_models[model_name]
        
        filepath = os.path.join(self.model_dir, f"{model_name}_{version}.pkl")
        
        if not os.path.exists(filepath):
            raise FileNotFoundError(f"Model file not found: {filepath}")
        
        model = joblib.load(filepath)
        self.loaded_models[model_name] = model
        
        # Set as default if it's the first model loaded
        if self.default_model is None:
            self.default_model = model_name
        
        return model
    
    def set_default_model(self, model_name: str) -> None:
        """Set the default model for predictions."""
        if model_name not in self.loaded_models:
            self.load_model(model_name)
        
        self.default_model = model_name
    
    def predict_single(self, features: Dict[str, Any], model_name: str = None) -> Dict[str, Any]:
        """Make prediction for a single car listing."""
        if model_name is None:
            model_name = self.default_model
        
        if model_name is None:
            raise ValueError("No model specified and no default model set")
        
        if model_name not in self.loaded_models:
            self.load_model(model_name)
        
        # Convert features to DataFrame
        df = pd.DataFrame([features])
        
        # Ensure all required features are present
        if self.feature_columns is not None:
            for col in self.feature_columns:
                if col not in df.columns:
                    df[col] = 0  # Default value for missing features
            
            # Reorder columns to match training data
            df = df[self.feature_columns]
        
        # Make prediction
        model = self.loaded_models[model_name]
        prediction = model.predict(df)[0]
        
        # Calculate prediction confidence (if available)
        confidence = self._calculate_confidence(model, df)
        
        result = {
            'predicted_price': float(prediction),
            'model_used': model_name,
            'confidence': confidence,
            'timestamp': datetime.now().isoformat(),
            'features': features
        }
        
        return result
    
    def predict_batch(self, features_list: List[Dict[str, Any]], model_name: str = None) -> List[Dict[str, Any]]:
        """Make predictions for multiple car listings."""
        if model_name is None:
            model_name = self.default_model
        
        if model_name is None:
            raise ValueError("No model specified and no default model set")
        
        if model_name not in self.loaded_models:
            self.load_model(model_name)
        
        # Convert features to DataFrame
        df = pd.DataFrame(features_list)
        
        # Ensure all required features are present
        if self.feature_columns is not None:
            for col in self.feature_columns:
                if col not in df.columns:
                    df[col] = 0  # Default value for missing features
            
            # Reorder columns to match training data
            df = df[self.feature_columns]
        
        # Make predictions
        model = self.loaded_models[model_name]
        predictions = model.predict(df)
        
        # Calculate confidence scores
        confidences = self._calculate_confidence_batch(model, df)
        
        results = []
        for i, features in enumerate(features_list):
            result = {
                'predicted_price': float(predictions[i]),
                'model_used': model_name,
                'confidence': confidences[i],
                'timestamp': datetime.now().isoformat(),
                'features': features
            }
            results.append(result)
        
        return results
    
    def predict_from_dataframe(self, df: pd.DataFrame, model_name: str = None) -> pd.DataFrame:
        """Make predictions from a pandas DataFrame."""
        if model_name is None:
            model_name = self.default_model
        
        if model_name is None:
            raise ValueError("No model specified and no default model set")
        
        if model_name not in self.loaded_models:
            self.load_model(model_name)
        
        # Ensure all required features are present
        if self.feature_columns is not None:
            for col in self.feature_columns:
                if col not in df.columns:
                    df[col] = 0  # Default value for missing features
            
            # Reorder columns to match training data
            df = df[self.feature_columns]
        
        # Make predictions
        model = self.loaded_models[model_name]
        predictions = model.predict(df)
        
        # Add predictions to DataFrame
        df_copy = df.copy()
        df_copy['predicted_price'] = predictions
        df_copy['model_used'] = model_name
        df_copy['prediction_timestamp'] = datetime.now().isoformat()
        
        return df_copy
    
    def _calculate_confidence(self, model: Any, df: pd.DataFrame) -> float:
        """Calculate prediction confidence score."""
        try:
            # For tree-based models, use prediction variance
            if hasattr(model, 'predict'):
                if hasattr(model, 'estimators_'):
                    # Random Forest - use std of predictions from all trees
                    tree_predictions = []
                    for estimator in model.estimators_:
                        tree_predictions.append(estimator.predict(df)[0])
                    
                    confidence = 1.0 - (np.std(tree_predictions) / np.mean(tree_predictions))
                    return max(0.0, min(1.0, confidence))
                
                # For other models, return a default confidence
                return 0.8
            else:
                return 0.8
                
        except Exception:
            return 0.8  # Default confidence
    
    def _calculate_confidence_batch(self, model: Any, df: pd.DataFrame) -> List[float]:
        """Calculate confidence scores for batch predictions."""
        confidences = []
        
        for _, row in df.iterrows():
            confidence = self._calculate_confidence(model, pd.DataFrame([row]))
            confidences.append(confidence)
        
        return confidences
    
    def get_feature_importance(self, model_name: str = None) -> Dict[str, float]:
        """Get feature importance from a loaded model."""
        if model_name is None:
            model_name = self.default_model
        
        if model_name is None:
            raise ValueError("No model specified and no default model set")
        
        if model_name not in self.loaded_models:
            self.load_model(model_name)
        
        model = self.loaded_models[model_name]
        
        if hasattr(model, 'feature_importance'):
            return model.feature_importance()
        elif hasattr(model, 'feature_importances_'):
            if self.feature_columns is not None:
                return dict(zip(self.feature_columns, model.feature_importances_))
            else:
                return {f'feature_{i}': imp for i, imp in enumerate(model.feature_importances_)}
        else:
            return {}
    
    def set_feature_columns(self, columns: List[str]) -> None:
        """Set the expected feature columns for predictions."""
        self.feature_columns = columns
    
    def get_loaded_models(self) -> List[str]:
        """Get list of loaded model names."""
        return list(self.loaded_models.keys())
    
    def unload_model(self, model_name: str) -> None:
        """Unload a model from memory."""
        if model_name in self.loaded_models:
            del self.loaded_models[model_name]
            
            # Update default model if necessary
            if self.default_model == model_name:
                self.default_model = None
                if self.loaded_models:
                    self.default_model = list(self.loaded_models.keys())[0]

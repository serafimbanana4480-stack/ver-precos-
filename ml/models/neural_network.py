"""
Neural Network model implementation for price prediction.
"""
import pandas as pd
import numpy as np
from typing import Dict, Any, Tuple
from sklearn.preprocessing import StandardScaler
from sklearn.model_selection import train_test_split
from sklearn.metrics import mean_squared_error, r2_score
import tensorflow as tf
from tensorflow import keras


class NeuralNetworkModel:
    """Neural Network model for car price prediction."""
    
    def __init__(self, hidden_layers: list = [64, 32], **kwargs):
        """Initialize Neural Network model."""
        self.hidden_layers = hidden_layers
        self.model = None
        self.scaler_X = StandardScaler()
        self.scaler_y = StandardScaler()
        self.is_trained = False
        self.feature_names = None
        
    def _build_model(self, input_shape: int) -> keras.Model:
        """Build the neural network architecture."""
        model = keras.Sequential()
        
        # Input layer
        model.add(keras.layers.Dense(
            self.hidden_layers[0], 
            activation='relu', 
            input_shape=(input_shape,)
        ))
        model.add(keras.layers.Dropout(0.2))
        
        # Hidden layers
        for units in self.hidden_layers[1:]:
            model.add(keras.layers.Dense(units, activation='relu'))
            model.add(keras.layers.Dropout(0.2))
        
        # Output layer
        model.add(keras.layers.Dense(1, activation='linear'))
        
        model.compile(
            optimizer='adam',
            loss='mse',
            metrics=['mae']
        )
        
        return model
    
    def train(self, X: pd.DataFrame, y: pd.Series, epochs: int = 100) -> Dict[str, Any]:
        """Train the Neural Network model."""
        X_train, X_val, y_train, y_val = train_test_split(
            X, y, test_size=0.2, random_state=42
        )
        
        # Scale features
        X_train_scaled = self.scaler_X.fit_transform(X_train)
        X_val_scaled = self.scaler_X.transform(X_val)
        
        # Scale target
        y_train_scaled = self.scaler_y.fit_transform(y_train.values.reshape(-1, 1)).ravel()
        y_val_scaled = self.scaler_y.transform(y_val.values.reshape(-1, 1)).ravel()
        
        # Build and train model
        self.model = self._build_model(X_train.shape[1])
        
        history = self.model.fit(
            X_train_scaled, y_train_scaled,
            validation_data=(X_val_scaled, y_val_scaled),
            epochs=epochs,
            batch_size=32,
            verbose=0
        )
        
        self.is_trained = True
        self.feature_names = X.columns.tolist()
        
        # Calculate metrics
        train_pred_scaled = self.model.predict(X_train_scaled)
        val_pred_scaled = self.model.predict(X_val_scaled)
        
        train_pred = self.scaler_y.inverse_transform(train_pred_scaled).ravel()
        val_pred = self.scaler_y.inverse_transform(val_pred_scaled).ravel()
        
        metrics = {
            'train_mse': mean_squared_error(y_train, train_pred),
            'val_mse': mean_squared_error(y_val, val_pred),
            'train_r2': r2_score(y_train, train_pred),
            'val_r2': r2_score(y_val, val_pred),
            'history': history.history
        }
        
        return metrics
    
    def predict(self, X: pd.DataFrame) -> np.ndarray:
        """Make predictions."""
        if not self.is_trained:
            raise ValueError("Model must be trained before prediction")
            
        X_scaled = self.scaler_X.transform(X)
        pred_scaled = self.model.predict(X_scaled)
        return self.scaler_y.inverse_transform(pred_scaled).ravel()

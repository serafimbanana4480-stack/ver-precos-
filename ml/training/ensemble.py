"""
Ensemble methods for ML models.
"""
import pandas as pd
import numpy as np
from typing import Dict, Any, List, Tuple
from sklearn.ensemble import VotingRegressor, BaggingRegressor, StackingRegressor
from sklearn.linear_model import LinearRegression
import warnings
warnings.filterwarnings('ignore')

from ..models import XGBoostModel, RandomForestModel, LinearRegressionModel, SVMModel, KNNModel


class EnsembleTrainer:
    """Ensemble methods for combining multiple models."""
    
    def __init__(self):
        """Initialize ensemble trainer."""
        self.ensemble_models = {}
        self.ensemble_results = {}
        
    def voting_ensemble(self, X: pd.DataFrame, y: pd.Series, models: List[str] = None) -> Dict[str, Any]:
        """Create a voting ensemble of models."""
        if models is None:
            models = ['xgboost', 'random_forest', 'linear_regression']
        
        # Train individual models
        trained_models = {}
        model_params = {}
        
        for model_name in models:
            if model_name == 'xgboost':
                model = XGBoostModel()
            elif model_name == 'random_forest':
                model = RandomForestModel()
            elif model_name == 'linear_regression':
                model = LinearRegressionModel()
            elif model_name == 'svm':
                model = SVMModel()
            elif model_name == 'knn':
                model = KNNModel()
            else:
                continue
                
            metrics = model.train(X, y)
            trained_models[model_name] = model
            model_params[model_name] = metrics
        
        # Create voting ensemble
        estimators = [(name, model.model) for name, model in trained_models.items()]
        voting_model = VotingRegressor(estimators=estimators)
        
        # Split data for evaluation
        from sklearn.model_selection import train_test_split
        X_train, X_val, y_train, y_val = train_test_split(X, y, test_size=0.2, random_state=42)
        
        voting_model.fit(X_train, y_train)
        
        # Make predictions
        y_pred = voting_model.predict(X_val)
        
        # Calculate metrics
        from sklearn.metrics import mean_squared_error, r2_score, mean_absolute_error
        
        ensemble_metrics = {
            'mse': mean_squared_error(y_val, y_pred),
            'r2': r2_score(y_val, y_pred),
            'mae': mean_absolute_error(y_val, y_pred),
            'individual_models': model_params
        }
        
        self.ensemble_models['voting'] = voting_model
        self.ensemble_results['voting'] = ensemble_metrics
        
        return ensemble_metrics
    
    def bagging_ensemble(self, X: pd.DataFrame, y: pd.Series, base_model: str = 'random_forest') -> Dict[str, Any]:
        """Create a bagging ensemble."""
        # Select base model
        if base_model == 'xgboost':
            base_estimator = XGBoostModel().model
        elif base_model == 'random_forest':
            base_estimator = RandomForestModel().model
        elif base_model == 'linear_regression':
            base_estimator = LinearRegressionModel().model
        else:
            base_estimator = RandomForestModel().model
        
        # Create bagging ensemble
        bagging_model = BaggingRegressor(
            base_estimator=base_estimator,
            n_estimators=10,
            max_samples=0.8,
            max_features=0.8,
            random_state=42
        )
        
        # Split data for evaluation
        from sklearn.model_selection import train_test_split
        X_train, X_val, y_train, y_val = train_test_split(X, y, test_size=0.2, random_state=42)
        
        bagging_model.fit(X_train, y_train)
        
        # Make predictions
        y_pred = bagging_model.predict(X_val)
        
        # Calculate metrics
        from sklearn.metrics import mean_squared_error, r2_score, mean_absolute_error
        
        metrics = {
            'mse': mean_squared_error(y_val, y_pred),
            'r2': r2_score(y_val, y_pred),
            'mae': mean_absolute_error(y_val, y_pred),
            'base_model': base_model
        }
        
        self.ensemble_models['bagging'] = bagging_model
        self.ensemble_results['bagging'] = metrics
        
        return metrics
    
    def stacking_ensemble(self, X: pd.DataFrame, y: pd.Series) -> Dict[str, Any]:
        """Create a stacking ensemble."""
        # Base models
        base_models = [
            ('xgboost', XGBoostModel().model),
            ('random_forest', RandomForestModel().model),
            ('svm', SVMModel().model)
        ]
        
        # Meta model
        meta_model = LinearRegression()
        
        # Create stacking ensemble
        stacking_model = StackingRegressor(
            estimators=base_models,
            final_estimator=meta_model,
            cv=5
        )
        
        # Split data for evaluation
        from sklearn.model_selection import train_test_split
        X_train, X_val, y_train, y_val = train_test_split(X, y, test_size=0.2, random_state=42)
        
        stacking_model.fit(X_train, y_train)
        
        # Make predictions
        y_pred = stacking_model.predict(X_val)
        
        # Calculate metrics
        from sklearn.metrics import mean_squared_error, r2_score, mean_absolute_error
        
        metrics = {
            'mse': mean_squared_error(y_val, y_pred),
            'r2': r2_score(y_val, y_pred),
            'mae': mean_absolute_error(y_val, y_pred)
        }
        
        self.ensemble_models['stacking'] = stacking_model
        self.ensemble_results['stacking'] = metrics
        
        return metrics
    
    def weighted_ensemble(self, X: pd.DataFrame, y: pd.Series, weights: Dict[str, float] = None) -> Dict[str, Any]:
        """Create a weighted ensemble with custom weights."""
        if weights is None:
            weights = {
                'xgboost': 0.4,
                'random_forest': 0.3,
                'linear_regression': 0.3
            }
        
        # Train individual models
        trained_models = {}
        model_metrics = {}
        
        for model_name, weight in weights.items():
            if model_name == 'xgboost':
                model = XGBoostModel()
            elif model_name == 'random_forest':
                model = RandomForestModel()
            elif model_name == 'linear_regression':
                model = LinearRegressionModel()
            elif model_name == 'svm':
                model = SVMModel()
            elif model_name == 'knn':
                model = KNNModel()
            else:
                continue
                
            metrics = model.train(X, y)
            trained_models[model_name] = model
            model_metrics[model_name] = metrics
        
        # Split data for evaluation
        from sklearn.model_selection import train_test_split
        X_train, X_val, y_train, y_val = train_test_split(X, y, test_size=0.2, random_state=42)
        
        # Make weighted predictions
        weighted_predictions = np.zeros(len(X_val))
        
        for model_name, weight in weights.items():
            if model_name in trained_models:
                predictions = trained_models[model_name].predict(X_val)
                weighted_predictions += weight * predictions
        
        # Calculate metrics
        from sklearn.metrics import mean_squared_error, r2_score, mean_absolute_error
        
        metrics = {
            'mse': mean_squared_error(y_val, weighted_predictions),
            'r2': r2_score(y_val, weighted_predictions),
            'mae': mean_absolute_error(y_val, weighted_predictions),
            'weights': weights,
            'individual_models': model_metrics
        }
        
        self.ensemble_results['weighted'] = metrics
        
        return metrics
    
    def compare_ensembles(self, X: pd.DataFrame, y: pd.Series) -> Dict[str, Dict[str, Any]]:
        """Compare different ensemble methods."""
        print("Training voting ensemble...")
        voting_results = self.voting_ensemble(X, y)
        
        print("Training bagging ensemble...")
        bagging_results = self.bagging_ensemble(X, y)
        
        print("Training stacking ensemble...")
        stacking_results = self.stacking_ensemble(X, y)
        
        print("Training weighted ensemble...")
        weighted_results = self.weighted_ensemble(X, y)
        
        results = {
            'voting': voting_results,
            'bagging': bagging_results,
            'stacking': stacking_results,
            'weighted': weighted_results
        }
        
        # Print comparison
        print("\nEnsemble Comparison:")
        for name, metrics in results.items():
            print(f"{name.capitalize()} - R2: {metrics['r2']:.4f}, MSE: {metrics['mse']:.4f}")
        
        return results
    
    def get_best_ensemble(self) -> Tuple[str, Dict[str, Any]]:
        """Get the best performing ensemble method."""
        best_ensemble = None
        best_r2 = float('-inf')
        
        for name, metrics in self.ensemble_results.items():
            if metrics['r2'] > best_r2:
                best_r2 = metrics['r2']
                best_ensemble = name
        
        return best_ensemble, self.ensemble_results[best_ensemble]
    
    def predict_with_ensemble(self, ensemble_name: str, X: pd.DataFrame) -> np.ndarray:
        """Make predictions using a specific ensemble."""
        if ensemble_name not in self.ensemble_models:
            raise ValueError(f"Ensemble {ensemble_name} not found")
        
        return self.ensemble_models[ensemble_name].predict(X)

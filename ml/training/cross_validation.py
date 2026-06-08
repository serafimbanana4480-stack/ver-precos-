"""
Cross validation utilities for ML models.
"""
import pandas as pd
import numpy as np
from typing import Dict, Any, List, Tuple
from sklearn.model_selection import KFold, StratifiedKFold, TimeSeriesSplit, cross_val_score
from sklearn.metrics import mean_squared_error, r2_score, mean_absolute_error
import warnings
warnings.filterwarnings('ignore')

from ..models import XGBoostModel, RandomForestModel, LinearRegressionModel, SVMModel, KNNModel


class CrossValidator:
    """Cross validation utilities for ML models."""
    
    def __init__(self, cv_folds: int = 5, random_state: int = 42):
        """Initialize cross validator."""
        self.cv_folds = cv_folds
        self.random_state = random_state
        self.cv_results = {}
        
    def kfold_cv(self, X: pd.DataFrame, y: pd.Series, model_class, **model_params) -> Dict[str, Any]:
        """Perform K-Fold cross validation."""
        kf = KFold(n_splits=self.cv_folds, shuffle=True, random_state=self.random_state)
        
        scores = {
            'mse_scores': [],
            'r2_scores': [],
            'mae_scores': [],
            'fold_results': []
        }
        
        for fold, (train_idx, val_idx) in enumerate(kf.split(X)):
            X_train, X_val = X.iloc[train_idx], X.iloc[val_idx]
            y_train, y_val = y.iloc[train_idx], y.iloc[val_idx]
            
            model = model_class(**model_params)
            metrics = model.train(X_train, y_train)
            
            # Make predictions on validation set
            y_pred = model.predict(X_val)
            
            # Calculate metrics
            mse = mean_squared_error(y_val, y_pred)
            r2 = r2_score(y_val, y_pred)
            mae = mean_absolute_error(y_val, y_pred)
            
            scores['mse_scores'].append(mse)
            scores['r2_scores'].append(r2)
            scores['mae_scores'].append(mae)
            
            fold_result = {
                'fold': fold + 1,
                'mse': mse,
                'r2': r2,
                'mae': mae,
                'train_size': len(train_idx),
                'val_size': len(val_idx)
            }
            scores['fold_results'].append(fold_result)
        
        # Calculate summary statistics
        scores['mean_mse'] = np.mean(scores['mse_scores'])
        scores['std_mse'] = np.std(scores['mse_scores'])
        scores['mean_r2'] = np.mean(scores['r2_scores'])
        scores['std_r2'] = np.std(scores['r2_scores'])
        scores['mean_mae'] = np.mean(scores['mae_scores'])
        scores['std_mae'] = np.std(scores['mae_scores'])
        
        return scores
    
    def time_series_cv(self, X: pd.DataFrame, y: pd.Series, model_class, **model_params) -> Dict[str, Any]:
        """Perform Time Series cross validation."""
        tscv = TimeSeriesSplit(n_splits=self.cv_folds)
        
        scores = {
            'mse_scores': [],
            'r2_scores': [],
            'mae_scores': [],
            'fold_results': []
        }
        
        for fold, (train_idx, val_idx) in enumerate(tscv.split(X)):
            X_train, X_val = X.iloc[train_idx], X.iloc[val_idx]
            y_train, y_val = y.iloc[train_idx], y.iloc[val_idx]
            
            model = model_class(**model_params)
            metrics = model.train(X_train, y_train)
            
            # Make predictions on validation set
            y_pred = model.predict(X_val)
            
            # Calculate metrics
            mse = mean_squared_error(y_val, y_pred)
            r2 = r2_score(y_val, y_pred)
            mae = mean_absolute_error(y_val, y_pred)
            
            scores['mse_scores'].append(mse)
            scores['r2_scores'].append(r2)
            scores['mae_scores'].append(mae)
            
            fold_result = {
                'fold': fold + 1,
                'mse': mse,
                'r2': r2,
                'mae': mae,
                'train_size': len(train_idx),
                'val_size': len(val_idx)
            }
            scores['fold_results'].append(fold_result)
        
        # Calculate summary statistics
        scores['mean_mse'] = np.mean(scores['mse_scores'])
        scores['std_mse'] = np.std(scores['mse_scores'])
        scores['mean_r2'] = np.mean(scores['r2_scores'])
        scores['std_r2'] = np.std(scores['r2_scores'])
        scores['mean_mae'] = np.mean(scores['mae_scores'])
        scores['std_mae'] = np.std(scores['mae_scores'])
        
        return scores
    
    def compare_models_cv(self, X: pd.DataFrame, y: pd.Series) -> Dict[str, Dict[str, Any]]:
        """Compare multiple models using cross validation."""
        models = {
            'xgboost': (XGBoostModel, {}),
            'random_forest': (RandomForestModel, {}),
            'linear_regression': (LinearRegressionModel, {}),
            'svm': (SVMModel, {}),
            'knn': (KNNModel, {})
        }
        
        results = {}
        
        for name, (model_class, params) in models.items():
            print(f"Cross validating {name}...")
            
            try:
                cv_scores = self.kfold_cv(X, y, model_class, **params)
                results[name] = cv_scores
                
                print(f"{name} - Mean R2: {cv_scores['mean_r2']:.4f} (+/- {cv_scores['std_r2']:.4f})")
                
            except Exception as e:
                print(f"Error cross validating {name}: {e}")
                results[name] = {'error': str(e)}
        
        self.cv_results = results
        return results
    
    def get_best_model_cv(self, metric: str = 'mean_r2') -> Tuple[str, float]:
        """Get the best model based on cross validation results."""
        best_model = None
        best_score = float('-inf') if 'r2' in metric else float('inf')
        
        for name, scores in self.cv_results.items():
            if 'error' in scores:
                continue
                
            score = scores.get(metric)
            if score is None:
                continue
                
            if 'r2' in metric and score > best_score:
                best_score = score
                best_model = name
            elif 'mse' in metric and score < best_score:
                best_score = score
                best_model = name
        
        return best_model, best_score
    
    def get_cv_summary(self) -> pd.DataFrame:
        """Get a summary table of cross validation results."""
        summary_data = []
        
        for name, scores in self.cv_results.items():
            if 'error' in scores:
                continue
                
            summary_data.append({
                'Model': name,
                'Mean R2': scores['mean_r2'],
                'Std R2': scores['std_r2'],
                'Mean MSE': scores['mean_mse'],
                'Std MSE': scores['std_mse'],
                'Mean MAE': scores['mean_mae'],
                'Std MAE': scores['std_mae']
            })
        
        return pd.DataFrame(summary_data).sort_values('Mean R2', ascending=False)

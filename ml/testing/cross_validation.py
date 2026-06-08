"""
Cross validation testing for ML models.
"""
import pandas as pd
import numpy as np
from typing import Dict, Any, List, Optional
from sklearn.model_selection import KFold, StratifiedKFold, TimeSeriesSplit
from sklearn.metrics import mean_squared_error, r2_score, mean_absolute_error
import warnings
warnings.filterwarnings('ignore')


class CrossValidator:
    """Cross validation testing for ML models."""
    
    def __init__(self, cv_folds: int = 5, random_state: int = 42):
        """Initialize cross validator."""
        self.cv_folds = cv_folds
        self.random_state = random_state
        self.cv_results = {}
        
    def test_cross_validation_stability(self, 
                                      model_class: Any, 
                                      X: pd.DataFrame, 
                                      y: pd.Series,
                                      n_runs: int = 3) -> Dict[str, Any]:
        """Test cross validation stability across multiple runs."""
        
        stability_results = {
            'runs': [],
            'mean_r2': 0,
            'std_r2': 0,
            'is_stable': True
        }
        
        all_r2_scores = []
        
        for run in range(n_runs):
            # Create model instance
            model = model_class()
            
            # Perform cross validation
            cv_scores = self._perform_cv(model, X, y)
            
            run_result = {
                'run': run + 1,
                'mean_r2': cv_scores['mean_r2'],
                'std_r2': cv_scores['std_r2'],
                'fold_scores': cv_scores['r2_scores']
            }
            
            stability_results['runs'].append(run_result)
            all_r2_scores.append(cv_scores['mean_r2'])
        
        # Calculate stability metrics
        stability_results['mean_r2'] = np.mean(all_r2_scores)
        stability_results['std_r2'] = np.std(all_r2_scores)
        
        # Consider stable if standard deviation is less than 0.05
        stability_results['is_stable'] = stability_results['std_r2'] < 0.05
        
        return stability_results
    
    def _perform_cv(self, model: Any, X: pd.DataFrame, y: pd.Series) -> Dict[str, Any]:
        """Perform cross validation on a model."""
        
        kf = KFold(n_splits=self.cv_folds, shuffle=True, random_state=self.random_state)
        
        r2_scores = []
        mse_scores = []
        mae_scores = []
        
        for fold, (train_idx, val_idx) in enumerate(kf.split(X)):
            X_train, X_val = X.iloc[train_idx], X.iloc[val_idx]
            y_train, y_val = y.iloc[train_idx], y.iloc[val_idx]
            
            # Train model
            model.train(X_train, y_train)
            
            # Make predictions
            y_pred = model.predict(X_val)
            
            # Calculate metrics
            r2 = r2_score(y_val, y_pred)
            mse = mean_squared_error(y_val, y_pred)
            mae = mean_absolute_error(y_val, y_pred)
            
            r2_scores.append(r2)
            mse_scores.append(mse)
            mae_scores.append(mae)
        
        return {
            'r2_scores': r2_scores,
            'mse_scores': mse_scores,
            'mae_scores': mae_scores,
            'mean_r2': np.mean(r2_scores),
            'std_r2': np.std(r2_scores),
            'mean_mse': np.mean(mse_scores),
            'std_mse': np.std(mse_scores),
            'mean_mae': np.mean(mae_scores),
            'std_mae': np.std(mae_scores)
        }
    
    def test_different_cv_strategies(self, 
                                   model_class: Any, 
                                   X: pd.DataFrame, 
                                   y: pd.Series) -> Dict[str, Any]:
        """Test different cross validation strategies."""
        
        strategies = {
            'kfold': KFold(n_splits=self.cv_folds, shuffle=True, random_state=self.random_state),
            'stratified': StratifiedKFold(n_splits=self.cv_folds, shuffle=True, random_state=self.random_state),
            'time_series': TimeSeriesSplit(n_splits=self.cv_folds)
        }
        
        strategy_results = {}
        
        for strategy_name, cv_strategy in strategies.items():
            try:
                model = model_class()
                results = self._perform_cv_with_strategy(model, X, y, cv_strategy)
                strategy_results[strategy_name] = results
            except Exception as e:
                strategy_results[strategy_name] = {'error': str(e)}
        
        return strategy_results
    
    def _perform_cv_with_strategy(self, 
                                 model: Any, 
                                 X: pd.DataFrame, 
                                 y: pd.Series,
                                 cv_strategy) -> Dict[str, Any]:
        """Perform cross validation with specific strategy."""
        
        r2_scores = []
        mse_scores = []
        mae_scores = []
        
        for fold, (train_idx, val_idx) in enumerate(cv_strategy.split(X, y)):
            X_train, X_val = X.iloc[train_idx], X.iloc[val_idx]
            y_train, y_val = y.iloc[train_idx], y.iloc[val_idx]
            
            # Train model
            model.train(X_train, y_train)
            
            # Make predictions
            y_pred = model.predict(X_val)
            
            # Calculate metrics
            r2 = r2_score(y_val, y_pred)
            mse = mean_squared_error(y_val, y_pred)
            mae = mean_absolute_error(y_val, y_pred)
            
            r2_scores.append(r2)
            mse_scores.append(mse)
            mae_scores.append(mae)
        
        return {
            'r2_scores': r2_scores,
            'mse_scores': mse_scores,
            'mae_scores': mae_scores,
            'mean_r2': np.mean(r2_scores),
            'std_r2': np.std(r2_scores),
            'mean_mse': np.mean(mse_scores),
            'std_mse': np.std(mse_scores),
            'mean_mae': np.mean(mae_scores),
            'std_mae': np.std(mae_scores)
        }
    
    def test_cv_folds_sensitivity(self, 
                                model_class: Any, 
                                X: pd.DataFrame, 
                                y: pd.Series,
                                fold_range: List[int] = [3, 5, 7, 10]) -> Dict[str, Any]:
        """Test sensitivity to number of CV folds."""
        
        fold_results = {}
        
        for n_folds in fold_range:
            try:
                model = model_class()
                kf = KFold(n_splits=n_folds, shuffle=True, random_state=self.random_state)
                results = self._perform_cv_with_strategy(model, X, y, kf)
                fold_results[n_folds] = results
            except Exception as e:
                fold_results[n_folds] = {'error': str(e)}
        
        return fold_results
    
    def validate_cv_results(self, cv_results: Dict[str, Any]) -> Dict[str, Any]:
        """Validate cross validation results."""
        
        validation = {
            'has_results': bool(cv_results),
            'has_mean_r2': 'mean_r2' in cv_results,
            'has_std_r2': 'std_r2' in cv_results,
            'r2_reasonable': False,
            'std_reasonable': False,
            'validation_passed': False
        }
        
        if cv_results and 'mean_r2' in cv_results:
            r2 = cv_results['mean_r2']
            std = cv_results.get('std_r2', 0)
            
            validation['r2_reasonable'] = 0 <= r2 <= 1
            validation['std_reasonable'] = std >= 0 and std <= 1
            validation['validation_passed'] = validation['r2_reasonable'] and validation['std_reasonable']
        
        return validation


# Legacy compatibility alias.
CrossValidation = CrossValidator

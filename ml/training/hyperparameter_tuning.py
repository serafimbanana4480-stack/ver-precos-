"""
Hyperparameter tuning for ML models.
"""
import pandas as pd
import numpy as np
from typing import Dict, Any, List, Tuple
from sklearn.model_selection import GridSearchCV, RandomizedSearchCV
from scipy.stats import uniform, randint
import optuna
from optuna.samplers import TPESampler
from optuna.pruners import MedianPruner

from ..models import XGBoostModel, RandomForestModel, SVMModel, KNNModel


class HyperparameterTuner:
    """Hyperparameter tuner for ML models."""
    
    def __init__(self, n_trials: int = 100, cv_folds: int = 5):
        """Initialize tuner."""
        self.n_trials = n_trials
        self.cv_folds = cv_folds
        self.best_params = {}
        
    def tune_xgboost(self, X: pd.DataFrame, y: pd.Series) -> Dict[str, Any]:
        """Tune XGBoost hyperparameters using Optuna."""
        
        def objective(trial):
            params = {
                'n_estimators': trial.suggest_int('n_estimators', 50, 500),
                'max_depth': trial.suggest_int('max_depth', 3, 10),
                'learning_rate': trial.suggest_float('learning_rate', 0.01, 0.3),
                'subsample': trial.suggest_float('subsample', 0.6, 1.0),
                'colsample_bytree': trial.suggest_float('colsample_bytree', 0.6, 1.0),
                'gamma': trial.suggest_float('gamma', 0, 5),
                'reg_alpha': trial.suggest_float('reg_alpha', 0, 10),
                'reg_lambda': trial.suggest_float('reg_lambda', 0, 10)
            }
            
            model = XGBoostModel(**params)
            metrics = model.train(X, y)
            
            return metrics['val_r2']
        
        study = optuna.create_study(direction='maximize', sampler=TPESampler(), pruner=MedianPruner())
        study.optimize(objective, n_trials=self.n_trials)
        
        self.best_params['xgboost'] = study.best_params
        
        return {
            'best_params': study.best_params,
            'best_score': study.best_value,
            'n_trials': len(study.trials)
        }
    
    def tune_random_forest(self, X: pd.DataFrame, y: pd.Series) -> Dict[str, Any]:
        """Tune Random Forest hyperparameters using GridSearch."""
        
        param_grid = {
            'n_estimators': [50, 100, 200, 300],
            'max_depth': [None, 10, 20, 30],
            'min_samples_split': [2, 5, 10],
            'min_samples_leaf': [1, 2, 4],
            'max_features': ['auto', 'sqrt', 'log2']
        }
        
        model = RandomForestModel()
        rf_model = model.model
        
        grid_search = GridSearchCV(
            rf_model, param_grid, 
            cv=self.cv_folds, 
            scoring='r2',
            n_jobs=-1,
            verbose=1
        )
        
        grid_search.fit(X, y)
        
        self.best_params['random_forest'] = grid_search.best_params_
        
        return {
            'best_params': grid_search.best_params_,
            'best_score': grid_search.best_score_,
            'cv_results': grid_search.cv_results_
        }
    
    def tune_svm(self, X: pd.DataFrame, y: pd.Series) -> Dict[str, Any]:
        """Tune SVM hyperparameters using RandomizedSearch."""
        
        param_dist = {
            'C': uniform(0.1, 100),
            'kernel': ['rbf', 'linear', 'poly'],
            'gamma': ['scale', 'auto'] + list(uniform(0.001, 1).rvs(10))
        }
        
        model = SVMModel()
        svm_model = model.model
        
        random_search = RandomizedSearchCV(
            svm_model, param_dist,
            n_iter=self.n_trials,
            cv=self.cv_folds,
            scoring='r2',
            n_jobs=-1,
            verbose=1,
            random_state=42
        )
        
        random_search.fit(X, y)
        
        self.best_params['svm'] = random_search.best_params_
        
        return {
            'best_params': random_search.best_params_,
            'best_score': random_search.best_score_,
            'n_trials': self.n_trials
        }
    
    def tune_knn(self, X: pd.DataFrame, y: pd.Series) -> Dict[str, Any]:
        """Tune KNN hyperparameters using GridSearch."""
        
        param_grid = {
            'n_neighbors': list(range(1, 31)),
            'weights': ['uniform', 'distance'],
            'algorithm': ['auto', 'ball_tree', 'kd_tree', 'brute'],
            'p': [1, 2]
        }
        
        model = KNNModel()
        knn_model = model.model
        
        grid_search = GridSearchCV(
            knn_model, param_grid,
            cv=self.cv_folds,
            scoring='r2',
            n_jobs=-1,
            verbose=1
        )
        
        grid_search.fit(X, y)
        
        self.best_params['knn'] = grid_search.best_params_
        
        return {
            'best_params': grid_search.best_params_,
            'best_score': grid_search.best_score_,
            'cv_results': grid_search.cv_results_
        }
    
    def get_best_params(self, model_name: str) -> Dict[str, Any]:
        """Get best parameters for a specific model."""
        return self.best_params.get(model_name, {})
    
    def tune_all_models(self, X: pd.DataFrame, y: pd.Series) -> Dict[str, Dict[str, Any]]:
        """Tune all available models."""
        results = {}
        
        print("Tuning XGBoost...")
        results['xgboost'] = self.tune_xgboost(X, y)
        
        print("Tuning Random Forest...")
        results['random_forest'] = self.tune_random_forest(X, y)
        
        print("Tuning SVM...")
        results['svm'] = self.tune_svm(X, y)
        
        print("Tuning KNN...")
        results['knn'] = self.tune_knn(X, y)
        
        return results

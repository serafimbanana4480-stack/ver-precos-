"""
ML configuration for AutoDeal IA Hunter.
"""
from pydantic import BaseModel
from typing import List, Optional


class MLConfig(BaseModel):
    """Configuration for ML settings."""
    
    enabled: bool = True
    
    # Model settings
    model_type: str = "xgboost"  # xgboost, lightgbm, catboost, ensemble
    model_version: str = "latest"
    model_path: str = "models/xgboost_model.pkl"
    
    # Training settings
    training_enabled: bool = True
    auto_retrain: bool = True
    retrain_interval_days: int = 7
    min_training_samples: int = 100
    
    # Feature engineering
    feature_engineering_enabled: bool = True
    feature_selection_enabled: bool = True
    feature_importance_threshold: float = 0.01
    
    # Hyperparameter tuning
    hyperparameter_tuning_enabled: bool = True
    tuning_method: str = "grid"  # grid, random, bayesian
    max_tuning_iterations: int = 100
    
    # Evaluation
    evaluation_enabled: bool = True
    cross_validation_folds: int = 5
    test_size: float = 0.2
    
    # Performance thresholds
    min_r2_score: float = 0.8
    max_mae_euros: int = 2000
    max_mape_percentage: float = 0.15
    
    # Model serving
    model_caching_enabled: bool = True
    batch_prediction_enabled: bool = True
    batch_size: int = 100
    
    # Monitoring
    model_drift_detection_enabled: bool = True
    drift_threshold: float = 0.1


ml_config = MLConfig()

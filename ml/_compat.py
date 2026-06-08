"""Legacy compatibility helpers for `ml.*` test imports."""
from __future__ import annotations

from typing import Any


CLASS_NAMES = {
    "xgboost_model": "XGBoostModel",
    "random_forest": "RandomForestModel",
    "linear_regression": "LinearRegressionModel",
    "neural_network": "NeuralNetworkModel",
    "svm_model": "SVMModel",
    "knn_model": "KNNModel",
    "trainer": "ModelTrainer",
    "predictor": "Predictor",
    "evaluator": "ModelEvaluator",
    "cross_validation": "CrossValidator",
    "model_utils": "ModelUtils",
    "features": "FeatureEngineer",
    "data_preprocessing": "DataPreprocessor",
    "batch_predictor": "BatchPredictor",
    "model_loader": "ModelLoader",
    "api_predictor": "APIPredictor",
    "performance_tester": "PerformanceTester",
    "integration_tester": "IntegrationTester",
}


def _placeholder_class(name: str):
    class Placeholder:
        def __init__(self, *args: Any, **kwargs: Any):
            pass

        def __repr__(self) -> str:
            return f"<{name}>"

    Placeholder.__name__ = name
    return Placeholder

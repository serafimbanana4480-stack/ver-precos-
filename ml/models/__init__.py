"""
ML models module.
"""

from .xgboost_model import XGBoostModel
from .random_forest import RandomForestModel
from .linear_regression import LinearRegressionModel
from .svm_model import SVMModel
from .knn_model import KNNModel

try:
    from .neural_network import NeuralNetworkModel
except ImportError:
    NeuralNetworkModel = None

__all__ = [
    'XGBoostModel',
    'RandomForestModel', 
    'LinearRegressionModel',
    'NeuralNetworkModel',
    'SVMModel',
    'KNNModel'
]

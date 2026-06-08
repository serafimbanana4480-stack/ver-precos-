"""
Valuation package initialization
"""
from .train_model import train_model
from .predict import estimate_market_value, calculate_deal_score
from .train_model_v3 import train_model_v3, model_passed_quality_gate
from .predict_v3 import (
    predict_price_v3,
    predict_price_v3_simple,
    predict_batch_v3,
    estimate_market_value_v3,
    get_model_status,
    clear_artifact_cache,
)

__all__ = [
    # Legacy v1
    "train_model",
    "estimate_market_value",
    "calculate_deal_score",
    # Production v3
    "train_model_v3",
    "model_passed_quality_gate",
    "predict_price_v3",
    "predict_price_v3_simple",
    "predict_batch_v3",
    "estimate_market_value_v3",
    "get_model_status",
    "clear_artifact_cache",
]

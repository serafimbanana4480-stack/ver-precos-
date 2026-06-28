"""
Valuation package initialization
"""
from .train import train_model, train_all_models
from .predict import PricePredictor, update_vehicle_valuations

# Backward-compatible aliases
estimate_market_value = lambda v: PricePredictor().predict(v)  # noqa: E731
calculate_deal_score = lambda v: {"deal_score": PricePredictor().predict(v) or 0}  # noqa: E731

__all__ = [
    "train_model",
    "train_all_models",
    "PricePredictor",
    "update_vehicle_valuations",
    "estimate_market_value",
    "calculate_deal_score",
]

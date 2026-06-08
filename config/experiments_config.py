"""
Experiments configuration for AutoDeal IA Hunter.
"""
from pydantic import BaseModel
from typing import Dict, Optional


class ExperimentConfig(BaseModel):
    """Configuration for A/B testing and experiments."""
    
    enabled: bool = False
    
    # Experiment tracking
    tracking_enabled: bool = True
    tracking_provider: str = "local"  # local, analytics, custom
    
    # Active experiments
    active_experiments: Dict[str, str] = {
        "deal_scoring_algorithm": "control",
        "scraper_strategy": "control",
        "ai_prompt_version": "control",
    }
    
    # Experiment variants
    deal_scoring_variants: Dict[str, str] = {
        "control": "standard",
        "variant_a": "enhanced",
        "variant_b": "experimental",
    }
    
    # Experiment duration
    default_experiment_days: int = 14
    min_sample_size: int = 100
    
    # Statistical significance
    significance_level: float = 0.05
    min_effect_size: float = 0.1


experiments_config = ExperimentConfig()

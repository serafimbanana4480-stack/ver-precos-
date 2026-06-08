"""
Validation configuration for AutoDeal IA Hunter.
"""
from pydantic import BaseModel
from typing import Dict, List


class ValidationConfig(BaseModel):
    """Configuration for validation settings."""
    
    enabled: bool = True
    strict_mode: bool = False
    
    # Data validation
    validate_required_fields: bool = True
    validate_data_types: bool = True
    validate_data_ranges: bool = True
    
    # Business validation
    validate_price_ranges: bool = True
    validate_year_ranges: bool = True
    validate_km_ranges: bool = True
    
    # Validation rules
    min_price_euros: int = 100
    max_price_euros: int = 500000
    min_year: int = 1990
    max_year: int = 2025
    min_km: int = 0
    max_km: int = 500000
    
    # Validation thresholds
    missing_data_threshold: float = 0.5
    invalid_data_threshold: float = 0.3
    
    # Custom validators
    validators: Dict[str, List[str]] = {
        "listing": ["required_fields", "price_range", "year_range"],
        "deal": ["profit_calculation", "score_threshold"],
        "vehicle": ["specifications", "condition"],
    }


validation_config = ValidationConfig()

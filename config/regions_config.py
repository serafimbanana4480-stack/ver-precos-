"""
Regions configuration for AutoDeal IA Hunter.
"""
from pydantic import BaseModel
from typing import Dict, List


class RegionConfig(BaseModel):
    """Configuration for regional settings."""
    
    enabled: bool = True
    
    # Default region
    default_region: str = "lisbon"
    default_country: str = "portugal"
    
    # Available regions
    regions: Dict[str, Dict[str, str]] = {
        "lisbon": {
            "name": "Lisboa",
            "country": "Portugal",
            "timezone": "Europe/Lisbon",
            "currency": "EUR",
        },
        "porto": {
            "name": "Porto",
            "country": "Portugal",
            "timezone": "Europe/Lisbon",
            "currency": "EUR",
        },
        "coimbra": {
            "name": "Coimbra",
            "country": "Portugal",
            "timezone": "Europe/Lisbon",
            "currency": "EUR",
        },
        "faro": {
            "name": "Faro",
            "country": "Portugal",
            "timezone": "Europe/Lisbon",
            "currency": "EUR",
        },
    }
    
    # Regional adjustments
    regional_price_adjustments: Dict[str, float] = {
        "lisbon": 1.0,
        "porto": 0.95,
        "coimbra": 0.9,
        "faro": 1.05,
    }
    
    # Regional scrapers
    regional_scrapers: Dict[str, List[str]] = {
        "lisbon": ["olx", "standvirtual", "autosapo"],
        "porto": ["olx", "standvirtual", "autosapo"],
        "coimbra": ["olx", "standvirtual"],
        "faro": ["olx", "standvirtual"],
    }


regions_config = RegionConfig()

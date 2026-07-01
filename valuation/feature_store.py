"""
Feature Store for vehicle pricing models.
Single source of truth for feature definitions (no training-serving skew).
Uses frequency-based dynamic brand encoding to handle any brand.
"""
from __future__ import annotations
import json
from collections import Counter
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Optional


LOCATION_PREMIUM: Dict[str, float] = {
    "lisboa": 1.15, "porto": 1.10, "faro": 1.05, "braga": 1.03,
    "coimbra": 1.02, "aveiro": 1.02, "setubal": 1.02, "leiria": 1.00,
    "santarem": 0.98, "viseu": 0.98, "evora": 0.97, "castelo branco": 0.96,
    "portalegre": 0.95, "braganca": 0.95, "vila real": 0.96,
    "viana do castelo": 0.98, "guarda": 0.95, "beja": 0.95,
}

DEPRECIATION_BY_AGE: Dict[int, float] = {
    0: 1.00, 1: 0.85, 2: 0.75, 3: 0.68, 4: 0.62, 5: 0.57,
    6: 0.53, 7: 0.49, 8: 0.46, 9: 0.43, 10: 0.40,
    11: 0.38, 12: 0.36, 13: 0.34, 14: 0.32, 15: 0.30,
    16: 0.29, 17: 0.28, 18: 0.27, 19: 0.26, 20: 0.25,
}

FUEL_MARKET_PREMIUM: Dict[str, float] = {
    "eletrico": 1.25, "hibrido": 1.12, "gasolina": 1.00,
    "gpl": 0.92, "diesel": 0.88, "gas natural": 0.90,
}

FUEL_ENCODE: Dict[str, int] = {
    "gasolina": 0, "diesel": 1, "eletrico": 2, "hibrido": 3, "gpl": 4,
}

TRANSMISSION_ENCODE: Dict[str, int] = {
    "manual": 0, "automatico": 1, "semi-automatico": 2,
}

DISTRICT_ENCODE: Dict[str, int] = {
    "lisboa": 0, "porto": 1, "braga": 2, "coimbra": 3, "aveiro": 4,
    "faro": 5, "setubal": 6, "leiria": 7, "santarem": 8, "viseu": 9,
    "evora": 10, "castelo branco": 11, "portalegre": 12, "braganca": 13,
    "vila real": 14, "viana do castelo": 15, "guarda": 16, "beja": 17,
}


class FeatureStore:
    """Provides feature computation used identically at train and inference time."""

    ALLOWED_FEATURES: List[str] = [
        "year", "km", "horsepower", "engine_size", "doors",
        "age", "km_per_year",
        "fuel_type", "transmission",
        "brand", "model", "district",
        "depreciation_factor", "fuel_premium", "location_premium",
    ]

    def __init__(self):
        self.brand_to_idx: Dict[str, int] = {}
        self.idx_to_brand: Dict[int, str] = {}
        self.model_to_idx: Dict[str, int] = {}
        self.idx_to_model: Dict[int, str] = {}

    def build_brand_index(self, brands: List[str]) -> None:
        counts = Counter(brands)
        sorted_brands = sorted(counts.keys(), key=lambda b: -counts[b])
        self.brand_to_idx = {b: i + 1 for i, b in enumerate(sorted_brands)}
        self.idx_to_brand = {v: k for k, v in self.brand_to_idx.items()}

    def build_model_index(self, models: List[str]) -> None:
        counts = Counter(models)
        sorted_models = sorted(counts.keys(), key=lambda m: -counts[m])
        self.model_to_idx = {m: i + 1 for i, m in enumerate(sorted_models)}
        self.idx_to_model = {v: k for k, v in self.model_to_idx.items()}

    def save_index(self, path: Path) -> None:
        data = {
            "brand_to_idx": self.brand_to_idx,
            "model_to_idx": self.model_to_idx,
        }
        path.write_text(json.dumps(data, indent=2), encoding="utf-8")

    def load_index(self, path: Path) -> None:
        if path.exists():
            data = json.loads(path.read_text(encoding="utf-8"))
            self.brand_to_idx = data.get("brand_to_idx", {})
            self.idx_to_brand = {v: k for k, v in self.brand_to_idx.items()}
            self.model_to_idx = data.get("model_to_idx", {})
            self.idx_to_model = {v: k for k, v in self.model_to_idx.items()}

    def compute_features(self, vehicle: dict) -> dict:
        features = {}
        features["year"] = float(vehicle.get("year", datetime.now().year - 5))
        features["km"] = float(vehicle.get("km", 0))
        features["horsepower"] = float(vehicle.get("horsepower", 0))
        features["engine_size"] = float(vehicle.get("engine_size", 0))
        features["doors"] = float(vehicle.get("doors", 4))
        age = max(datetime.now().year - features["year"], 0)
        features["age"] = float(age)
        features["km_per_year"] = features["km"] / max(age, 1)

        # --- Engineered features ---
        # Depreciation factor (0-1 scale, older = more depreciated)
        features["depreciation_factor"] = DEPRECIATION_BY_AGE.get(min(age, 20), 0.25)

        # Fuel market premium
        fuel = str(vehicle.get("fuel_type", "")).lower()
        fuel_premium = 1.0
        for key, prem in FUEL_MARKET_PREMIUM.items():
            if key in fuel:
                fuel_premium = prem
                break
        features["fuel_premium"] = fuel_premium

        # Location premium
        location = str(vehicle.get("district", vehicle.get("location", ""))).lower().strip()
        loc_premium = 1.0
        for key, prem in LOCATION_PREMIUM.items():
            if key in location:
                loc_premium = prem
                break
        features["location_premium"] = loc_premium

        # --- Categorical encodings ---
        fuel_idx = 0
        for key, idx in FUEL_ENCODE.items():
            if key in fuel:
                fuel_idx = idx
                break
        features["fuel_type"] = float(fuel_idx)

        trans = str(vehicle.get("transmission", "")).lower()
        trans_idx = 0
        for key, idx in TRANSMISSION_ENCODE.items():
            if key in trans:
                trans_idx = idx
                break
        features["transmission"] = float(trans_idx)

        brand = str(vehicle.get("brand", "Unknown")).strip()
        features["brand"] = float(self.brand_to_idx.get(brand, 0))

        # Model frequency encoding
        model = str(vehicle.get("model", "")).strip()
        features["model"] = float(self.model_to_idx.get(model, 0))

        district = str(vehicle.get("district", vehicle.get("location", ""))).lower().strip()
        d_idx = -1.0
        for key, val in DISTRICT_ENCODE.items():
            if key in district:
                d_idx = float(val)
                break
        features["district"] = d_idx

        return features

"""
Data Normalizers for Portuguese Input
Normalizes Portuguese text to match English enum values
"""
from __future__ import annotations
import re
import logging
from typing import Optional, Dict, Any
from enum import Enum

logger = logging.getLogger(__name__)


# Mapping dictionaries for Portuguese → English normalization
FUEL_TYPE_MAPPINGS: Dict[str, str] = {
    # Portuguese variants
    "híbrido": "hibrido",
    "híbrido plug-in": "hibrido",
    "hibrido plug-in": "hibrido",
    "elétrico": "eletrico",
    "eléctrico": "eletrico",
    "gás natural": "gas natural",
    "gas natural": "gas natural",
    "gpl": "gpl",
    "gás": "gpl",  # GPL is often just called "gás"
    
    # Already correct values (pass through)
    "gasolina": "gasolina",
    "diesel": "diesel",
    "eletrico": "eletrico",
    "hibrido": "hibrido",
    "gas natural": "gas natural",
    "gpl": "gpl",
}

TRANSMISSION_MAPPINGS: Dict[str, str] = {
    # Portuguese variants
    "automática": "automatico",
    "automático": "automatico",
    "manual": "manual",
    "semi-automática": "semi-automatico",
    "semi-automático": "semi-automatico",
    
    # Already correct values (pass through)
    "automatico": "automatico",
    "manual": "manual",
    "semi-automatico": "semi-automatico",
}

VEHICLE_TYPE_MAPPINGS: Dict[str, str] = {
    # Portuguese variants
    "carro": "carros",
    "carros": "carros",
    "automóvel": "carros",
    "automovel": "carros",
    "moto": "motos",
    "motociclo": "motos",
    "motocicleta": "motos",
    "motos": "motos",
}


def normalize_text(text: Optional[str]) -> Optional[str]:
    """
    Normalize text: lowercase, strip whitespace, remove accents
    """
    if not text or not isinstance(text, str):
        return None
    
    # Convert to lowercase
    text = text.lower().strip()
    
    # Remove accents
    # á → a, é → e, í → i, ó → o, ú → u, ã → a, õ → o, ç → c
    accents_map = {
        'á': 'a', 'à': 'a', 'ã': 'a', 'â': 'a',
        'é': 'e', 'è': 'e', 'ê': 'e',
        'í': 'i', 'ì': 'i',
        'ó': 'o', 'ò': 'o', 'õ': 'o', 'ô': 'o',
        'ú': 'u', 'ù': 'u',
        'ç': 'c',
    }
    
    for accented, normal in accents_map.items():
        text = text.replace(accented, normal)
    
    return text


def normalize_fuel_type(value: Optional[Any]) -> Optional[str]:
    """
    Normalize fuel type from Portuguese to English enum value
    
    Args:
        value: Raw fuel type value
        
    Returns:
        Normalized fuel type string or None if invalid
    """
    if value is None:
        return None
    
    # Convert to string and normalize
    normalized = normalize_text(str(value))
    if not normalized:
        return None
    
    # Look up in mappings
    mapped = FUEL_TYPE_MAPPINGS.get(normalized)
    if mapped:
        logger.debug(f"Normalized fuel type: {value} → {mapped}")
        return mapped
    
    # Try fuzzy matching for common variations
    if "hibrid" in normalized or "hybrid" in normalized:
        return "hibrido"
    elif "electr" in normalized:
        return "eletrico"
    elif "gas" in normalized and "natural" in normalized:
        return "gas natural"
    elif "gas" in normalized or "gpl" in normalized:
        return "gpl"
    elif "diesel" in normalized:
        return "diesel"
    elif "gasolina" in normalized:
        return "gasolina"
    
    logger.warning(f"Unknown fuel type: {value}, returning None")
    return None


def normalize_transmission(value: Optional[Any]) -> Optional[str]:
    """
    Normalize transmission from Portuguese to English enum value
    
    Args:
        value: Raw transmission value
        
    Returns:
        Normalized transmission string or None if invalid
    """
    if value is None:
        return None
    
    # Convert to string and normalize
    normalized = normalize_text(str(value))
    if not normalized:
        return None
    
    # Look up in mappings
    mapped = TRANSMISSION_MAPPINGS.get(normalized)
    if mapped:
        logger.debug(f"Normalized transmission: {value} → {mapped}")
        return mapped
    
    # Try fuzzy matching
    if "auto" in normalized and "semi" in normalized:
        return "semi-automatico"
    elif "auto" in normalized:
        return "automatico"
    elif "manual" in normalized:
        return "manual"
    
    logger.warning(f"Unknown transmission: {value}, returning None")
    return None


def normalize_vehicle_type(value: Optional[Any]) -> Optional[str]:
    """
    Normalize vehicle type from Portuguese to enum value
    
    Args:
        value: Raw vehicle type value
        
    Returns:
        Normalized vehicle type string or None if invalid
    """
    if value is None:
        return None
    
    # Convert to string and normalize
    normalized = normalize_text(str(value))
    if not normalized:
        return None
    
    # Look up in mappings
    mapped = VEHICLE_TYPE_MAPPINGS.get(normalized)
    if mapped:
        logger.debug(f"Normalized vehicle type: {value} → {mapped}")
        return mapped
    
    # Try fuzzy matching
    if "car" in normalized or "auto" in normalized:
        return "carros"
    elif "moto" in normalized:
        return "motos"
    
    logger.warning(f"Unknown vehicle type: {value}, returning None")
    return None


def normalize_seller_type(value: Optional[Any]) -> Optional[str]:
    """
    Normalize seller type
    """
    if value is None:
        return None
    
    normalized = normalize_text(str(value))
    if not normalized:
        return None
        
    if any(x in normalized for x in ('partic', 'indiv', 'priv')):
        return "particular"
    if any(x in normalized for x in ('prof', 'deal', 'stand', 'comerc')):
        return "profissional"
        
    return None


def normalize_vehicle_data(vehicle_data: Dict[str, Any]) -> Dict[str, Any]:
    """
    Normalize all relevant fields in vehicle data
    
    Args:
        vehicle_data: Raw vehicle data dictionary
        
    Returns:
        Vehicle data with normalized fields
    """
    normalized = vehicle_data.copy()
    
    # Normalize fuel_type
    if 'fuel_type' in normalized:
        normalized['fuel_type'] = normalize_fuel_type(normalized['fuel_type'])
    
    # Normalize transmission
    if 'transmission' in normalized:
        normalized['transmission'] = normalize_transmission(normalized['transmission'])
    
    # Normalize source for ScrapedVehicle schema (lowercase slugs)
    if normalized.get('source'):
        src = str(normalized['source']).strip().lower()
        source_aliases = {
            "olx": "olx",
            "standvirtual": "standvirtual",
            "autosapo": "autosapo",
            "auto sapo": "autosapo",
            "custojusto": "custojusto",
            "custo justo": "custojusto",
        }
        normalized['source'] = source_aliases.get(src, src)

    # Normalize vehicle_type
    if 'vehicle_type' in normalized:
        normalized['vehicle_type'] = normalize_vehicle_type(normalized['vehicle_type'])
    
    # Normalize seller_type
    if 'seller_type' in normalized:
        normalized['seller_type'] = normalize_seller_type(normalized['seller_type'])
    
    # Infer vehicle_type from title if missing
    if not normalized.get('vehicle_type') and normalized.get('title'):
        title = str(normalized['title']).lower()
        if 'moto' in title or 'motociclo' in title:
            normalized['vehicle_type'] = 'motos'
        elif 'carro' in title or 'automóvel' in title or 'automovel' in title:
            normalized['vehicle_type'] = 'carros'
        else:
            # Default to carros if unclear
            normalized['vehicle_type'] = 'carros'
    
    return normalized


def validate_enum_value(value: Optional[str], enum_class: Enum) -> bool:
    """
    Check if a value is valid for a given enum class
    
    Args:
        value: Value to check
        enum_class: Enum class to validate against
        
    Returns:
        True if valid, False otherwise
    """
    if not value:
        return False
    
    try:
        enum_class(value)
        return True
    except ValueError:
        return False

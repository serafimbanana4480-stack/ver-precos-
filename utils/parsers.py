"""
Unified parsing utilities for vehicle data extraction
"""
import re
import logging
from typing import Optional, Union

logger = logging.getLogger(__name__)

def parse_price(price_str: Optional[Union[str, float]]) -> Optional[float]:
    """
    Robustly parse price strings like '1.234,56 €', '1234.56', or 'Sob consulta'.
    
    Returns:
        float: The parsed price
        None: If unparseable or 'Sob consulta'
    """
    if price_str is None:
        return None
    if isinstance(price_str, (int, float)):
        return float(price_str)
    
    # Handle 'Sob consulta' or empty
    if not price_str or "consulta" in price_str.lower():
        return None
        
    try:
        # Remove currency symbols and spaces
        clean_str = re.sub(r'[€$£\s]', '', price_str)
        
        # Handle European format: dot as thousands separator, comma as decimal
        # 1.234,56 -> 1234.56
        if ',' in clean_str and '.' in clean_str:
            if clean_str.find('.') < clean_str.find(','):
                # Standard Euro: 1.234,56
                clean_str = clean_str.replace('.', '').replace(',', '.')
            else:
                # Reverse (unlikely but possible): 1,234.56
                clean_str = clean_str.replace(',', '')
        elif ',' in clean_str:
            # Check if it's a decimal comma or thousands separator
            # If comma is near the end (2 chars), it's likely decimal
            if len(clean_str.split(',')[-1]) <= 2:
                clean_str = clean_str.replace(',', '.')
            else:
                clean_str = clean_str.replace(',', '')
        elif '.' in clean_str:
            # Check if it's a thousands separator or decimal
            # In vehicle prices, dots are usually thousands separators if price is large
            parts = clean_str.split('.')
            if len(parts[-1]) != 2: # Not 123.45
                 clean_str = clean_str.replace('.', '')
                 
        return float(clean_str)
    except Exception as e:
        logger.warning(f"Failed to parse price '{price_str}': {e}")
        return None

def parse_km(km_str: Optional[Union[str, int]]) -> Optional[int]:
    """
    Parse mileage strings like '100 000 km', '10.000', or 'Novo'.
    """
    if km_str is None:
        return None
    if isinstance(km_str, int):
        return km_str
        
    if not km_str or "novo" in km_str.lower():
        return 0
        
    try:
        # Extract numerical part
        # Handles "100.000 km" -> "100.000"
        match = re.search(r'([\d\s\.\,]+)', km_str)
        if not match:
            return None
            
        clean_str = match.group(1).replace(' ', '').replace('.', '').replace(',', '')
        return int(clean_str)
    except Exception as e:
        logger.warning(f"Failed to parse KM '{km_str}': {e}")
        return None

def extract_year_km_from_string(text: str) -> tuple[Optional[int], Optional[int]]:
    """
    Handle concatenated strings like '2021 - 100.000 km' (common on OLX).
    """
    year = None
    km = None
    
    # Try to find a 4-digit year starting with 19 or 20
    year_match = re.search(r'\b(19\d{2}|20\d{2})\b', text)
    if year_match:
        year = int(year_match.group(1))
        
    # Try to find KM (string ending in km or typical large number)
    km = parse_km(text)
    
    return year, km

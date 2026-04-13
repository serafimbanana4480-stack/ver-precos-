"""
Helper functions for data formatting and calculations
"""
from datetime import datetime
from typing import Optional


def format_price(price: Optional[float], currency: str = "€") -> str:
    """
    Format price with currency and thousands separator
    
    Args:
        price: Price value
        currency: Currency symbol
    
    Returns:
        Formatted price string
    """
    if price is None:
        return "N/A"
    
    return f"{currency}{price:,.0f}"


def format_km(km: Optional[int]) -> str:
    """
    Format kilometers with thousands separator
    
    Args:
        km: Kilometer value
    
    Returns:
        Formatted km string
    """
    if km is None:
        return "N/A"
    
    return f"{km:,} km"


def calculate_age(year: Optional[int], current_year: Optional[int] = None) -> Optional[int]:
    """
    Calculate vehicle age
    
    Args:
        year: Vehicle year
        current_year: Current year (defaults to current year)
    
    Returns:
        Age in years or None
    """
    if year is None:
        return None
    
    if current_year is None:
        current_year = datetime.now().year
    
    age = current_year - year
    return max(0, age)


def calculate_km_per_year(km: Optional[int], year: Optional[int]) -> Optional[float]:
    """
    Calculate average km per year
    
    Args:
        km: Total kilometers
        year: Vehicle year
    
    Returns:
        Average km per year or None
    """
    if km is None or year is None:
        return None
    
    age = calculate_age(year)
    if age == 0:
        return None
    
    return round(km / age, 0)


def sanitize_filename(filename: str) -> str:
    """
    Sanitize filename by removing invalid characters
    
    Args:
        filename: Original filename
    
    Returns:
        Sanitized filename
    """
    invalid_chars = '<>:"/\\|?*'
    for char in invalid_chars:
        filename = filename.replace(char, '_')
    return filename


def truncate_text(text: str, max_length: int = 100, suffix: str = "...") -> str:
    """
    Truncate text to maximum length
    
    Args:
        text: Original text
        max_length: Maximum length
        suffix: Suffix to add if truncated
    
    Returns:
        Truncated text
    """
    if len(text) <= max_length:
        return text
    
    return text[:max_length - len(suffix)] + suffix


def parse_price(price_str: str) -> Optional[float]:
    """
    Parse price string to float
    
    Args:
        price_str: Price string (e.g., "15.000 €", "15000")
    
    Returns:
        Parsed price or None
    """
    if not price_str:
        return None
    
    # Remove currency symbols and spaces
    cleaned = price_str.replace('€', '').replace('$', '').replace(' ', '')
    
    # Handle Portuguese number format (1.500,00)
    if ',' in cleaned and '.' in cleaned:
        # Assume 1.500,00 format
        cleaned = cleaned.replace('.', '').replace(',', '.')
    elif ',' in cleaned:
        # Assume 1500,00 format
        cleaned = cleaned.replace(',', '.')
    elif '.' in cleaned:
        # Assume 1,500.00 or 1500.00 format
        # Remove thousands separators
        parts = cleaned.split('.')
        if len(parts) == 2 and len(parts[1]) == 2:
            # Assume 1500.00 format (decimal)
            pass
        else:
            # Assume 1.500 format (thousands)
            cleaned = cleaned.replace('.', '')
    
    try:
        return float(cleaned)
    except ValueError:
        return None


def calculate_deal_rating(deal_score: Optional[float]) -> str:
    """
    Convert deal score to rating text
    
    Args:
        deal_score: Deal score (0-10)
    
    Returns:
        Rating text
    """
    if deal_score is None:
        return "N/A"
    
    if deal_score >= 9.0:
        return "Excelente"
    elif deal_score >= 7.5:
        return "Muito Bom"
    elif deal_score >= 6.0:
        return "Bom"
    elif deal_score >= 4.0:
        return "Razoável"
    else:
        return "Fraco"


def get_vehicle_emoji(vehicle_type: str) -> str:
    """Get emoji for vehicle type"""
    emoji_map = {
        "car": "🚗",
        "carro": "🚗",
        "moto": "🏍️",
        "motorcycle": "🏍️"
    }
    return emoji_map.get(vehicle_type.lower(), "🚗")


def format_duration(seconds: float) -> str:
    """
    Format duration in seconds to human-readable string
    
    Args:
        seconds: Duration in seconds
    
    Returns:
        Formatted duration string
    """
    if seconds < 60:
        return f"{seconds:.1f}s"
    elif seconds < 3600:
        minutes = seconds / 60
        return f"{minutes:.1f}m"
    else:
        hours = seconds / 3600
        return f"{hours:.1f}h"

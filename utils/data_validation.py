"""
Comprehensive data validation utilities for scraped vehicle data
"""
from __future__ import annotations
import re
import logging
from typing import Optional, Dict, Any
from urllib.parse import urlparse
from datetime import datetime

logger = logging.getLogger(__name__)


class DataValidator:
    """Comprehensive data validation for scraped vehicle data"""
    
    # Valid URL patterns for Portuguese car sites
    VALID_URL_PATTERNS = [
        r'^https?://(www\.)?olx\.pt',
        r'^https?://(www\.)?standvirtual\.com',
        r'^https?://(www\.)?autos\.sapo\.pt',
    ]
    
    # Suspicious price indicators
    SUSPICIOUS_PRICE_INDICATORS = [
        'negociável', 'negociavel', 'sob consulta', 'a combinar',
        'contactar', 'preço', 'price', 'consultar'
    ]
    
    # Realistic price ranges for Portuguese market (EUR)
    PRICE_RANGES = {
        'car': {'min': 100, 'max': 500000},
        'moto': {'min': 50, 'max': 100000}
    }
    
    # Realistic year ranges
    YEAR_RANGE = {'min': 1980, 'max': datetime.now().year + 1}
    
    # Realistic KM ranges
    KM_RANGE = {'min': 0, 'max': 500000}
    
    @classmethod
    def validate_url(cls, url: Optional[str]) -> tuple[bool, Optional[str]]:
        """
        Validate vehicle listing URL
        
        Args:
            url: URL to validate
            
        Returns:
            Tuple of (is_valid, error_message)
        """
        if not url:
            return False, "URL is empty"
        
        if not isinstance(url, str):
            return False, f"URL must be string, got {type(url)}"
        
        # Check URL format
        try:
            parsed = urlparse(url)
            if not parsed.scheme or not parsed.netloc:
                return False, "Invalid URL format"
        except Exception as e:
            return False, f"URL parsing error: {e}"
        
        # Check if URL matches known patterns
        is_valid_pattern = any(
            re.match(pattern, url, re.IGNORECASE)
            for pattern in cls.VALID_URL_PATTERNS
        )
        
        if not is_valid_pattern:
            logger.warning(f"URL doesn't match known patterns: {url}")
            # Don't reject, just warn - might be new source
        
        return True, None
    
    @classmethod
    def validate_price(cls, price: Optional[Any], vehicle_type: str = 'car') -> tuple[bool, Optional[str]]:
        """
        Validate vehicle price
        
        Args:
            price: Price value to validate
            vehicle_type: Type of vehicle ('car' or 'moto')
            
        Returns:
            Tuple of (is_valid, error_message)
        """
        if price is None:
            return False, "Price is None"
        
        # Check if price is numeric
        try:
            price_float = float(price)
        except (ValueError, TypeError):
            return False, f"Price is not numeric: {price}"
        
        # Check price range
        range_key = vehicle_type.lower()
        price_range = cls.PRICE_RANGES.get(range_key, cls.PRICE_RANGES['car'])
        
        if price_float < price_range['min']:
            return False, f"Price below minimum ({price_range['min']}): {price_float}"
        
        if price_float > price_range['max']:
            return False, f"Price above maximum ({price_range['max']}): {price_float}"
        
        # Check for suspicious indicators if price is a string
        if isinstance(price, str):
            price_lower = price.lower()
            for indicator in cls.SUSPICIOUS_PRICE_INDICATORS:
                if indicator in price_lower:
                    logger.warning(f"Price contains suspicious indicator '{indicator}': {price}")
        
        return True, None
    
    @classmethod
    def validate_year(cls, year: Optional[Any]) -> tuple[bool, Optional[str]]:
        """
        Validate vehicle year
        
        Args:
            year: Year value to validate
            
        Returns:
            Tuple of (is_valid, error_message)
        """
        if year is None:
            return False, "Year is None"
        
        try:
            year_int = int(year)
        except (ValueError, TypeError):
            return False, f"Year is not integer: {year}"
        
        if year_int < cls.YEAR_RANGE['min']:
            return False, f"Year below minimum ({cls.YEAR_RANGE['min']}): {year_int}"
        
        if year_int > cls.YEAR_RANGE['max']:
            return False, f"Year above maximum ({cls.YEAR_RANGE['max']}): {year_int}"
        
        return True, None
    
    @classmethod
    def validate_km(cls, km: Optional[Any]) -> tuple[bool, Optional[str]]:
        """
        Validate vehicle kilometers
        
        Args:
            km: KM value to validate
            
        Returns:
            Tuple of (is_valid, error_message)
        """
        if km is None:
            # KM is optional, but if present should be valid
            return True, None
        
        try:
            km_int = int(km)
        except (ValueError, TypeError):
            return False, f"KM is not integer: {km}"
        
        if km_int < cls.KM_RANGE['min']:
            return False, f"KM below minimum ({cls.KM_RANGE['min']}): {km_int}"
        
        if km_int > cls.KM_RANGE['max']:
            return False, f"KM above maximum ({cls.KM_RANGE['max']}): {km_int}"
        
        return True, None
    
    @classmethod
    def validate_listing(cls, listing_data: Dict[str, Any]) -> Dict[str, Any]:
        """
        Validate a complete listing data dictionary
        
        Args:
            listing_data: Dictionary containing listing data
            
        Returns:
            Dictionary with validation results including:
            - is_valid: Overall validity
            - errors: List of error messages
            - warnings: List of warning messages
            - cleaned_data: Data with basic cleaning applied
        """
        errors = []
        warnings = []
        cleaned_data = listing_data.copy()
        
        # Validate URL (required)
        url = listing_data.get('url')
        url_valid, url_error = cls.validate_url(url)
        if not url_valid:
            errors.append(f"URL validation failed: {url_error}")
        
        # Validate price (required for DB)
        price = listing_data.get('price')
        vehicle_type = listing_data.get('vehicle_type', 'car')
        price_valid, price_error = cls.validate_price(price, vehicle_type)
        if not price_valid:
            errors.append(f"Price validation failed: {price_error}")
        
        # Validate year (required for DB)
        year = listing_data.get('year')
        year_valid, year_error = cls.validate_year(year)
        if not year_valid:
            errors.append(f"Year validation failed: {year_error}")
        
        # Validate KM (optional)
        km = listing_data.get('km')
        if km is not None:
            km_valid, km_error = cls.validate_km(km)
            if not km_valid:
                warnings.append(f"KM validation warning: {km_error}")
        
        # Basic data cleaning
        if 'title' in cleaned_data and isinstance(cleaned_data['title'], str):
            cleaned_data['title'] = cleaned_data['title'].strip()
        
        if 'location' in cleaned_data and isinstance(cleaned_data['location'], str):
            cleaned_data['location'] = cleaned_data['location'].strip()
        
        # Determine overall validity
        is_valid = len(errors) == 0
        
        return {
            'is_valid': is_valid,
            'errors': errors,
            'warnings': warnings,
            'cleaned_data': cleaned_data
        }
    
    @classmethod
    def sanitize_string(cls, value: Any, max_length: int = 500) -> str:
        """
        Sanitize string values for database storage
        
        Args:
            value: Value to sanitize
            max_length: Maximum allowed length
            
        Returns:
            Sanitized string
        """
        if value is None:
            return ""
        
        if not isinstance(value, str):
            value = str(value)
        
        # Remove null bytes and other problematic characters
        value = value.replace('\x00', '')
        
        # Trim whitespace
        value = value.strip()
        
        # Truncate if too long
        if len(value) > max_length:
            value = value[:max_length]
            logger.warning(f"String truncated to {max_length} characters")
        
        return value
    
    @classmethod
    def check_data_quality(cls, listing_data: Dict[str, Any]) -> Dict[str, Any]:
        """
        Check overall data quality of a listing
        
        Args:
            listing_data: Dictionary containing listing data
            
        Returns:
            Dictionary with quality metrics
        """
        quality_score = 0
        max_score = 10
        issues = []
        
        # Check for required fields
        required_fields = ['url', 'price', 'title', 'source']
        for field in required_fields:
            if not listing_data.get(field):
                issues.append(f"Missing required field: {field}")
                quality_score -= 2
        
        # Check for recommended fields
        recommended_fields = ['year', 'km', 'location', 'images']
        missing_recommended = [f for f in recommended_fields if not listing_data.get(f)]
        if missing_recommended:
            issues.append(f"Missing recommended fields: {', '.join(missing_recommended)}")
            quality_score -= 1
        
        # Check data completeness
        total_fields = len(listing_data)
        non_null_fields = sum(1 for v in listing_data.values() if v is not None and v != "")
        completeness = non_null_fields / max(total_fields, 1)
        
        if completeness < 0.5:
            issues.append(f"Low data completeness: {completeness:.0%}")
            quality_score -= 1
        
        # Normalize score
        quality_score = max(0, min(max_score, quality_score + max_score))
        
        return {
            'quality_score': quality_score,
            'max_score': max_score,
            'completeness': completeness,
            'issues': issues
        }


def validate_scraped_data(listing_data: Dict[str, Any]) -> tuple[bool, Optional[str]]:
    """
    Convenience function to validate scraped data
    
    Args:
        listing_data: Dictionary containing listing data
        
    Returns:
        Tuple of (is_valid, error_message)
    """
    result = DataValidator.validate_listing(listing_data)
    if not result['is_valid']:
        return False, '; '.join(result['errors'])
    return True, None

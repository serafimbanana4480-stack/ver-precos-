"""
Error Classification for Enhanced Error Handling
Classifies errors as transient (retryable) or permanent (non-retryable)
"""
from __future__ import annotations
import logging
from typing import Optional, Type
from enum import Enum

logger = logging.getLogger(__name__)


class ErrorType(Enum):
    """Classification of error types"""
    TRANSIENT_NETWORK = "transient_network"  # Network issues, timeouts
    TRANSIENT_RATE_LIMIT = "transient_rate_limit"  # Rate limiting, can retry
    PERMANENT_BLOCKED = "permanent_blocked"  # IP blocked, CAPTCHA required
    PERMANENT_NOT_FOUND = "permanent_not_found"  # 404, resource not found
    PERMANENT_AUTH = "permanent_auth"  # Authentication failure
    PERMANENT_PERMISSION = "permanent_permission"  # Permission denied
    UNKNOWN = "unknown"


class ErrorClassifier:
    """Classifies errors for appropriate handling"""
    
    # Transient error patterns
    TRANSIENT_PATTERNS = [
        'timeout',
        'connection',
        'network',
        'temporary',
        'rate limit',
        'too many requests',
        'service unavailable',
        '503',
        '502',
        '504',
    ]
    
    # Permanent error patterns
    PERMANENT_PATTERNS = [
        'blocked',
        'captcha',
        'access denied',
        'forbidden',
        '404',
        '403',
        '401',
        'unauthorized',
        'authentication',
    ]
    
    @classmethod
    def classify(cls, error: Exception) -> ErrorType:
        """
        Classify an error as transient or permanent
        
        Args:
            error: The exception to classify
            
        Returns:
            ErrorType classification
        """
        error_message = str(error).lower()
        error_type_name = type(error).__name__.lower()
        
        # Check for permanent errors first
        for pattern in cls.PERMANENT_PATTERNS:
            if pattern in error_message or pattern in error_type_name:
                if 'blocked' in pattern or 'captcha' in pattern:
                    return ErrorType.PERMANENT_BLOCKED
                elif '404' in pattern or 'not found' in pattern:
                    return ErrorType.PERMANENT_NOT_FOUND
                elif '401' in pattern or 'auth' in pattern:
                    return ErrorType.PERMANENT_AUTH
                elif '403' in pattern or 'permission' in pattern:
                    return ErrorType.PERMANENT_PERMISSION
                else:
                    return ErrorType.PERMANENT_BLOCKED
        
        # Check for transient errors
        for pattern in cls.TRANSIENT_PATTERNS:
            if pattern in error_message or pattern in error_type_name:
                if 'rate limit' in pattern or 'too many' in pattern:
                    return ErrorType.TRANSIENT_RATE_LIMIT
                else:
                    return ErrorType.TRANSIENT_NETWORK
        
        # Check specific exception types
        if cls._is_network_error(error):
            return ErrorType.TRANSIENT_NETWORK
        
        # Default to unknown
        logger.warning(f"Unable to classify error: {error} ({type(error).__name__})")
        return ErrorType.UNKNOWN
    
    @classmethod
    def is_transient(cls, error: Exception) -> bool:
        """
        Check if an error is transient (retryable)
        
        Args:
            error: The exception to check
            
        Returns:
            True if transient, False if permanent
        """
        error_type = cls.classify(error)
        return error_type in [ErrorType.TRANSIENT_NETWORK, ErrorType.TRANSIENT_RATE_LIMIT]
    
    @classmethod
    def is_permanent(cls, error: Exception) -> bool:
        """
        Check if an error is permanent (non-retryable)
        
        Args:
            error: The exception to check
            
        Returns:
            True if permanent, False if transient
        """
        error_type = cls.classify(error)
        return error_type in [
            ErrorType.PERMANENT_BLOCKED,
            ErrorType.PERMANENT_NOT_FOUND,
            ErrorType.PERMANENT_AUTH,
            ErrorType.PERMANENT_PERMISSION
        ]
    
    @classmethod
    def _is_network_error(cls, error: Exception) -> bool:
        """Check if error is a network-related error"""
        import httpx
        import requests
        
        network_error_types = (
            ConnectionError,
            TimeoutError,
            httpx.TimeoutException,
            httpx.ConnectError,
            httpx.ConnectTimeout,
            httpx.ReadTimeout,
        )
        
        if requests:
            network_error_types += (
                requests.exceptions.ConnectionError,
                requests.exceptions.Timeout,
            )
        
        return isinstance(error, network_error_types)
    
    @classmethod
    def detect_blocking_in_html(cls, html: str) -> bool:
        """
        Detect if the HTML content indicates the scraper is blocked
        
        Patterns:
        - Cloudflare Turnstile iframe
        - 'Access Denied' / '403 Forbidden' text
        - 'Houston, temos um problema' (OLX specific)
        - 'Challenge' or 'Checking your browser'
        - Additional OLX-specific blocking patterns
        """
        if not html:
            return False
            
        # Only definitive anti-bot indicators — avoid generic terms that appear in normal pages
        # (e.g. 'nginx', 'service unavailable', 'forbidden', 'server error', 'maintenance mode'
        #  all appear in normal site footers / error pages that are NOT bot-blocks)
        block_patterns = [
            'cf-challenge-running',
            'cf-ray',
            'turnstile',
            'access denied',
            '403 forbidden',
            'houston, temos um problema',
            'checking your browser',
            'verify you are a human',
            'security challenge',
            'just a moment...',
            'ddos protection',
            'challenge platform',
            'error 403',
            'you have been blocked',
            'blocked by cloudflare',
        ]
        
        html_lower = html.lower()
        for pattern in block_patterns:
            if pattern in html_lower:
                logger.warning(f"[BLOCK] Detected blocking pattern in HTML: {pattern}")
                return True
        
        # Check for extremely short HTML (likely blocked page)
        if len(html) < 500:
            logger.warning(f"[BLOCK] HTML too short ({len(html)} chars), likely blocked")
            return True
                
        return False

    @classmethod
    def get_retry_delay(cls, error: Exception, attempt: int) -> float:
        """
        Get recommended retry delay based on error type and attempt number
        
        Args:
            error: The exception that occurred
            attempt: Current attempt number (1-based)
            
        Returns:
            Delay in seconds
        """
        error_type = cls.classify(error)
        
        if error_type == ErrorType.TRANSIENT_RATE_LIMIT:
            # Exponential backoff for rate limiting
            return min(2 ** attempt, 60)  # Max 60 seconds
        elif error_type == ErrorType.TRANSIENT_NETWORK:
            # Shorter backoff for network errors
            return min(2 ** (attempt - 1), 30)  # Max 30 seconds
        else:
            # Default backoff
            return min(2 ** attempt, 30)

"""
Security middleware for API.
"""
import re
import hashlib
import hmac
from typing import Dict, Any, Optional, List
from fastapi import Request, HTTPException, status
from starlette.middleware.base import BaseHTTPMiddleware
import logging
from datetime import datetime, timedelta
from core.settings import settings

logger = logging.getLogger(__name__)


class SecurityMiddleware(BaseHTTPMiddleware):
    """Security middleware for API protection."""
    
    def __init__(self, app, security_config: Dict[str, Any] = None):
        """Initialize security middleware."""
        super().__init__(app)
        
        self.config = security_config or {}
        
        # Security settings
        self.enable_csrf_protection = self.config.get("enable_csrf", True)
        self.enable_security_headers = self.config.get("enable_security_headers", True)
        self.enable_input_validation = self.config.get("enable_input_validation", True)
        self.enable_rate_limit_enforcement = self.config.get("enable_rate_limit_enforcement", True)
        
        # CSRF settings
        self.csrf_token_timeout = self.config.get("csrf_token_timeout", 3600)  # 1 hour
        self.csrf_tokens = {}
        
        # Security headers
        self.security_headers = {
            "X-Content-Type-Options": "nosniff",
            "X-Frame-Options": "DENY",
            "X-XSS-Protection": "1; mode=block",
            "Strict-Transport-Security": "max-age=31536000; includeSubDomains",
            "Content-Security-Policy": "default-src 'self'; script-src 'self' 'unsafe-inline'; style-src 'self' 'unsafe-inline'",
            "Referrer-Policy": "strict-origin-when-cross-origin",
            "Permissions-Policy": "geolocation=(), microphone=(), camera=()"
        }
        
        # Input validation patterns
        self.dangerous_patterns = [
            r'<script[^>]*>.*?</script>',  # Script tags
            r'javascript:',                # JavaScript URLs
            r'on\w+\s*=',                 # Event handlers
            r'eval\s*\(',                 # eval() calls
            r'document\.',                # Document access
            r'window\.',                  # Window access
            r'<iframe[^>]*>',             # Iframes
            r'<object[^>]*>',             # Objects
            r'<embed[^>]*>',              # Embeds
            r'<link[^>]*>',               # Links
            r'<meta[^>]*>',               # Meta tags
        ]
        
        # Size limits
        self.max_request_size = self.config.get("max_request_size", 10 * 1024 * 1024)  # 10MB
        self.max_header_size = self.config.get("max_header_size", 8192)  # 8KB
        self.max_query_params = self.config.get("max_query_params", 50)
        
        # Blocked IPs
        self.blocked_ips = set(self.config.get("blocked_ips", []))
        self.trusted_ips = set(self.config.get("trusted_ips", []))
        
        logger.info("Security middleware initialized")
    
    async def dispatch(self, request: Request, call_next):
        """Process request with security checks."""
        
        try:
            # Get client IP
            client_ip = self._get_client_ip(request)
            
            # Check if IP is blocked
            if client_ip in self.blocked_ips:
                logger.warning(f"Blocked IP attempted access: {client_ip}")
                raise HTTPException(
                    status_code=status.HTTP_403_FORBIDDEN,
                    detail="Access denied"
                )
            
            # Validate request size
            await self._validate_request_size(request)
            
            # Validate headers
            self._validate_headers(request)
            
            # Validate query parameters
            self._validate_query_params(request)
            
            # CSRF protection for state-changing requests
            if self.enable_csrf_protection and request.method in ["POST", "PUT", "DELETE", "PATCH"]:
                await self._validate_csrf_token(request)
            
            # Input validation
            if self.enable_input_validation:
                await self._validate_input(request)
            
            # Process request
            response = await call_next(request)
            
            # Add security headers
            if self.enable_security_headers:
                self._add_security_headers(response)
            
            return response
            
        except HTTPException:
            raise
        except Exception as e:
            logger.error(f"Security middleware error (denying request): {e}")
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="Security check failed",
            )
    
    def _get_client_ip(self, request: Request) -> str:
        """Get client IP address."""
        
        # Check for forwarded IP
        forwarded_for = request.headers.get("X-Forwarded-For")
        if forwarded_for:
            return forwarded_for.split(",")[0].strip()
        
        # Check for real IP
        real_ip = request.headers.get("X-Real-IP")
        if real_ip:
            return real_ip
        
        # Fall back to client IP
        return request.client.host if request.client else "unknown"
    
    async def _validate_request_size(self, request: Request):
        """Validate request size."""
        
        content_length = request.headers.get("Content-Length")
        if content_length:
            try:
                size = int(content_length)
                if size > self.max_request_size:
                    logger.warning(f"Request too large: {size} bytes from {self._get_client_ip(request)}")
                    raise HTTPException(
                        status_code=status.HTTP_413_REQUEST_ENTITY_TOO_LARGE,
                        detail="Request entity too large"
                    )
            except ValueError:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail="Invalid Content-Length header"
                )
    
    def _validate_headers(self, request: Request):
        """Validate request headers."""
        
        for name, value in request.headers.items():
            # Check header size
            if len(value) > self.max_header_size:
                logger.warning(f"Header too large: {name} from {self._get_client_ip(request)}")
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail=f"Header '{name}' too large"
                )
            
            # Check for dangerous characters in headers
            if self._contains_dangerous_content(value):
                logger.warning(f"Dangerous content in header: {name} from {self._get_client_ip(request)}")
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail="Invalid header content"
                )
    
    def _validate_query_params(self, request: Request):
        """Validate query parameters."""
        
        if len(request.query_params) > self.max_query_params:
            logger.warning(f"Too many query parameters: {len(request.query_params)} from {self._get_client_ip(request)}")
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Too many query parameters"
            )
        
        for name, value in request.query_params.items():
            # Check for dangerous content
            if self._contains_dangerous_content(value):
                logger.warning(f"Dangerous content in query param: {name} from {self._get_client_ip(request)}")
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail="Invalid query parameter content"
                )
    
    async def _validate_csrf_token(self, request: Request):
        """Validate CSRF token for state-changing requests."""
        
        # Skip CSRF for API endpoints with token-based auth
        if self._is_api_request(request):
            return
        
        # Get CSRF token from header
        csrf_token = request.headers.get("X-CSRF-Token")
        
        if not csrf_token:
            # Try to get from form data (would need to parse body)
            logger.warning(f"Missing CSRF token from {self._get_client_ip(request)}")
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="CSRF token missing"
            )
        
        # Validate CSRF token
        if not self._validate_csrf_token_value(csrf_token, request):
            logger.warning(f"Invalid CSRF token from {self._get_client_ip(request)}")
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Invalid CSRF token"
            )
    
    def _is_api_request(self, request: Request) -> bool:
        """Check if request is for API endpoint."""
        
        return request.url.path.startswith("/api/") or request.headers.get("Authorization")
    
    def _validate_csrf_token_value(self, token: str, request: Request) -> bool:
        """Validate CSRF token value."""
        
        # In a real implementation, you would validate against session or database
        # For now, just check if token exists and is not expired
        
        client_ip = self._get_client_ip(request)
        token_key = f"{client_ip}:{hash(token)}"
        
        if token_key in self.csrf_tokens:
            token_data = self.csrf_tokens[token_key]
            if datetime.now().timestamp() < token_data['expires_at']:
                return True
            else:
                # Remove expired token
                del self.csrf_tokens[token_key]
        
        return False
    
    def generate_csrf_token(self, request: Request) -> str:
        """Generate CSRF token for client."""
        
        client_ip = self._get_client_ip(request)
        timestamp = datetime.now().timestamp()
        
        # Generate token using HMAC with secret from settings
        csrf_secret = settings.jwt_secret or "csrf-fallback-change-me"
        message = f"{client_ip}:{timestamp}"
        token = hmac.new(csrf_secret.encode(), message.encode(), hashlib.sha256).hexdigest()
        
        # Store token
        token_key = f"{client_ip}:{hash(token)}"
        self.csrf_tokens[token_key] = {
            'token': token,
            'created_at': timestamp,
            'expires_at': timestamp + self.csrf_token_timeout
        }
        
        return token
    
    async def _validate_input(self, request: Request):
        """Validate input for dangerous content."""
        
        # Validate URL path
        if self._contains_dangerous_content(request.url.path):
            logger.warning(f"Dangerous content in URL path: {request.url.path} from {self._get_client_ip(request)}")
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Invalid URL path"
            )
        
        # Validate query parameters (already done above)
        
        # For POST/PUT requests, would need to validate body
        # This is a simplified implementation
        
    def _contains_dangerous_content(self, content: str) -> bool:
        """Check if content contains dangerous patterns."""
        
        if not content:
            return False
        
        content_lower = content.lower()
        
        for pattern in self.dangerous_patterns:
            if re.search(pattern, content_lower, re.IGNORECASE | re.DOTALL):
                return True
        
        return False
    
    def _add_security_headers(self, response):
        """Add security headers to response."""
        
        for header, value in self.security_headers.items():
            response.headers[header] = value
        
        # Add custom security headers
        response.headers["X-API-Version"] = "1.0"
        response.headers["X-Content-Security-Policy"] = "active"
    
    def block_ip(self, ip: str):
        """Block an IP address."""
        
        self.blocked_ips.add(ip)
        logger.info(f"Blocked IP: {ip}")
    
    def unblock_ip(self, ip: str) -> bool:
        """Unblock an IP address."""
        
        if ip in self.blocked_ips:
            self.blocked_ips.remove(ip)
            logger.info(f"Unblocked IP: {ip}")
            return True
        
        return False
    
    def add_trusted_ip(self, ip: str):
        """Add trusted IP address."""
        
        self.trusted_ips.add(ip)
        logger.info(f"Added trusted IP: {ip}")
    
    def remove_trusted_ip(self, ip: str) -> bool:
        """Remove trusted IP address."""
        
        if ip in self.trusted_ips:
            self.trusted_ips.remove(ip)
            logger.info(f"Removed trusted IP: {ip}")
            return True
        
        return False
    
    def is_ip_blocked(self, ip: str) -> bool:
        """Check if IP is blocked."""
        
        return ip in self.blocked_ips
    
    def is_ip_trusted(self, ip: str) -> bool:
        """Check if IP is trusted."""
        
        return ip in self.trusted_ips
    
    def update_security_headers(self, headers: Dict[str, str]):
        """Update security headers."""
        
        self.security_headers.update(headers)
        logger.info("Security headers updated")
    
    def add_security_header(self, name: str, value: str):
        """Add a security header."""
        
        self.security_headers[name] = value
        logger.info(f"Added security header: {name}")
    
    def remove_security_header(self, name: str) -> bool:
        """Remove a security header."""
        
        if name in self.security_headers:
            del self.security_headers[name]
            logger.info(f"Removed security header: {name}")
            return True
        
        return False
    
    def add_dangerous_pattern(self, pattern: str):
        """Add a dangerous content pattern."""
        
        self.dangerous_patterns.append(pattern)
        logger.info(f"Added dangerous pattern: {pattern}")
    
    def remove_dangerous_pattern(self, pattern: str) -> bool:
        """Remove a dangerous content pattern."""
        
        if pattern in self.dangerous_patterns:
            self.dangerous_patterns.remove(pattern)
            logger.info(f"Removed dangerous pattern: {pattern}")
            return True
        
        return False
    
    def set_max_request_size(self, size: int):
        """Set maximum request size."""
        
        self.max_request_size = size
        logger.info(f"Max request size set to {size} bytes")
    
    def set_max_header_size(self, size: int):
        """Set maximum header size."""
        
        self.max_header_size = size
        logger.info(f"Max header size set to {size} bytes")
    
    def set_max_query_params(self, count: int):
        """Set maximum query parameters."""
        
        self.max_query_params = count
        logger.info(f"Max query params set to {count}")
    
    def cleanup_expired_csrf_tokens(self):
        """Clean up expired CSRF tokens."""
        
        current_time = datetime.now().timestamp()
        expired_tokens = []
        
        for token_key, token_data in self.csrf_tokens.items():
            if current_time >= token_data['expires_at']:
                expired_tokens.append(token_key)
        
        for token_key in expired_tokens:
            del self.csrf_tokens[token_key]
        
        logger.info(f"Cleaned up {len(expired_tokens)} expired CSRF tokens")
    
    def get_security_stats(self) -> Dict[str, Any]:
        """Get security statistics."""
        
        return {
            "blocked_ips": len(self.blocked_ips),
            "trusted_ips": len(self.trusted_ips),
            "csrf_tokens": len(self.csrf_tokens),
            "dangerous_patterns": len(self.dangerous_patterns),
            "security_headers": len(self.security_headers),
            "config": {
                "enable_csrf_protection": self.enable_csrf_protection,
                "enable_security_headers": self.enable_security_headers,
                "enable_input_validation": self.enable_input_validation,
                "max_request_size": self.max_request_size,
                "max_header_size": self.max_header_size,
                "max_query_params": self.max_query_params
            }
        }
    
    def export_security_config(self) -> Dict[str, Any]:
        """Export security configuration."""
        
        return {
            "config": self.config,
            "security_headers": self.security_headers,
            "dangerous_patterns": self.dangerous_patterns,
            "blocked_ips": list(self.blocked_ips),
            "trusted_ips": list(self.trusted_ips),
            "csrf_token_timeout": self.csrf_token_timeout,
            "max_request_size": self.max_request_size,
            "max_header_size": self.max_header_size,
            "max_query_params": self.max_query_params,
            "statistics": self.get_security_stats()
        }
    
    def import_security_config(self, config: Dict[str, Any]):
        """Import security configuration."""
        
        if "security_headers" in config:
            self.security_headers.update(config["security_headers"])
        
        if "dangerous_patterns" in config:
            self.dangerous_patterns = config["dangerous_patterns"]
        
        if "blocked_ips" in config:
            self.blocked_ips = set(config["blocked_ips"])
        
        if "trusted_ips" in config:
            self.trusted_ips = set(config["trusted_ips"])
        
        if "csrf_token_timeout" in config:
            self.csrf_token_timeout = config["csrf_token_timeout"]
        
        if "max_request_size" in config:
            self.max_request_size = config["max_request_size"]
        
        if "max_header_size" in config:
            self.max_header_size = config["max_header_size"]
        
        if "max_query_params" in config:
            self.max_query_params = config["max_query_params"]
        
        logger.info("Security configuration imported")
    
    def reset_security_config(self):
        """Reset security configuration to defaults."""
        
        self.blocked_ips.clear()
        self.trusted_ips.clear()
        self.csrf_tokens.clear()
        
        self.security_headers = {
            "X-Content-Type-Options": "nosniff",
            "X-Frame-Options": "DENY",
            "X-XSS-Protection": "1; mode=block",
            "Strict-Transport-Security": "max-age=31536000; includeSubDomains",
            "Content-Security-Policy": "default-src 'self'; script-src 'self' 'unsafe-inline'; style-src 'self' 'unsafe-inline'",
            "Referrer-Policy": "strict-origin-when-cross-origin",
            "Permissions-Policy": "geolocation=(), microphone=(), camera=()"
        }
        
        self.dangerous_patterns = [
            r'<script[^>]*>.*?</script>',
            r'javascript:',
            r'on\w+\s*=',
            r'eval\s*\(',
            r'document\.',
            r'window\.',
            r'<iframe[^>]*>',
            r'<object[^>]*>',
            r'<embed[^>]*>',
            r'<link[^>]*>',
            r'<meta[^>]*>',
        ]
        
        logger.info("Security configuration reset to defaults")


class InputSanitizer:
    """Input sanitizer for cleaning user input."""
    
    def __init__(self):
        """Initialize input sanitizer."""
        
        self.sanitization_rules = {
            'remove_html': True,
            'remove_scripts': True,
            'remove_styles': True,
            'escape_html': True,
            'normalize_whitespace': True,
            'max_length': 10000
        }
    
    def sanitize_input(self, input_str: str, input_type: str = "text") -> str:
        """Sanitize input string."""
        
        if not input_str:
            return ""
        
        sanitized = input_str
        
        # Remove HTML tags
        if self.sanitization_rules['remove_html']:
            sanitized = re.sub(r'<[^>]+>', '', sanitized)
        
        # Remove scripts specifically
        if self.sanitization_rules['remove_scripts']:
            sanitized = re.sub(r'<script[^>]*>.*?</script>', '', sanitized, flags=re.IGNORECASE | re.DOTALL)
            sanitized = re.sub(r'javascript:', '', sanitized, flags=re.IGNORECASE)
        
        # Remove styles
        if self.sanitization_rules['remove_styles']:
            sanitized = re.sub(r'<style[^>]*>.*?</style>', '', sanitized, flags=re.IGNORECASE | re.DOTALL)
            sanitized = re.sub(r'style\s*=\s*["\'][^"\']*["\']', '', sanitized, flags=re.IGNORECASE)
        
        # Escape HTML entities
        if self.sanitization_rules['escape_html']:
            sanitized = self._escape_html(sanitized)
        
        # Normalize whitespace
        if self.sanitization_rules['normalize_whitespace']:
            sanitized = re.sub(r'\s+', ' ', sanitized).strip()
        
        # Limit length
        if len(sanitized) > self.sanitization_rules['max_length']:
            sanitized = sanitized[:self.sanitization_rules['max_length']]
        
        return sanitized
    
    def _escape_html(self, text: str) -> str:
        """Escape HTML entities."""
        
        html_escape_table = {
            "&": "&amp;",
            '"': "&quot;",
            "'": "&#x27;",
            ">": "&gt;",
            "<": "&lt;",
        }
        
        return "".join(html_escape_table.get(c, c) for c in text)
    
    def sanitize_json(self, json_data: Dict[str, Any]) -> Dict[str, Any]:
        """Sanitize JSON data."""
        
        sanitized = {}
        
        for key, value in json_data.items():
            if isinstance(value, str):
                sanitized[key] = self.sanitize_input(value, "json_string")
            elif isinstance(value, dict):
                sanitized[key] = self.sanitize_json(value)
            elif isinstance(value, list):
                sanitized[key] = [self.sanitize_item(item) for item in value]
            else:
                sanitized[key] = value
        
        return sanitized
    
    def sanitize_item(self, item: Any) -> Any:
        """Sanitize individual item."""
        
        if isinstance(item, str):
            return self.sanitize_input(item)
        elif isinstance(item, dict):
            return self.sanitize_json(item)
        elif isinstance(item, list):
            return [self.sanitize_item(sub_item) for sub_item in item]
        else:
            return item
    
    def set_sanitization_rule(self, rule: str, value: bool):
        """Set sanitization rule."""
        
        if rule in self.sanitization_rules:
            self.sanitization_rules[rule] = value
        else:
            raise ValueError(f"Unknown sanitization rule: {rule}")
    
    def get_sanitization_rules(self) -> Dict[str, bool]:
        """Get current sanitization rules."""
        
        return self.sanitization_rules.copy()

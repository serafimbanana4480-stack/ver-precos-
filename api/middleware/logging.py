"""
Logging middleware for API.
"""
import time
import uuid
from typing import Dict, Any, Optional
from fastapi import Request, Response
from starlette.middleware.base import BaseHTTPMiddleware
import logging
import json

logger = logging.getLogger(__name__)


class LoggingMiddleware(BaseHTTPMiddleware):
    """Logging middleware for API requests and responses."""
    
    def __init__(self, app, log_level: str = "INFO"):
        """Initialize logging middleware."""
        super().__init__(app)
        self.log_level = getattr(logging, log_level.upper())
        self.request_start_times = {}
        
    async def dispatch(self, request: Request, call_next):
        """Process request and log details."""
        
        # Generate unique request ID
        request_id = str(uuid.uuid4())
        
        # Store request ID in state for other middleware/endpoints
        request.state.request_id = request_id
        
        # Record start time
        start_time = time.time()
        self.request_start_times[request_id] = start_time
        
        # Log request
        await self._log_request(request, request_id)
        
        try:
            # Process request
            response = await call_next(request)
            
            # Record end time
            end_time = time.time()
            duration = end_time - start_time
            
            # Log response
            await self._log_response(request, response, request_id, duration)
            
            # Add request ID to response headers
            response.headers["X-Request-ID"] = request_id
            response.headers["X-Response-Time"] = f"{duration:.3f}s"
            
            return response
            
        except Exception as e:
            # Log error
            end_time = time.time()
            duration = end_time - start_time
            
            await self._log_error(request, e, request_id, duration)
            
            # Re-raise the exception
            raise
        
        finally:
            # Clean up request start time
            if request_id in self.request_start_times:
                del self.request_start_times[request_id]
    
    async def _log_request(self, request: Request, request_id: str):
        """Log incoming request details."""
        
        try:
            # Get client IP
            client_ip = self._get_client_ip(request)
            
            # Get user agent
            user_agent = request.headers.get("User-Agent", "Unknown")
            
            # Get content length
            content_length = request.headers.get("Content-Length", "0")
            
            # Log request details
            log_data = {
                "request_id": request_id,
                "method": request.method,
                "url": str(request.url),
                "path": request.url.path,
                "query_params": dict(request.query_params),
                "client_ip": client_ip,
                "user_agent": user_agent,
                "content_length": content_length,
                "timestamp": time.time()
            }
            
            # Add user info if available
            if hasattr(request.state, 'user'):
                log_data["user_id"] = request.state.user.get('id')
                log_data["user_role"] = request.state.user.get('role')
            
            # Add API key info if available
            if hasattr(request.state, 'api_key'):
                log_data["api_key_id"] = request.state.api_key.get('id')
                log_data["api_key_name"] = request.state.api_key.get('name')
            
            logger.log(self.log_level, f"Request: {request.method} {request.url.path}", extra=log_data)
            
        except Exception as e:
            logger.error(f"Error logging request: {e}")
    
    async def _log_response(self, request: Request, response: Response, request_id: str, duration: float):
        """Log response details."""
        
        try:
            # Get response size
            response_size = len(response.body) if hasattr(response, 'body') else 0
            
            # Log response details
            log_data = {
                "request_id": request_id,
                "method": request.method,
                "url": str(request.url),
                "path": request.url.path,
                "status_code": response.status_code,
                "response_size": response_size,
                "duration_ms": duration * 1000,
                "timestamp": time.time()
            }
            
            # Add response headers (selective)
            important_headers = ["Content-Type", "Content-Length", "Cache-Control"]
            for header in important_headers:
                if header in response.headers:
                    log_data[f"response_{header.lower().replace('-', '_')}"] = response.headers[header]
            
            # Log with appropriate level based on status code
            if response.status_code >= 500:
                logger.error(f"Response: {response.status_code} {request.method} {request.url.path}", extra=log_data)
            elif response.status_code >= 400:
                logger.warning(f"Response: {response.status_code} {request.method} {request.url.path}", extra=log_data)
            else:
                logger.log(self.log_level, f"Response: {response.status_code} {request.method} {request.url.path}", extra=log_data)
            
        except Exception as e:
            logger.error(f"Error logging response: {e}")
    
    async def _log_error(self, request: Request, error: Exception, request_id: str, duration: float):
        """Log error details."""
        
        try:
            # Log error details
            log_data = {
                "request_id": request_id,
                "method": request.method,
                "url": str(request.url),
                "path": request.url.path,
                "error_type": type(error).__name__,
                "error_message": str(error),
                "duration_ms": duration * 1000,
                "timestamp": time.time()
            }
            
            # Add user info if available
            if hasattr(request.state, 'user'):
                log_data["user_id"] = request.state.user.get('id')
                log_data["user_role"] = request.state.user.get('role')
            
            logger.error(f"Error: {request.method} {request.url.path} - {type(error).__name__}: {error}", extra=log_data)
            
        except Exception as e:
            logger.error(f"Error logging error: {e}")
    
    def _get_client_ip(self, request: Request) -> str:
        """Get client IP address from request."""
        
        # Check for forwarded IP
        forwarded_for = request.headers.get("X-Forwarded-For")
        if forwarded_for:
            # Take the first IP in the list
            return forwarded_for.split(",")[0].strip()
        
        # Check for real IP
        real_ip = request.headers.get("X-Real-IP")
        if real_ip:
            return real_ip
        
        # Fall back to client IP
        return request.client.host if request.client else "Unknown"
    
    def get_request_duration(self, request_id: str) -> Optional[float]:
        """Get request duration by request ID."""
        
        if request_id in self.request_start_times:
            return time.time() - self.request_start_times[request_id]
        
        return None
    
    def get_active_requests_count(self) -> int:
        """Get number of active requests."""
        
        return len(self.request_start_times)
    
    def get_request_stats(self) -> Dict[str, Any]:
        """Get request statistics."""
        
        return {
            "active_requests": len(self.request_start_times),
            "total_requests_processed": getattr(self, 'total_requests', 0),
            "average_response_time": getattr(self, 'avg_response_time', 0)
        }
    
    def set_log_level(self, level: str):
        """Set logging level."""
        
        self.log_level = getattr(logging, level.upper())
        logger.info(f"Logging level set to {level}")


class StructuredLogger:
    """Structured logger for better log parsing."""
    
    def __init__(self, name: str = "api"):
        """Initialize structured logger."""
        self.logger = logging.getLogger(name)
        self.setup_logger()
    
    def setup_logger(self):
        """Setup logger with structured formatting."""
        
        # Create formatter
        formatter = logging.Formatter(
            '%(asctime)s - %(name)s - %(levelname)s - %(message)s'
        )
        
        # Create console handler
        console_handler = logging.StreamHandler()
        console_handler.setFormatter(formatter)
        
        # Add handler to logger
        self.logger.addHandler(console_handler)
        self.logger.setLevel(logging.INFO)
    
    def log_request(self, request_data: Dict[str, Any]):
        """Log request with structured data."""
        
        self.logger.info("API Request", extra={"event": "request", **request_data})
    
    def log_response(self, response_data: Dict[str, Any]):
        """Log response with structured data."""
        
        self.logger.info("API Response", extra={"event": "response", **response_data})
    
    def log_error(self, error_data: Dict[str, Any]):
        """Log error with structured data."""
        
        self.logger.error("API Error", extra={"event": "error", **error_data})
    
    def log_auth_event(self, auth_data: Dict[str, Any]):
        """Log authentication event."""
        
        self.logger.info("Auth Event", extra={"event": "auth", **auth_data})
    
    def log_business_event(self, event_data: Dict[str, Any]):
        """Log business event."""
        
        self.logger.info("Business Event", extra={"event": "business", **event_data})
    
    def log_security_event(self, security_data: Dict[str, Any]):
        """Log security event."""
        
        self.logger.warning("Security Event", extra={"event": "security", **security_data})
    
    def log_performance_event(self, performance_data: Dict[str, Any]):
        """Log performance event."""
        
        self.logger.info("Performance Event", extra={"event": "performance", **performance_data})


class AuditLogger:
    """Audit logger for compliance and security."""
    
    def __init__(self, log_file: str = "audit.log"):
        """Initialize audit logger."""
        self.logger = logging.getLogger("audit")
        self.setup_audit_logger(log_file)
    
    def setup_audit_logger(self, log_file: str):
        """Setup audit logger with file handler."""
        
        # Create file handler
        file_handler = logging.FileHandler(log_file)
        
        # Create formatter
        formatter = logging.Formatter(
            '%(asctime)s - %(name)s - %(levelname)s - %(message)s'
        )
        file_handler.setFormatter(formatter)
        
        # Add handler to logger
        self.logger.addHandler(file_handler)
        self.logger.setLevel(logging.INFO)
    
    def log_user_action(self, user_id: str, action: str, resource: str, details: Dict[str, Any] = None):
        """Log user action for audit."""
        
        audit_data = {
            "user_id": user_id,
            "action": action,
            "resource": resource,
            "timestamp": time.time(),
            "details": details or {}
        }
        
        self.logger.info(f"User Action: {action} on {resource} by user {user_id}", extra=audit_data)
    
    def log_admin_action(self, admin_id: str, action: str, target: str, details: Dict[str, Any] = None):
        """Log admin action for audit."""
        
        audit_data = {
            "admin_id": admin_id,
            "action": action,
            "target": target,
            "timestamp": time.time(),
            "details": details or {}
        }
        
        self.logger.info(f"Admin Action: {action} on {target} by admin {admin_id}", extra=audit_data)
    
    def log_data_access(self, user_id: str, data_type: str, record_id: str, action: str = "read"):
        """Log data access for audit."""
        
        audit_data = {
            "user_id": user_id,
            "data_type": data_type,
            "record_id": record_id,
            "action": action,
            "timestamp": time.time()
        }
        
        self.logger.info(f"Data Access: {action} {data_type} {record_id} by user {user_id}", extra=audit_data)
    
    def log_security_event(self, event_type: str, severity: str, details: Dict[str, Any]):
        """Log security event for audit."""
        
        audit_data = {
            "event_type": event_type,
            "severity": severity,
            "timestamp": time.time(),
            "details": details
        }
        
        self.logger.warning(f"Security Event: {event_type} - {severity}", extra=audit_data)
    
    def log_api_usage(self, user_id: str, endpoint: str, method: str, status_code: int, response_time: float):
        """Log API usage for audit."""
        
        audit_data = {
            "user_id": user_id,
            "endpoint": endpoint,
            "method": method,
            "status_code": status_code,
            "response_time": response_time,
            "timestamp": time.time()
        }
        
        self.logger.info(f"API Usage: {method} {endpoint} - {status_code} by user {user_id}", extra=audit_data)


class PerformanceLogger:
    """Performance logger for monitoring API performance."""
    
    def __init__(self, name: str = "performance"):
        """Initialize performance logger."""
        self.logger = logging.getLogger(name)
        self.setup_logger()
        self.slow_request_threshold = 1.0  # 1 second
        self.very_slow_request_threshold = 5.0  # 5 seconds
    
    def setup_logger(self):
        """Setup performance logger."""
        
        # Create formatter
        formatter = logging.Formatter(
            '%(asctime)s - %(name)s - %(levelname)s - %(message)s'
        )
        
        # Create console handler
        console_handler = logging.StreamHandler()
        console_handler.setFormatter(formatter)
        
        # Add handler to logger
        self.logger.addHandler(console_handler)
        self.logger.setLevel(logging.INFO)
    
    def log_request_performance(self, request_id: str, method: str, path: str, duration: float, status_code: int):
        """Log request performance."""
        
        perf_data = {
            "request_id": request_id,
            "method": method,
            "path": path,
            "duration": duration,
            "duration_ms": duration * 1000,
            "status_code": status_code,
            "timestamp": time.time()
        }
        
        # Determine log level based on performance
        if duration > self.very_slow_request_threshold:
            self.logger.error(f"Very Slow Request: {method} {path} - {duration:.3f}s", extra=perf_data)
        elif duration > self.slow_request_threshold:
            self.logger.warning(f"Slow Request: {method} {path} - {duration:.3f}s", extra=perf_data)
        else:
            self.logger.info(f"Request Performance: {method} {path} - {duration:.3f}s", extra=perf_data)
    
    def log_database_performance(self, operation: str, table: str, duration: float, records_affected: int = None):
        """Log database performance."""
        
        perf_data = {
            "operation": operation,
            "table": table,
            "duration": duration,
            "duration_ms": duration * 1000,
            "records_affected": records_affected,
            "timestamp": time.time()
        }
        
        if duration > 1.0:
            self.logger.warning(f"Slow Database Operation: {operation} on {table} - {duration:.3f}s", extra=perf_data)
        else:
            self.logger.info(f"Database Performance: {operation} on {table} - {duration:.3f}s", extra=perf_data)
    
    def log_cache_performance(self, operation: str, key: str, hit: bool, duration: float):
        """Log cache performance."""
        
        perf_data = {
            "operation": operation,
            "key": key,
            "hit": hit,
            "duration": duration,
            "duration_ms": duration * 1000,
            "timestamp": time.time()
        }
        
        self.logger.info(f"Cache Performance: {operation} {key} - {'HIT' if hit else 'MISS'} - {duration:.3f}s", extra=perf_data)
    
    def set_slow_request_threshold(self, threshold: float):
        """Set slow request threshold."""
        
        self.slow_request_threshold = threshold
        self.logger.info(f"Slow request threshold set to {threshold}s")
    
    def set_very_slow_request_threshold(self, threshold: float):
        """Set very slow request threshold."""
        
        self.very_slow_request_threshold = threshold
        self.logger.info(f"Very slow request threshold set to {threshold}s")


class SecurityLogger:
    """Security logger for security events."""
    
    def __init__(self, name: str = "security"):
        """Initialize security logger."""
        self.logger = logging.getLogger(name)
        self.setup_logger()
    
    def setup_logger(self):
        """Setup security logger."""
        
        # Create formatter
        formatter = logging.Formatter(
            '%(asctime)s - %(name)s - %(levelname)s - %(message)s'
        )
        
        # Create console handler
        console_handler = logging.StreamHandler()
        console_handler.setFormatter(formatter)
        
        # Add handler to logger
        self.logger.addHandler(console_handler)
        self.logger.setLevel(logging.WARNING)
    
    def log_authentication_attempt(self, username: str, success: bool, ip_address: str, user_agent: str):
        """Log authentication attempt."""
        
        security_data = {
            "event_type": "authentication_attempt",
            "username": username,
            "success": success,
            "ip_address": ip_address,
            "user_agent": user_agent,
            "timestamp": time.time()
        }
        
        if success:
            self.logger.info(f"Authentication Success: {username} from {ip_address}", extra=security_data)
        else:
            self.logger.warning(f"Authentication Failed: {username} from {ip_address}", extra=security_data)
    
    def log_authorization_failure(self, user_id: str, resource: str, action: str, ip_address: str):
        """Log authorization failure."""
        
        security_data = {
            "event_type": "authorization_failure",
            "user_id": user_id,
            "resource": resource,
            "action": action,
            "ip_address": ip_address,
            "timestamp": time.time()
        }
        
        self.logger.warning(f"Authorization Failed: User {user_id} attempted {action} on {resource}", extra=security_data)
    
    def log_suspicious_activity(self, activity_type: str, details: Dict[str, Any], severity: str = "medium"):
        """Log suspicious activity."""
        
        security_data = {
            "event_type": "suspicious_activity",
            "activity_type": activity_type,
            "severity": severity,
            "details": details,
            "timestamp": time.time()
        }
        
        if severity == "high":
            self.logger.error(f"Suspicious Activity: {activity_type} - HIGH SEVERITY", extra=security_data)
        else:
            self.logger.warning(f"Suspicious Activity: {activity_type} - {severity}", extra=security_data)
    
    def log_rate_limit_exceeded(self, ip_address: str, endpoint: str, limit: int, window: int):
        """Log rate limit exceeded."""
        
        security_data = {
            "event_type": "rate_limit_exceeded",
            "ip_address": ip_address,
            "endpoint": endpoint,
            "limit": limit,
            "window": window,
            "timestamp": time.time()
        }
        
        self.logger.warning(f"Rate Limit Exceeded: {ip_address} on {endpoint} (limit: {limit}/{window}s)", extra=security_data)
    
    def log_invalid_token(self, token: str, reason: str, ip_address: str):
        """Log invalid token usage."""
        
        security_data = {
            "event_type": "invalid_token",
            "token_hash": hash(token) % 1000000,  # Partial hash for logging
            "reason": reason,
            "ip_address": ip_address,
            "timestamp": time.time()
        }
        
        self.logger.warning(f"Invalid Token: {reason} from {ip_address}", extra=security_data)
    
    def log_data_breach_attempt(self, attempt_type: str, details: Dict[str, Any], ip_address: str):
        """Log data breach attempt."""
        
        security_data = {
            "event_type": "data_breach_attempt",
            "attempt_type": attempt_type,
            "details": details,
            "ip_address": ip_address,
            "timestamp": time.time()
        }
        
        self.logger.error(f"Data Breach Attempt: {attempt_type} from {ip_address}", extra=security_data)

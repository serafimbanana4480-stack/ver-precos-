"""
Authentication dependencies for API.
"""
from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from typing import Optional, Dict, Any
import logging

from core.settings import settings
from ..middleware.auth import AuthMiddleware

logger = logging.getLogger(__name__)

security = HTTPBearer(auto_error=False)

# Global auth middleware instance (secret from env/settings)
auth_middleware = AuthMiddleware(
    secret_key=settings.resolve_jwt_secret(),
    algorithm=settings.jwt_algorithm,
)


async def get_current_user(credentials: Optional[HTTPAuthorizationCredentials] = Depends(security)) -> Dict[str, Any]:
    """Get current authenticated user. Raises 401 if not authenticated."""
    
    if credentials is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Not authenticated",
            headers={"WWW-Authenticate": "Bearer"},
        )
    
    try:
        # Verify JWT token
        payload = auth_middleware.verify_token(credentials.credentials)
        
        # Validate user session
        if not auth_middleware.validate_user_session(payload):
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Invalid user session",
                headers={"WWW-Authenticate": "Bearer"},
            )
        
        return payload
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error getting current user: {e}")
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Could not validate credentials",
            headers={"WWW-Authenticate": "Bearer"},
        )


async def get_optional_user(credentials: Optional[HTTPAuthorizationCredentials] = Depends(security)) -> Optional[Dict[str, Any]]:
    """Get current user if authenticated, otherwise return None.
    Never raises on missing credentials (unlike get_current_user)."""
    
    if credentials is None:
        return None
    
    try:
        # Verify JWT token
        payload = auth_middleware.verify_token(credentials.credentials)
        return payload
        
    except Exception as e:
        logger.warning(f"Optional auth failed (non-fatal): {e}")
        return None
    
    try:
        # Verify JWT token
        payload = auth_middleware.verify_token(credentials.credentials)
        
        # Validate user session
        if not auth_middleware.validate_user_session(payload):
            return None
        
        return payload
        
    except Exception as e:
        logger.error(f"Error getting optional user: {e}")
        return None


async def require_admin(user: Dict[str, Any] = Depends(get_current_user)) -> Dict[str, Any]:
    """Require admin role."""
    
    if user.get('role') != 'admin':
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Admin access required"
        )
    
    return user


async def require_moderator(user: Dict[str, Any] = Depends(get_current_user)) -> Dict[str, Any]:
    """Require moderator role or higher."""
    
    if user.get('role') not in ['admin', 'moderator']:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Moderator access required"
        )
    
    return user


async def require_permission(permission: str):
    """Require specific permission."""
    
    def permission_checker(user: Dict[str, Any] = Depends(get_current_user)) -> Dict[str, Any]:
        if not auth_middleware.has_permission(user, permission):
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=f"Permission '{permission}' required"
            )
        return user
    
    return permission_checker


async def require_any_permission(permissions: list):
    """Require any of the specified permissions."""
    
    def permission_checker(user: Dict[str, Any] = Depends(get_current_user)) -> Dict[str, Any]:
        if not auth_middleware.has_any_permission(user, permissions):
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=f"One of these permissions required: {', '.join(permissions)}"
            )
        return user
    
    return permission_checker


async def require_all_permissions(permissions: list):
    """Require all of the specified permissions."""
    
    def permission_checker(user: Dict[str, Any] = Depends(get_current_user)) -> Dict[str, Any]:
        if not auth_middleware.has_all_permissions(user, permissions):
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=f"All these permissions required: {', '.join(permissions)}"
            )
        return user
    
    return permission_checker


async def get_api_key(api_key: str = Depends(security)) -> Dict[str, Any]:
    """Get API key information."""
    
    try:
        # Validate API key
        api_key_info = auth_middleware.validate_api_key(api_key)
        
        if not api_key_info:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Invalid API key"
            )
        
        return api_key_info
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error validating API key: {e}")
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Could not validate API key"
        )


async def require_api_key(api_key_info: Dict[str, Any] = Depends(get_api_key)) -> Dict[str, Any]:
    """Require valid API key."""
    
    return api_key_info


async def get_user_or_api_key(
    user: Optional[Dict[str, Any]] = Depends(get_optional_user),
    api_key_info: Optional[Dict[str, Any]] = Depends(get_api_key)
) -> Optional[Dict[str, Any]]:
    """Get user or API key information."""
    
    if user:
        return user
    elif api_key_info:
        return api_key_info
    else:
        return None


async def require_authentication(
    auth_info: Optional[Dict[str, Any]] = Depends(get_user_or_api_key)
) -> Dict[str, Any]:
    """Require either user authentication or API key."""
    
    if not auth_info:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Authentication required"
        )
    
    return auth_info


def create_access_token(data: dict, expires_delta: Optional[int] = None) -> str:
    """Create access token."""
    
    return auth_middleware.create_access_token(data, expires_delta)


def create_refresh_token(data: dict, expires_delta: Optional[int] = None) -> str:
    """Create refresh token."""
    
    return auth_middleware.create_refresh_token(data, expires_delta)


def verify_token(token: str) -> dict:
    """Verify JWT token."""
    
    return auth_middleware.verify_token(token)


def revoke_token(token: str) -> bool:
    """Revoke JWT token."""
    
    return auth_middleware.revoke_token(token)


def hash_password(password: str) -> str:
    """Hash password."""
    
    return auth_middleware.hash_password(password)


def verify_password(plain_password: str, hashed_password: str) -> bool:
    """Verify password."""
    
    return auth_middleware.verify_password(plain_password, hashed_password)


def create_password_reset_token(user_id: str, email: str, expires_hours: int = 1) -> str:
    """Create password reset token."""
    
    return auth_middleware.create_password_reset_token(user_id, email, expires_hours)


def validate_password_reset_token(token: str) -> Optional[dict]:
    """Validate password reset token."""
    
    return auth_middleware.validate_password_reset_token(token)


def create_email_verification_token(user_id: str, email: str, expires_hours: int = 24) -> str:
    """Create email verification token."""
    
    return auth_middleware.create_email_verification_token(user_id, email, expires_hours)


def validate_email_verification_token(token: str) -> Optional[dict]:
    """Validate email verification token."""
    
    return auth_middleware.validate_email_verification_token(token)


def refresh_access_token(refresh_token: str) -> Optional[str]:
    """Refresh access token."""
    
    return auth_middleware.refresh_access_token(refresh_token)


def get_token_info(token: str) -> dict:
    """Get token information."""
    
    return auth_middleware.get_token_info(token)


def is_token_expired(token: str) -> bool:
    """Check if token is expired."""
    
    return auth_middleware.is_token_expired(token)


def cleanup_expired_tokens() -> int:
    """Clean up expired tokens."""
    
    return auth_middleware.cleanup_expired_tokens()


def get_token_stats() -> dict:
    """Get token statistics."""
    
    return auth_middleware.get_token_stats()


def create_api_key_for_user(user_id: str, name: str, permissions: list, expires_days: int = None) -> dict:
    """Create API key for user."""
    
    return auth_middleware.create_api_key(user_id, name, permissions, expires_days)


def validate_api_key(api_key: str) -> Optional[dict]:
    """Validate API key."""
    
    return auth_middleware.validate_api_key(api_key)


def create_session_token(user_data: dict, expires_delta: Optional[int] = None) -> str:
    """Create session token."""
    
    return auth_middleware.create_session_token(user_data, expires_delta)


def validate_session_token(session_token: str) -> Optional[dict]:
    """Validate session token."""
    
    return auth_middleware.validate_session_token(session_token)


def update_session_activity(session_token: str) -> bool:
    """Update session activity."""
    
    return auth_middleware.update_session_activity(session_token)


def revoke_session(session_token: str) -> bool:
    """Revoke session token."""
    
    return auth_middleware.revoke_session(session_token)


def get_user_from_token(token: str) -> Optional[dict]:
    """Get user information from token."""
    
    return auth_middleware.get_user_from_token(token)


def is_admin(user: dict) -> bool:
    """Check if user is admin."""
    
    return auth_middleware.is_admin(user)


def is_moderator(user: dict) -> bool:
    """Check if user is moderator."""
    
    return auth_middleware.is_moderator(user)


def has_user_permission(user: dict, permission: str) -> bool:
    """Check if user has specific permission."""
    
    return auth_middleware.has_permission(user, permission)


def has_user_any_permission(user: dict, permissions: list) -> bool:
    """Check if user has any of the specified permissions."""
    
    return auth_middleware.has_any_permission(user, permissions)


def has_user_all_permissions(user: dict, permissions: list) -> bool:
    """Check if user has all of the specified permissions."""
    
    return auth_middleware.has_all_permissions(user, permissions)


def get_user_permissions(user: dict) -> list:
    """Get user permissions."""
    
    return auth_middleware.get_user_permissions(user)


def add_user_permission(user: dict, permission: str) -> bool:
    """Add permission to user (for current session only)."""
    
    return auth_middleware.add_user_permission(user, permission)


def remove_user_permission(user: dict, permission: str) -> bool:
    """Remove permission from user (for current session only)."""
    
    return auth_middleware.remove_user_permission(user, permission)

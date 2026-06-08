"""
Authentication middleware.
"""
import jwt
import bcrypt
from datetime import datetime, timedelta
from typing import Optional, Dict, Any, List
from fastapi import HTTPException, Request, status
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
import logging

logger = logging.getLogger(__name__)

security = HTTPBearer()

class AuthMiddleware:
    """Authentication middleware for API."""
    
    def __init__(self, secret_key: str, algorithm: str = "HS256"):
        """Initialize auth middleware."""
        self.secret_key = secret_key
        self.algorithm = algorithm
        self.token_blacklist = set()
        
    def create_access_token(self, data: Dict[str, Any], expires_delta: Optional[timedelta] = None) -> str:
        """Create JWT access token."""
        
        to_encode = data.copy()
        
        if expires_delta:
            expire = datetime.utcnow() + expires_delta
        else:
            expire = datetime.utcnow() + timedelta(minutes=15)
        
        to_encode.update({"exp": expire})
        encoded_jwt = jwt.encode(to_encode, self.secret_key, algorithm=self.algorithm)
        
        return encoded_jwt
    
    def create_refresh_token(self, data: Dict[str, Any], expires_delta: Optional[timedelta] = None) -> str:
        """Create JWT refresh token."""
        
        to_encode = data.copy()
        
        if expires_delta:
            expire = datetime.utcnow() + expires_delta
        else:
            expire = datetime.utcnow() + timedelta(days=30)
        
        to_encode.update({"exp": expire})
        encoded_jwt = jwt.encode(to_encode, self.secret_key, algorithm=self.algorithm)
        
        return encoded_jwt
    
    def verify_token(self, token: str) -> Dict[str, Any]:
        """Verify JWT token."""
        
        try:
            # Check if token is blacklisted
            if token in self.token_blacklist:
                raise HTTPException(
                    status_code=status.HTTP_401_UNAUTHORIZED,
                    detail="Token has been revoked",
                    headers={"WWW-Authenticate": "Bearer"},
                )
            
            payload = jwt.decode(token, self.secret_key, algorithms=[self.algorithm])
            return payload
            
        except jwt.ExpiredSignatureError:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Token expired",
                headers={"WWW-Authenticate": "Bearer"},
            )
        except jwt.JWTError:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Invalid token",
                headers={"WWW-Authenticate": "Bearer"},
            )
    
    def revoke_token(self, token: str) -> bool:
        """Revoke a token by adding it to blacklist."""
        
        try:
            # Verify token is valid before blacklisting
            jwt.decode(token, self.secret_key, algorithms=[self.algorithm])
            self.token_blacklist.add(token)
            return True
        except jwt.JWTError:
            return False
    
    def hash_password(self, password: str) -> str:
        """Hash password using bcrypt."""
        
        salt = bcrypt.gensalt()
        hashed_password = bcrypt.hashpw(password.encode('utf-8'), salt)
        return hashed_password.decode('utf-8')
    
    def verify_password(self, plain_password: str, hashed_password: str) -> bool:
        """Verify password against hash."""
        
        try:
            return bcrypt.checkpw(plain_password.encode('utf-8'), hashed_password.encode('utf-8'))
        except:
            return False
    
    def get_current_user(self, request: Request) -> Optional[Dict[str, Any]]:
        """Get current user from request."""
        
        # Try to get user from request state (set by dependency)
        if hasattr(request.state, 'user'):
            return request.state.user
        
        # Try to get from Authorization header
        authorization = request.headers.get("Authorization")
        if not authorization:
            return None
        
        try:
            scheme, token = authorization.split(" ")
            if scheme.lower() != "bearer":
                return None
            
            payload = self.verify_token(token)
            return payload
            
        except Exception:
            return None
    
    def require_auth(self, request: Request) -> Dict[str, Any]:
        """Require authentication."""
        
        user = self.get_current_user(request)
        if not user:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Not authenticated",
                headers={"WWW-Authenticate": "Bearer"},
            )
        
        return user
    
    def require_role(self, required_role: str):
        """Decorator to require specific role."""
        
        def decorator(func):
            def wrapper(request: Request, *args, **kwargs):
                user = self.require_auth(request)
                
                if user.get('role') != required_role:
                    raise HTTPException(
                        status_code=status.HTTP_403_FORBIDDEN,
                        detail=f"Access denied. Required role: {required_role}",
                    )
                
                return func(request, *args, **kwargs)
            return wrapper
        return decorator
    
    def require_permission(self, permission: str):
        """Decorator to require specific permission."""
        
        def decorator(func):
            def wrapper(request: Request, *args, **kwargs):
                user = self.require_auth(request)
                
                user_permissions = user.get('permissions', [])
                if permission not in user_permissions:
                    raise HTTPException(
                        status_code=status.HTTP_403_FORBIDDEN,
                        detail=f"Access denied. Required permission: {permission}",
                    )
                
                return func(request, *args, **kwargs)
            return wrapper
        return decorator
    
    def create_user_session(self, user_data: Dict[str, Any]) -> Dict[str, Any]:
        """Create user session data."""
        
        session_data = {
            'id': user_data.get('id'),
            'email': user_data.get('email'),
            'role': user_data.get('role', 'user'),
            'permissions': user_data.get('permissions', []),
            'created_at': datetime.utcnow().isoformat(),
            'last_login': datetime.utcnow().isoformat()
        }
        
        return session_data
    
    def is_token_expired(self, token: str) -> bool:
        """Check if token is expired."""
        
        try:
            payload = jwt.decode(token, self.secret_key, algorithms=[self.algorithm])
            return False
        except jwt.ExpiredSignatureError:
            return True
        except jwt.JWTError:
            return True
    
    def refresh_access_token(self, refresh_token: str) -> Optional[str]:
        """Refresh access token using refresh token."""
        
        try:
            payload = jwt.decode(refresh_token, self.secret_key, algorithms=[self.algorithm])
            
            # Create new access token
            user_data = {
                'id': payload.get('id'),
                'email': payload.get('email'),
                'role': payload.get('role'),
                'permissions': payload.get('permissions', [])
            }
            
            new_token = self.create_access_token(user_data)
            return new_token
            
        except jwt.JWTError:
            return None
    
    def get_token_info(self, token: str) -> Dict[str, Any]:
        """Get token information."""
        
        try:
            payload = jwt.decode(token, self.secret_key, algorithms=[self.algorithm])
            
            return {
                'user_id': payload.get('sub'),
                'email': payload.get('email'),
                'role': payload.get('role'),
                'permissions': payload.get('permissions', []),
                'issued_at': datetime.fromtimestamp(payload.get('iat', 0)),
                'expires_at': datetime.fromtimestamp(payload.get('exp', 0)),
                'token_type': payload.get('type', 'access')
            }
            
        except jwt.JWTError:
            return {}
    
    def validate_user_session(self, user_data: Dict[str, Any]) -> bool:
        """Validate user session data."""
        
        required_fields = ['id', 'email', 'role']
        
        for field in required_fields:
            if field not in user_data or not user_data[field]:
                return False
        
        # Validate role
        valid_roles = ['admin', 'moderator', 'user']
        if user_data['role'] not in valid_roles:
            return False
        
        return True
    
    def update_user_session(self, user_data: Dict[str, Any], updates: Dict[str, Any]) -> Dict[str, Any]:
        """Update user session data."""
        
        updated_session = user_data.copy()
        updated_session.update(updates)
        updated_session['last_login'] = datetime.utcnow().isoformat()
        
        return updated_session
    
    def cleanup_expired_tokens(self) -> int:
        """Clean up expired tokens from blacklist."""
        
        current_time = datetime.utcnow()
        expired_tokens = []
        
        for token in self.token_blacklist:
            if self.is_token_expired(token):
                expired_tokens.append(token)
        
        for token in expired_tokens:
            self.token_blacklist.remove(token)
        
        return len(expired_tokens)
    
    def get_blacklisted_tokens(self) -> List[str]:
        """Get list of blacklisted tokens."""
        
        return list(self.token_blacklist)
    
    def clear_blacklist(self) -> int:
        """Clear all blacklisted tokens."""
        
        count = len(self.token_blacklist)
        self.token_blacklist.clear()
        return count
    
    def get_token_stats(self) -> Dict[str, Any]:
        """Get token statistics."""
        
        return {
            'blacklisted_tokens': len(self.token_blacklist),
            'blacklisted_token_count': len(self.token_blacklist),
            'algorithm': self.algorithm,
            'token_blacklist': list(self.token_blacklist)  # For debugging
        }
    
    def create_api_key(self, user_id: str, name: str, permissions: List[str], expires_days: int = None) -> Dict[str, Any]:
        """Create API key for user."""
        
        api_key_data = {
            'id': user_id,
            'name': name,
            'permissions': permissions,
            'type': 'api_key',
            'created_at': datetime.utcnow().isoformat()
        }
        
        if expires_days:
            api_key_data['expires_at'] = (datetime.utcnow() + timedelta(days=expires_days)).isoformat()
        
        api_key = self.create_access_token(api_key_data)
        
        return {
            'api_key': api_key,
            'name': name,
            'permissions': permissions,
            'expires_at': api_key_data.get('expires_at'),
            'created_at': api_key_data['created_at']
        }
    
    def validate_api_key(self, api_key: str) -> Optional[Dict[str, Any]]:
        """Validate API key and return user info."""
        
        try:
            payload = self.verify_token(api_key)
            
            if payload.get('type') != 'api_key':
                return None
            
            return {
                'user_id': payload.get('id'),
                'name': payload.get('name'),
                'permissions': payload.get('permissions', []),
                'expires_at': payload.get('expires_at')
            }
            
        except Exception:
            return None
    
    def create_session_token(self, user_data: Dict[str, Any], expires_delta: Optional[timedelta] = None) -> str:
        """Create session token for web sessions."""
        
        session_data = {
            'id': user_data.get('id'),
            'email': user_data.get('email'),
            'role': user_data.get('role', 'user'),
            'type': 'session',
            'created_at': datetime.utcnow().isoformat(),
            'last_activity': datetime.utcnow().isoformat()
        }
        
        if expires_delta:
            session_data['expires_at'] = (datetime.utcnow() + expires_delta).isoformat()
        
        return self.create_access_token(session_data)
    
    def validate_session_token(self, session_token: str) -> Optional[Dict[str, Any]]:
        """Validate session token and update last activity."""
        
        try:
            payload = self.verify_token(session_token)
            
            if payload.get('type') != 'session':
                return None
            
            # Check if session is expired
            if 'expires_at' in payload:
                expires_at = datetime.fromisoformat(payload['expires_at'])
                if datetime.utcnow() > expires_at:
                    return None
            
            return {
                'user_id': payload.get('id'),
                'email': payload.get('email'),
                'role': payload.get('role', 'user'),
                'last_activity': payload.get('last_activity'),
                'expires_at': payload.get('expires_at')
            }
            
        except Exception:
            return None
    
    def update_session_activity(self, session_token: str) -> bool:
        """Update session activity timestamp."""
        
        try:
            payload = jwt.decode(session_token, self.secret_key, algorithms=[self.algorithm])
            
            if payload.get('type') != 'session':
                return False
            
            # Create new token with updated activity
            updated_data = {
                'id': payload.get('id'),
                'email': payload.get('email'),
                'role': payload.get('role'),
                'type': 'session',
                'created_at': payload.get('created_at'),
                'last_activity': datetime.utcnow().isoformat(),
                'expires_at': payload.get('expires_at')
            }
            
            # Note: In a real implementation, you'd store this new token
            # and return it to the client
            
            return True
            
        except Exception:
            return False
    
    def revoke_session(self, session_token: str) -> bool:
        """Revoke session token."""
        
        return self.revoke_token(session_token)
    
    def get_user_from_token(self, token: str) -> Optional[Dict[str, Any]]:
        """Get user information from token."""
        
        try:
            payload = self.verify_token(token)
            
            return {
                'id': payload.get('id'),
                'email': payload.get('email'),
                'role': payload.get('role', 'user'),
                'permissions': payload.get('permissions', []),
                'token_type': payload.get('type', 'access')
            }
            
        except Exception:
            return None
    
    def is_admin(self, user: Dict[str, Any]) -> bool:
        """Check if user is admin."""
        
        return user.get('role') == 'admin'
    
    def is_moderator(self, user: Dict[str, Any]) -> bool:
        """Check if user is moderator."""
        
        return user.get('role') == 'moderator'
    
    def has_permission(self, user: Dict[str, Any], permission: str) -> bool:
        """Check if user has specific permission."""
        
        user_permissions = user.get('permissions', [])
        return permission in user_permissions
    
    def has_any_permission(self, user: Dict[str, Any], permissions: List[str]) -> bool:
        """Check if user has any of the specified permissions."""
        
        user_permissions = user.get('permissions', [])
        return any(perm in user_permissions for perm in permissions)
    
    def has_all_permissions(self, user: Dict[str, Any], permissions: List[str]) -> bool:
        """Check if user has all of the specified permissions."""
        
        user_permissions = user.get('permissions', [])
        return all(perm in user_permissions for perm in permissions)
    
    def get_user_permissions(self, user: Dict[str, Any]) -> List[str]:
        """Get user permissions."""
        
        return user.get('permissions', [])
    
    def add_user_permission(self, user: Dict[str, Any], permission: str) -> bool:
        """Add permission to user (for current session only)."""
        
        if 'permissions' not in user:
            user['permissions'] = []
        
        if permission not in user['permissions']:
            user['permissions'].append(permission)
            return True
        
        return False
    
    def remove_user_permission(self, user: Dict[str, Any], permission: str) -> bool:
        """Remove permission from user (for current session only)."""
        
        if 'permissions' in user and permission in user['permissions']:
            user['permissions'].remove(permission)
            return True
        
        return False
    
    def create_password_reset_token(self, user_id: str, email: str, expires_hours: int = 1) -> str:
        """Create password reset token."""
        
        reset_data = {
            'id': user_id,
            'email': email,
            'type': 'password_reset',
            'created_at': datetime.utcnow().isoformat()
        }
        
        expires_delta = timedelta(hours=expires_hours)
        token = self.create_access_token(reset_data, expires_delta)
        
        return token
    
    def validate_password_reset_token(self, token: str) -> Optional[Dict[str, Any]]:
        """Validate password reset token."""
        
        try:
            payload = self.verify_token(token)
            
            if payload.get('type') != 'password_reset':
                return None
            
            return {
                'user_id': payload.get('id'),
                'email': payload.get('email'),
                'created_at': payload.get('created_at')
            }
            
        except Exception:
            return None
    
    def create_email_verification_token(self, user_id: str, email: str, expires_hours: int = 24) -> str:
        """Create email verification token."""
        
        verification_data = {
            'id': user_id,
            'email': email,
            'type': 'email_verification',
            'created_at': datetime.utcnow().isoformat()
        }
        
        expires_delta = timedelta(hours=expires_hours)
        token = self.create_access_token(verification_data, expires_delta)
        
        return token
    
    def validate_email_verification_token(self, token: str) -> Optional[Dict[str, Any]]:
        """Validate email verification token."""
        
        try:
            payload = jwt.decode(token, self.secret_key, algorithms=[self.algorithm])
            
            if payload.get('type') != 'email_verification':
                return None
            
            return {
                'user_id': payload.get('id'),
                'email': payload.get('email'),
                'created_at': payload.get('created_at')
            }
            
        except Exception:
            return None

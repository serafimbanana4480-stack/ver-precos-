"""
Authentication Module
JWT-based authentication with Supabase integration support
"""
from __future__ import annotations
import logging
from datetime import datetime, timedelta, timezone
from typing import Optional, Dict, Any
from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from jose import JWTError, jwt
import bcrypt
from pydantic import BaseModel

from config import settings

logger = logging.getLogger(__name__)

# Security
security = HTTPBearer()
# Using bcrypt directly to avoid passlib's 72-byte limit check


# Models
class User(BaseModel):
    """User model"""
    id: Optional[int] = None
    email: str
    username: Optional[str] = None
    is_active: bool = True
    is_admin: bool = False


class UserCreate(BaseModel):
    """User creation model"""
    email: str
    username: Optional[str] = None
    password: str


class UserLogin(BaseModel):
    """User login model"""
    email: str
    password: str


class Token(BaseModel):
    """Token response model"""
    access_token: str
    token_type: str
    user: User


# JWT Configuration
SECRET_KEY = settings.resolve_jwt_secret()
ALGORITHM = settings.jwt_algorithm
ACCESS_TOKEN_EXPIRE_MINUTES = 60 * 24 * 7  # 7 days


def verify_password(plain_password: str, hashed_password: str) -> bool:
    """Verify a password against a hash"""
    # Truncate password to 72 bytes (bcrypt limit)
    password_bytes = plain_password.encode('utf-8')
    if len(password_bytes) > 72:
        password_bytes = password_bytes[:72]
    return bcrypt.checkpw(password_bytes, hashed_password.encode('utf-8'))


def get_password_hash(password: str) -> str:
    """Hash a password"""
    # Truncate password to 72 bytes (bcrypt limit)
    password_bytes = password.encode('utf-8')
    if len(password_bytes) > 72:
        password_bytes = password_bytes[:72]
    salt = bcrypt.gensalt()
    hashed = bcrypt.hashpw(password_bytes, salt)
    return hashed.decode('utf-8')


def create_access_token(data: Dict[str, Any], expires_delta: Optional[timedelta] = None) -> str:
    """Create a JWT access token"""
    to_encode = data.copy()
    if expires_delta:
        expire = datetime.now(timezone.utc) + expires_delta
    else:
        expire = datetime.now(timezone.utc) + timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES)
    
    to_encode.update({"exp": expire})
    encoded_jwt = jwt.encode(to_encode, SECRET_KEY, algorithm=ALGORITHM)
    return encoded_jwt


def decode_token(token: str) -> Optional[Dict[str, Any]]:
    """Decode and verify a JWT token"""
    try:
        payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
        return payload
    except JWTError:
        return None


async def get_current_user(credentials: HTTPAuthorizationCredentials = Depends(security)) -> User:
    """Get the current authenticated user"""
    credentials_exception = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Could not validate credentials",
        headers={"WWW-Authenticate": "Bearer"},
    )
    
    token = credentials.credentials
    payload = decode_token(token)
    
    if payload is None:
        raise credentials_exception
    
    email: str = payload.get("sub")
    if email is None:
        raise credentials_exception
    
    # In a real implementation, you would fetch the user from database
    # For now, return a simple user object
    user = User(
        id=payload.get("user_id"),
        email=email,
        username=payload.get("username"),
        is_active=payload.get("is_active", True),
        is_admin=payload.get("is_admin", False)
    )
    
    return user


async def get_current_active_user(current_user: User = Depends(get_current_user)) -> User:
    """Get the current active user"""
    if not current_user.is_active:
        raise HTTPException(status_code=400, detail="Inactive user")
    return current_user


async def get_current_admin_user(current_user: User = Depends(get_current_active_user)) -> User:
    """Get the current admin user"""
    if not current_user.is_admin:
        raise HTTPException(status_code=403, detail="Not enough permissions")
    return current_user


# Simple in-memory user store (in production, use database)
# This is a placeholder - in production, integrate with Supabase Auth
_users_db: Dict[str, Dict[str, Any]] = {}


def create_user(user: UserCreate) -> User:
    """Create a new user (placeholder)"""
    # Check if user already exists
    if user.email in _users_db:
        raise HTTPException(status_code=400, detail="Email already registered")
    
    # Hash password
    hashed_password = get_password_hash(user.password)
    
    # Store user
    user_data = {
        "email": user.email,
        "username": user.username,
        "hashed_password": hashed_password,
        "is_active": True,
        "is_admin": False,
        "created_at": datetime.now(timezone.utc).isoformat()
    }
    
    _users_db[user.email] = user_data
    
    return User(
        id=len(_users_db),
        email=user.email,
        username=user.username,
        is_active=True,
        is_admin=False
    )


def authenticate_user(email: str, password: str) -> Optional[User]:
    """Authenticate a user (placeholder)"""
    user_data = _users_db.get(email)
    
    if not user_data:
        return None
    
    if not verify_password(password, user_data["hashed_password"]):
        return None
    
    return User(
        id=len(_users_db),
        email=user_data["email"],
        username=user_data.get("username"),
        is_active=user_data["is_active"],
        is_admin=user_data.get("is_admin", False)
    )


# Supabase integration (optional)
try:
    from supabase import create_client, Client
    
    supabase: Optional[Client] = None
    
    if hasattr(settings, 'supabase_url') and hasattr(settings, 'supabase_key'):
        try:
            supabase = create_client(
                settings.supabase_url,
                settings.supabase_key
            )
            logger.info("Supabase client initialized")
        except Exception as e:
            logger.warning(f"Failed to initialize Supabase: {e}")
    
except ImportError:
    logger.warning("supabase package not installed, skipping Supabase integration")
    supabase = None

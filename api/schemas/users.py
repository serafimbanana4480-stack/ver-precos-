"""
User schemas for API.
"""
from typing import Optional, List, Dict, Any
from datetime import datetime
from pydantic import BaseModel, Field, validator, EmailStr
import re


class BaseUser(BaseModel):
    """Base user schema."""
    
    email: str
    role: str
    is_active: bool
    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None
    last_login: Optional[datetime] = None
    
    class Config:
        from_attributes = True


class UserResponse(BaseUser):
    """User response schema."""
    
    id: str
    name: Optional[str] = None
    phone: Optional[str] = None
    avatar: Optional[str] = None
    preferences: Optional[Dict[str, Any]] = None
    permissions: List[str] = Field(default_factory=list)
    
    @validator('email')
    def validate_email(cls, v):
        if not re.match(r'^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$', v):
            raise ValueError('Invalid email format')
        return v.lower()
    
    @validator('phone')
    def validate_phone(cls, v):
        if v:
            # Remove non-numeric characters
            phone_digits = re.sub(r'[^\d]', '', v)
            if len(phone_digits) < 9 or len(phone_digits) > 15:
                raise ValueError('Invalid phone number')
        return v
    
    @validator('role')
    def validate_role(cls, v):
        valid_roles = ['admin', 'moderator', 'user']
        if v not in valid_roles:
            raise ValueError(f'Role must be one of: {valid_roles}')
        return v


class UserCreate(BaseModel):
    """User creation schema."""
    
    email: EmailStr = Field(..., description="User email address")
    password: str = Field(..., min_length=8, max_length=128, description="User password")
    name: Optional[str] = Field(None, min_length=1, max_length=100, description="User full name")
    phone: Optional[str] = Field(None, description="User phone number")
    role: str = Field("user", description="User role")
    is_active: bool = Field(True, description="Whether user is active")
    preferences: Optional[Dict[str, Any]] = Field(default_factory=dict, description="User preferences")
    
    @validator('password')
    def validate_password(cls, v):
        if len(v) < 8:
            raise ValueError('Password must be at least 8 characters long')
        
        if not re.search(r'[A-Z]', v):
            raise ValueError('Password must contain at least one uppercase letter')
        
        if not re.search(r'[a-z]', v):
            raise ValueError('Password must contain at least one lowercase letter')
        
        if not re.search(r'\d', v):
            raise ValueError('Password must contain at least one digit')
        
        return v
    
    @validator('name')
    def clean_name(cls, v):
        if v:
            return v.strip().title()
        return v
    
    @validator('phone')
    def clean_phone(cls, v):
        if v:
            # Remove all non-numeric characters
            return re.sub(r'[^\d]', '', v)
        return v
    
    @validator('role')
    def validate_role(cls, v):
        valid_roles = ['admin', 'moderator', 'user']
        if v not in valid_roles:
            raise ValueError(f'Role must be one of: {valid_roles}')
        return v


class UserUpdate(BaseModel):
    """User update schema."""
    
    name: Optional[str] = Field(None, min_length=1, max_length=100)
    phone: Optional[str] = None
    avatar: Optional[str] = None
    role: Optional[str] = None
    is_active: Optional[bool] = None
    preferences: Optional[Dict[str, Any]] = None
    permissions: Optional[List[str]] = None
    
    @validator('name')
    def clean_name(cls, v):
        if v:
            return v.strip().title()
        return v
    
    @validator('phone')
    def clean_phone(cls, v):
        if v:
            return re.sub(r'[^\d]', '', v)
        return v
    
    @validator('role')
    def validate_role(cls, v):
        if v is not None:
            valid_roles = ['admin', 'moderator', 'user']
            if v not in valid_roles:
                raise ValueError(f'Role must be one of: {valid_roles}')
        return v


class UserLogin(BaseModel):
    """User login schema."""
    
    email: EmailStr = Field(..., description="User email")
    password: str = Field(..., description="User password")
    remember_me: bool = Field(False, description="Remember login session")
    
    @validator('email')
    def clean_email(cls, v):
        return v.lower().strip()


class UserRegister(BaseModel):
    """User registration schema."""
    
    email: EmailStr = Field(..., description="User email address")
    password: str = Field(..., min_length=8, max_length=128, description="User password")
    confirm_password: str = Field(..., description="Confirm password")
    name: str = Field(..., min_length=1, max_length=100, description="User full name")
    phone: Optional[str] = Field(None, description="User phone number")
    accept_terms: bool = Field(..., description="Accept terms and conditions")
    
    @validator('email')
    def clean_email(cls, v):
        return v.lower().strip()
    
    @validator('name')
    def clean_name(cls, v):
        return v.strip().title()
    
    @validator('phone')
    def clean_phone(cls, v):
        if v:
            return re.sub(r'[^\d]', '', v)
        return v
    
    @validator('confirm_password')
    def passwords_match(cls, v, values):
        if 'password' in values and v != values['password']:
            raise ValueError('Passwords do not match')
        return v
    
    @validator('password')
    def validate_password(cls, v):
        if len(v) < 8:
            raise ValueError('Password must be at least 8 characters long')
        
        if not re.search(r'[A-Z]', v):
            raise ValueError('Password must contain at least one uppercase letter')
        
        if not re.search(r'[a-z]', v):
            raise ValueError('Password must contain at least one lowercase letter')
        
        if not re.search(r'\d', v):
            raise ValueError('Password must contain at least one digit')
        
        return v


class UserPasswordChange(BaseModel):
    """User password change schema."""
    
    current_password: str = Field(..., description="Current password")
    new_password: str = Field(..., min_length=8, max_length=128, description="New password")
    confirm_password: str = Field(..., description="Confirm new password")
    
    @validator('confirm_password')
    def passwords_match(cls, v, values):
        if 'new_password' in values and v != values['new_password']:
            raise ValueError('Passwords do not match')
        return v
    
    @validator('new_password')
    def validate_password(cls, v):
        if len(v) < 8:
            raise ValueError('Password must be at least 8 characters long')
        
        if not re.search(r'[A-Z]', v):
            raise ValueError('Password must contain at least one uppercase letter')
        
        if not re.search(r'[a-z]', v):
            raise ValueError('Password must contain at least one lowercase letter')
        
        if not re.search(r'\d', v):
            raise ValueError('Password must contain at least one digit')
        
        return v


class UserPasswordReset(BaseModel):
    """User password reset schema."""
    
    email: EmailStr = Field(..., description="User email address")
    token: str = Field(..., description="Reset token")
    new_password: str = Field(..., min_length=8, max_length=128, description="New password")
    confirm_password: str = Field(..., description="Confirm new password")
    
    @validator('email')
    def clean_email(cls, v):
        return v.lower().strip()
    
    @validator('confirm_password')
    def passwords_match(cls, v, values):
        if 'new_password' in values and v != values['new_password']:
            raise ValueError('Passwords do not match')
        return v
    
    @validator('new_password')
    def validate_password(cls, v):
        if len(v) < 8:
            raise ValueError('Password must be at least 8 characters long')
        
        if not re.search(r'[A-Z]', v):
            raise ValueError('Password must contain at least one uppercase letter')
        
        if not re.search(r'[a-z]', v):
            raise ValueError('Password must contain at least one lowercase letter')
        
        if not re.search(r'\d', v):
            raise ValueError('Password must contain at least one digit')
        
        return v


class UserEmailVerification(BaseModel):
    """User email verification schema."""
    
    email: EmailStr = Field(..., description="User email address")
    token: str = Field(..., description="Verification token")
    
    @validator('email')
    def clean_email(cls, v):
        return v.lower().strip()


class UserProfile(BaseModel):
    """User profile schema."""
    
    name: Optional[str] = Field(None, min_length=1, max_length=100)
    phone: Optional[str] = None
    avatar: Optional[str] = None
    bio: Optional[str] = Field(None, max_length=500)
    location: Optional[str] = Field(None, max_length=100)
    website: Optional[str] = None
    social_links: Optional[Dict[str, str]] = Field(default_factory=dict)
    preferences: Optional[Dict[str, Any]] = Field(default_factory=dict)
    notification_settings: Optional[Dict[str, bool]] = Field(default_factory=dict)
    
    @validator('name')
    def clean_name(cls, v):
        if v:
            return v.strip().title()
        return v
    
    @validator('phone')
    def clean_phone(cls, v):
        if v:
            return re.sub(r'[^\d]', '', v)
        return v
    
    @validator('website')
    def validate_website(cls, v):
        if v:
            if not re.match(r'^https?://', v):
                raise ValueError('Website must start with http:// or https://')
        return v


class UserPreferences(BaseModel):
    """User preferences schema."""
    
    theme: str = Field("light", pattern="^(light|dark|auto)$")
    language: str = Field("en", pattern="^(en|pt|es|fr|de)$")
    timezone: str = Field("UTC")
    date_format: str = Field("%Y-%m-%d", pattern="^(%Y-%m-%d|%d/%m/%Y|%m/%d/%Y)$")
    time_format: str = Field("%H:%M", pattern="^(%H:%M|%I:%M %p)$")
    currency: str = Field("EUR", pattern="^(EUR|USD|GBP|JPY)$")
    notifications: Dict[str, bool] = Field(default_factory=dict)
    privacy: Dict[str, bool] = Field(default_factory=dict)
    
    @validator('timezone')
    def validate_timezone(cls, v):
        # Basic timezone validation
        if not re.match(r'^[A-Za-z_]+/[A-Za-z_]+$', v):
            raise ValueError('Invalid timezone format')
        return v


class UserApiKey(BaseModel):
    """User API key schema."""
    
    name: str = Field(..., min_length=1, max_length=100)
    permissions: List[str] = Field(..., min_items=1)
    expires_days: Optional[int] = Field(None, ge=1, le=365)
    description: Optional[str] = Field(None, max_length=500)
    is_active: bool = Field(True)
    
    @validator('name')
    def clean_name(cls, v):
        return v.strip()
    
    @validator('permissions')
    def validate_permissions(cls, v):
        valid_permissions = [
            'read_listings', 'write_listings', 'delete_listings',
            'read_analytics', 'read_search', 'write_search',
            'admin_users', 'admin_system'
        ]
        
        for perm in v:
            if perm not in valid_permissions:
                raise ValueError(f'Invalid permission: {perm}')
        
        return v


class UserSession(BaseModel):
    """User session schema."""
    
    id: str
    user_id: str
    token: str
    refresh_token: str
    expires_at: datetime
    created_at: datetime
    last_activity: datetime
    ip_address: str
    user_agent: str
    is_active: bool


class UserActivity(BaseModel):
    """User activity schema."""
    
    id: Optional[str] = None
    user_id: str
    activity_type: str = Field(..., pattern="^(login|logout|view|search|create|update|delete)$")
    resource_type: Optional[str] = None
    resource_id: Optional[str] = None
    details: Optional[Dict[str, Any]] = Field(default_factory=dict)
    ip_address: str
    user_agent: str
    created_at: datetime


class UserNotification(BaseModel):
    """User notification schema."""
    
    id: Optional[str] = None
    user_id: str
    type: str = Field(..., pattern="^(info|warning|error|success)$")
    title: str = Field(..., min_length=1, max_length=200)
    message: str = Field(..., min_length=1, max_length=1000)
    data: Optional[Dict[str, Any]] = Field(default_factory=dict)
    is_read: bool = False
    created_at: datetime
    read_at: Optional[datetime] = None


class UserStats(BaseModel):
    """User statistics schema."""
    
    user_id: str
    total_listings: int = Field(0, ge=0)
    total_searches: int = Field(0, ge=0)
    total_views: int = Field(0, ge=0)
    total_actions: int = Field(0, ge=0)
    last_login: Optional[datetime] = None
    registration_date: Optional[datetime] = None
    activity_streakdown: Dict[str, int] = Field(default_factory=dict)
    favorite_listings: List[str] = Field(default_factory=list)
    saved_searches: List[str] = Field(default_factory=list)


class UserBulkCreate(BaseModel):
    """Bulk user creation schema."""
    
    users: List[UserCreate] = Field(..., max_items=100)
    
    @validator('users')
    def validate_users_count(cls, v):
        if len(v) == 0:
            raise ValueError('At least one user must be provided')
        return v


class UserBulkUpdate(BaseModel):
    """Bulk user update schema."""
    
    user_ids: List[str] = Field(..., max_items=100)
    updates: UserUpdate
    
    @validator('user_ids')
    def validate_user_ids_count(cls, v):
        if len(v) == 0:
            raise ValueError('At least one user ID must be provided')
        return v


class UserSearch(BaseModel):
    """User search schema."""
    
    query: Optional[str] = Field(None, min_length=2, max_length=100)
    role: Optional[str] = Field(None, pattern="^(admin|moderator|user)$")
    is_active: Optional[bool] = None
    created_after: Optional[datetime] = None
    created_before: Optional[datetime] = None
    last_login_after: Optional[datetime] = None
    last_login_before: Optional[datetime] = None
    sort_by: str = Field("created_at", pattern="^(created_at|updated_at|last_login|name|email)$")
    sort_order: str = Field("desc", pattern="^(asc|desc)$")
    limit: int = Field(20, ge=1, le=100)
    offset: int = Field(0, ge=0)
    
    @validator('query')
    def clean_query(cls, v):
        if v:
            return v.strip()
        return v


class UserExport(BaseModel):
    """User export schema."""
    
    format: str = Field("csv", pattern="^(csv|json|excel)$")
    filters: Optional[UserSearch] = None
    fields: Optional[List[str]] = None
    include_sensitive_data: bool = False


class UserImport(BaseModel):
    """User import schema."""
    
    file_path: str = Field(..., min_length=1)
    format: str = Field("csv", pattern="^(csv|json|excel)$")
    overwrite_existing: bool = False
    validate_emails: bool = True
    send_welcome_email: bool = False


class UserValidation(BaseModel):
    """User validation schema."""
    
    email: EmailStr = Field(..., description="User email")
    password: Optional[str] = Field(None, min_length=8, max_length=128)
    phone: Optional[str] = None
    strict_mode: bool = False
    
    @validator('email')
    def clean_email(cls, v):
        return v.lower().strip()
    
    @validator('phone')
    def clean_phone(cls, v):
        if v:
            return re.sub(r'[^\d]', '', v)
        return v


class UserDeletion(BaseModel):
    """User deletion schema."""
    
    user_id: str = Field(..., min_length=1)
    confirm: bool = Field(False, description="Confirm deletion")
    reason: Optional[str] = Field(None, max_length=500)
    transfer_data_to: Optional[str] = None
    delete_all_data: bool = False


class UserRoleUpdate(BaseModel):
    """User role update schema."""
    
    user_id: str = Field(..., min_length=1)
    new_role: str = Field(..., pattern="^(admin|moderator|user)$")
    reason: str = Field(..., min_length=10, max_length=500)
    notify_user: bool = True


class UserPermissionUpdate(BaseModel):
    """User permission update schema."""
    
    user_id: str = Field(..., min_length=1)
    permissions: List[str] = Field(..., min_items=1)
    action: str = Field("add", pattern="^(add|remove|replace)$")
    reason: Optional[str] = Field(None, max_length=500)
    notify_user: bool = True
    
    @validator('permissions')
    def validate_permissions(cls, v):
        valid_permissions = [
            'read_listings', 'write_listings', 'delete_listings',
            'read_analytics', 'read_search', 'write_search',
            'admin_users', 'admin_system'
        ]
        
        for perm in v:
            if perm not in valid_permissions:
                raise ValueError(f'Invalid permission: {perm}')
        
        return v


class UserActivityReport(BaseModel):
    """User activity report schema."""
    
    user_id: str
    start_date: datetime
    end_date: datetime
    activity_types: Optional[List[str]] = None
    include_details: bool = False
    export_format: str = Field("json", pattern="^(json|csv)$")

"""
Common schemas for API.
"""
from typing import Optional, List, Dict, Any, Union
from datetime import datetime, date
from pydantic import BaseModel, Field, validator
import re


class BaseResponse(BaseModel):
    """Base response schema."""
    
    success: bool = True
    message: Optional[str] = None
    timestamp: datetime = Field(default_factory=datetime.now)
    request_id: Optional[str] = None
    
    class Config:
        from_attributes = True


class ErrorResponse(BaseResponse):
    """Error response schema."""
    
    success: bool = False
    error: str = Field(..., min_length=1)
    error_code: Optional[str] = None
    details: Optional[Dict[str, Any]] = None
    stack_trace: Optional[str] = None


class SuccessResponse(BaseResponse):
    """Success response schema."""
    
    data: Optional[Union[Dict[str, Any], List[Any]]] = None
    count: Optional[int] = None
    total: Optional[int] = None
    page: Optional[int] = None
    pages: Optional[int] = None


class PaginationParams(BaseModel):
    """Pagination parameters schema."""
    
    page: int = Field(1, ge=1, description="Page number")
    limit: int = Field(20, ge=1, le=100, description="Items per page")
    offset: Optional[int] = Field(None, ge=0, description="Offset for pagination")
    
    @validator('limit')
    def validate_limit(cls, v):
        if v > 100:
            raise ValueError('Limit cannot exceed 100 items per page')
        return v


class DateRangeParams(BaseModel):
    """Date range parameters schema."""
    
    start_date: Union[datetime, date, str] = Field(..., description="Start date")
    end_date: Union[datetime, date, str] = Field(..., description="End date")
    
    @validator('start_date', 'end_date')
    def parse_date(cls, v):
        if isinstance(v, str):
            try:
                return datetime.fromisoformat(v.replace('Z', '+00:00'))
            except ValueError:
                try:
                    return datetime.strptime(v, '%Y-%m-%d')
                except ValueError:
                    raise ValueError('Invalid date format. Use ISO format or YYYY-MM-DD')
        elif isinstance(v, date):
            return datetime.combine(v, datetime.min.time())
        return v
    
    @validator('end_date')
    def validate_date_range(cls, v, values):
        if 'start_date' in values:
            start_date = values['start_date']
            if isinstance(start_date, datetime) and isinstance(v, datetime):
                if start_date >= v:
                    raise ValueError('End date must be after start date')
        return v


class SortParams(BaseModel):
    """Sort parameters schema."""
    
    sort_by: str = Field("created_at", description="Field to sort by")
    sort_order: str = Field("desc", pattern="^(asc|desc)$", description="Sort order")
    
    @validator('sort_by')
    def validate_sort_by(cls, v):
        # Clean up field name
        return v.strip().lower()


class FilterParams(BaseModel):
    """Filter parameters schema."""
    
    filters: Optional[Dict[str, Any]] = Field(default_factory=dict)
    search: Optional[str] = Field(None, min_length=2, max_length=100)
    
    @validator('search')
    def clean_search(cls, v):
        if v:
            return v.strip()
        return v


class BulkOperationParams(BaseModel):
    """Bulk operation parameters schema."""
    
    ids: List[str] = Field(..., min_items=1, max_items=1000)
    confirm: bool = Field(False, description="Confirm bulk operation")
    reason: Optional[str] = Field(None, max_length=500)
    
    @validator('ids')
    def validate_ids(cls, v):
        if len(v) == 0:
            raise ValueError('At least one ID must be provided')
        return v


class ExportParams(BaseModel):
    """Export parameters schema."""
    
    format: str = Field("csv", pattern="^(csv|json|excel|pdf)$", description="Export format")
    fields: Optional[List[str]] = Field(None, description="Fields to export")
    filters: Optional[Dict[str, Any]] = Field(default_factory=dict)
    include_headers: bool = Field(True, description="Include headers in export")
    
    @validator('fields')
    def validate_fields(cls, v):
        if v:
            # Remove duplicates and clean field names
            cleaned_fields = []
            for field in v:
                cleaned_field = field.strip().lower()
                if cleaned_field not in cleaned_fields:
                    cleaned_fields.append(cleaned_field)
            return cleaned_fields
        return v


class ImportParams(BaseModel):
    """Import parameters schema."""
    
    file_path: str = Field(..., min_length=1, description="File path")
    format: str = Field("csv", pattern="^(csv|json|excel)$", description="Import format")
    overwrite: bool = Field(False, description="Overwrite existing data")
    validate: bool = Field(True, description="Validate data during import")
    
    @validator('file_path')
    def clean_file_path(cls, v):
        return v.strip()


class ValidationParams(BaseModel):
    """Validation parameters schema."""
    
    strict_mode: bool = Field(False, description="Enable strict validation")
    skip_validation: bool = Field(False, description="Skip validation")
    custom_rules: Optional[Dict[str, Any]] = Field(default_factory=dict)


class CacheParams(BaseModel):
    """Cache parameters schema."""
    
    ttl: Optional[int] = Field(None, ge=0, le=3600, description="Cache TTL in seconds")
    invalidate: bool = Field(False, description="Invalidate cache")
    cache_key: Optional[str] = Field(None, description="Specific cache key")
    
    @validator('cache_key')
    def clean_cache_key(cls, v):
        if v:
            return v.strip()
        return v


class NotificationParams(BaseModel):
    """Notification parameters schema."""
    
    channels: List[str] = Field(default_factory=lambda: ["email"])
    recipients: Optional[List[str]] = None
    subject: Optional[str] = Field(None, max_length=200)
    message: Optional[str] = Field(None, max_length=1000)
    
    @validator('channels')
    def validate_channels(cls, v):
        valid_channels = ["email", "sms", "push", "webhook", "slack", "teams"]
        for channel in v:
            if channel not in valid_channels:
                raise ValueError(f'Invalid notification channel: {channel}')
        return v
    
    @validator('recipients')
    def validate_recipients(cls, v):
        if v:
            email_pattern = r'^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$'
            for recipient in v:
                if '@' in recipient and not re.match(email_pattern, recipient):
                    raise ValueError(f'Invalid email: {recipient}')
        return v


class HealthCheckResponse(BaseModel):
    """Health check response schema."""
    
    status: str = Field(..., pattern="^(healthy|unhealthy|degraded)$")
    timestamp: datetime = Field(default_factory=datetime.now)
    version: str
    uptime: float
    checks: Dict[str, Dict[str, Any]] = Field(default_factory=dict)
    environment: Optional[str] = None


class MetricsResponse(BaseModel):
    """Metrics response schema."""
    
    metrics: Dict[str, Union[int, float, str]]
    timestamp: datetime = Field(default_factory=datetime.now)
    period: str
    unit: Optional[str] = None


class LogEntry(BaseModel):
    """Log entry schema."""
    
    timestamp: datetime
    level: str = Field(..., pattern="^(DEBUG|INFO|WARNING|ERROR|CRITICAL)$")
    message: str
    module: Optional[str] = None
    user_id: Optional[str] = None
    request_id: Optional[str] = None
    extra: Optional[Dict[str, Any]] = None


class ConfigResponse(BaseModel):
    """Configuration response schema."""
    
    config: Dict[str, Any]
    version: str
    last_updated: datetime
    environment: str


class FileUploadResponse(BaseModel):
    """File upload response schema."""
    
    file_id: str
    filename: str
    size: int
    content_type: str
    uploaded_at: datetime = Field(default_factory=datetime.now)
    url: Optional[str] = None


class FileDownloadParams(BaseModel):
    """File download parameters schema."""
    
    file_id: str = Field(..., min_length=1)
    filename: Optional[str] = None
    force_download: bool = True


class WebhookParams(BaseModel):
    """Webhook parameters schema."""
    
    url: str = Field(..., min_length=1)
    event: str = Field(..., min_length=1)
    payload: Optional[Dict[str, Any]] = None
    headers: Optional[Dict[str, str]] = None
    timeout: int = Field(30, ge=1, le=300)
    
    @validator('url')
    def validate_url(cls, v):
        if not re.match(r'^https?://', v):
            raise ValueError('URL must start with http:// or https://')
        return v


class BatchResponse(BaseModel):
    """Batch operation response schema."""
    
    total: int = Field(..., ge=0)
    successful: int = Field(..., ge=0)
    failed: int = Field(..., ge=0)
    errors: List[Dict[str, Any]] = Field(default_factory=list)
    results: Optional[List[Dict[str, Any]]] = None
    
    @validator('failed')
    def validate_failed(cls, v, values):
        if 'total' in values and 'successful' in values:
            expected_failed = values['total'] - values['successful']
            if v != expected_failed:
                raise ValueError(f'Failed count ({v}) does not match expected ({expected_failed})')
        return v


class SearchParams(BaseModel):
    """Search parameters schema."""
    
    query: Optional[str] = Field(None, min_length=2, max_length=100)
    filters: Optional[Dict[str, Any]] = Field(default_factory=dict)
    sort_by: Optional[str] = None
    sort_order: str = Field("desc", pattern="^(asc|desc)$")
    limit: int = Field(20, ge=1, le=100)
    offset: int = Field(0, ge=0)
    
    @validator('query')
    def clean_query(cls, v):
        if v:
            return v.strip()
        return v


class CountResponse(BaseModel):
    """Count response schema."""
    
    count: int = Field(..., ge=0)
    filters: Optional[Dict[str, Any]] = None
    timestamp: datetime = Field(default_factory=datetime.now)


class StatusResponse(BaseModel):
    """Status response schema."""
    
    status: str
    message: Optional[str] = None
    progress: Optional[float] = Field(None, ge=0, le=1)
    details: Optional[Dict[str, Any]] = None
    timestamp: datetime = Field(default_factory=datetime.now)


class IdResponse(BaseModel):
    """ID response schema."""
    
    id: str
    created_at: Optional[datetime] = None


class MessageResponse(BaseModel):
    """Message response schema."""
    
    message: str = Field(..., min_length=1)
    type: str = Field("info", pattern="^(info|success|warning|error)$")
    timestamp: datetime = Field(default_factory=datetime.now)


class ValidationError(BaseModel):
    """Validation error schema."""
    
    field: str
    message: str
    value: Any
    code: Optional[str] = None


class ValidationErrorResponse(BaseModel):
    """Validation error response schema."""
    
    success: bool = False
    errors: List[ValidationError]
    timestamp: datetime = Field(default_factory=datetime.now)


class RateLimitResponse(BaseModel):
    """Rate limit response schema."""
    
    limit: int
    remaining: int
    reset: int
    retry_after: Optional[int] = None


class TokenResponse(BaseModel):
    """Token response schema."""
    
    access_token: str
    token_type: str = "bearer"
    expires_in: int
    refresh_token: Optional[str] = None
    scope: Optional[str] = None


class UserSession(BaseModel):
    """User session schema."""
    
    session_id: str
    user_id: str
    expires_at: datetime
    created_at: datetime
    last_activity: datetime
    ip_address: str
    user_agent: str


class ApiKeyResponse(BaseModel):
    """API key response schema."""
    
    api_key: str
    key_id: str
    name: str
    permissions: List[str]
    expires_at: Optional[datetime] = None
    created_at: datetime


class PermissionResponse(BaseModel):
    """Permission response schema."""
    
    permissions: List[str]
    roles: List[str]
    scopes: List[str]


class FeatureFlag(BaseModel):
    """Feature flag schema."""
    
    name: str
    enabled: bool
    description: Optional[str] = None
    conditions: Optional[Dict[str, Any]] = None


class FeatureFlagsResponse(BaseModel):
    """Feature flags response schema."""
    
    flags: Dict[str, FeatureFlag]
    user_id: Optional[str] = None
    timestamp: datetime = Field(default_factory=datetime.now)


class SystemInfo(BaseModel):
    """System information schema."""
    
    version: str
    build: str
    environment: str
    uptime: float
    memory_usage: Dict[str, float]
    cpu_usage: float
    disk_usage: Dict[str, float]
    timestamp: datetime = Field(default_factory=datetime.now)


class BackupResponse(BaseModel):
    """Backup response schema."""
    
    backup_id: str
    status: str = Field(..., pattern="^(started|completed|failed)$")
    size: Optional[int] = None
    location: Optional[str] = None
    created_at: datetime = Field(default_factory=datetime.now)
    completed_at: Optional[datetime] = None


class RestoreResponse(BaseModel):
    """Restore response schema."""
    
    restore_id: str
    status: str = Field(..., pattern="^(started|completed|failed)$")
    backup_id: str
    records_restored: int = 0
    errors: List[str] = Field(default_factory=list)
    created_at: datetime = Field(default_factory=datetime.now)
    completed_at: Optional[datetime] = None


class MaintenanceMode(BaseModel):
    """Maintenance mode schema."""
    
    enabled: bool
    message: Optional[str] = None
    start_time: Optional[datetime] = None
    end_time: Optional[datetime] = None
    affected_services: List[str] = Field(default_factory=list)


class AuditLog(BaseModel):
    """Audit log schema."""
    
    id: str
    user_id: Optional[str] = None
    action: str
    resource: str
    resource_id: Optional[str] = None
    details: Optional[Dict[str, Any]] = None
    ip_address: str
    user_agent: str
    timestamp: datetime = Field(default_factory=datetime.now)

"""
Alert validator for AutoDeal IA Hunter.
"""
from pydantic import BaseModel, validator
from typing import Optional


class AlertValidator(BaseModel):
    """Validator for alert data."""
    
    alert_type: str
    message: str
    channels: list
    
    @validator('alert_type')
    def validate_alert_type(cls, v):
        """Validate alert type."""
        valid_types = ['deal_found', 'error', 'scraping_complete', 'model_trained', 'system_health']
        if v not in valid_types:
            raise ValueError(f'Invalid alert type: {v}')
        return v
    
    @validator('message')
    def validate_message(cls, v):
        """Validate message is not empty."""
        if not v or not v.strip():
            raise ValueError('Message cannot be empty')
        return v
    
    @validator('channels')
    def validate_channels(cls, v):
        """Validate channels."""
        valid_channels = ['discord', 'email', 'telegram', 'webhook', 'slack', 'pagerduty']
        for channel in v:
            if channel not in valid_channels:
                raise ValueError(f'Invalid channel: {channel}')
        return v

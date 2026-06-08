"""
PagerDuty channel for alerts.
"""
import requests
from typing import Dict, Optional
from pydantic import BaseModel


class PagerDutyChannel(BaseModel):
    """PagerDuty notification channel."""
    
    integration_key: str
    api_key: Optional[str] = None
    service_key: Optional[str] = None
    
    def send(self, event: Dict) -> bool:
        """Send event to PagerDuty."""
        try:
            url = "https://events.pagerduty.com/v2/enqueue"
            payload = {
                "routing_key": self.integration_key,
                "event_action": "trigger",
                **event
            }
            
            response = requests.post(url, json=payload, timeout=10)
            return response.status_code == 202
        except Exception:
            return False

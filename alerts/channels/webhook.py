"""
Webhook channel for alerts.
"""
import requests
from typing import Dict, Optional
from pydantic import BaseModel


class WebhookChannel(BaseModel):
    """Webhook notification channel."""
    
    url: str
    method: str = "POST"
    headers: Dict[str, str] = {}
    timeout_seconds: int = 10
    
    def send(self, data: Dict) -> bool:
        """Send data to webhook."""
        try:
            if self.method.upper() == "POST":
                response = requests.post(self.url, json=data, headers=self.headers, timeout=self.timeout_seconds)
            elif self.method.upper() == "GET":
                response = requests.get(self.url, params=data, headers=self.headers, timeout=self.timeout_seconds)
            else:
                return False
            
            return response.status_code == 200
        except Exception:
            return False

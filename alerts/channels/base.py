"""
Base channel class for alerts.
"""
from abc import ABC, abstractmethod
from pydantic import BaseModel


class BaseChannel(BaseModel, ABC):
    """Base class for alert channels."""
    
    @abstractmethod
    def send(self, message: str, **kwargs) -> bool:
        """Send alert message."""
        pass

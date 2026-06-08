"""
Channel adapter for alerts.
"""
from typing import Dict, Any
from .base import BaseChannel


class ChannelAdapter:
    """Adapter for channel compatibility."""
    
    def __init__(self, channel: BaseChannel):
        self.channel = channel
    
    def send(self, data: Dict[str, Any]) -> bool:
        """Send data through channel."""
        message = self._format_message(data)
        return self.channel.send(message)
    
    def _format_message(self, data: Dict[str, Any]) -> str:
        """Format data into message."""
        return str(data)

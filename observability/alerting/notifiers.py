"""
Notifiers for alerting in AutoDeal IA Hunter.
"""
from typing import Dict, Callable
from datetime import datetime


class Notifier:
    """Notifier for sending alerts."""
    
    def __init__(self):
        self.notifiers: Dict[str, Callable] = {}
    
    def register_notifier(self, name: str, notifier_func: Callable) -> None:
        """Register notifier."""
        self.notifiers[name] = notifier_func
    
    def send_notification(self, notifier_name: str, message: str, **kwargs) -> bool:
        """Send notification via notifier."""
        if notifier_name not in self.notifiers:
            return False
        
        try:
            self.notifiers[notifier_name](message, **kwargs)
            return True
        except Exception:
            return False

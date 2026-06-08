"""
Alert persistence for AutoDeal IA Hunter.
"""
import json
from typing import Dict, List
from pathlib import Path


class AlertPersistence:
    """Persist alerts to disk."""
    
    def __init__(self, storage_path: str = "data/alerts.json"):
        self.storage_path = Path(storage_path)
        self.storage_path.parent.mkdir(parents=True, exist_ok=True)
    
    def save_alert(self, alert: Dict[str, any]) -> None:
        """Save alert to disk."""
        alerts = self.load_alerts()
        alerts.append(alert)
        
        with open(self.storage_path, 'w') as f:
            json.dump(alerts, f, indent=2)
    
    def load_alerts(self) -> List[Dict[str, any]]:
        """Load alerts from disk."""
        if not self.storage_path.exists():
            return []
        
        with open(self.storage_path, 'r') as f:
            return json.load(f)

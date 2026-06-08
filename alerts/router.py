"""
Alert router for AutoDeal IA Hunter.
"""
from typing import Dict, List
from pydantic import BaseModel


class AlertRouter(BaseModel):
    """Router for alert notifications based on type."""
    
    routes: Dict[str, List[str]] = {
        "deal_found": ["discord", "telegram"],
        "error": ["email"],
        "scraping_complete": ["discord"],
        "model_trained": ["discord"],
        "system_health": ["email"],
    }
    
    def get_channels(self, alert_type: str) -> List[str]:
        """Get channels for alert type."""
        return self.routes.get(alert_type, [])

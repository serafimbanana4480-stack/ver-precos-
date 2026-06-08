"""
Grafana dashboard configuration for AutoDeal IA Hunter.
"""
from typing import Dict, List


class GrafanaDashboard:
    """Grafana dashboard configuration."""
    
    def __init__(self):
        self.panels: List[Dict[str, any]] = []
    
    def add_panel(self, panel: Dict[str, any]) -> None:
        """Add panel to dashboard."""
        self.panels.append(panel)
    
    def get_dashboard_config(self) -> Dict[str, any]:
        """Get complete dashboard configuration."""
        return {
            "dashboard": {
                "title": "AutoDeal IA Hunter Dashboard",
                "panels": self.panels,
                "refresh": "1m",
                "timezone": "browser",
            }
        }

"""
Alerting rules for AutoDeal IA Hunter.
"""
from typing import Dict, List, Callable
from datetime import datetime


class AlertingRules:
    """Alerting rules for metrics."""
    
    def __init__(self):
        self.rules: Dict[str, Dict[str, any]] = {}
    
    def add_rule(self, name: str, condition: Callable, threshold: float, action: Callable) -> None:
        """Add alerting rule."""
        self.rules[name] = {
            "condition": condition,
            "threshold": threshold,
            "action": action,
        }
    
    def evaluate_rules(self, metrics: Dict[str, float]) -> List[Dict[str, any]]:
        """Evaluate all rules against metrics."""
        triggered = []
        
        for name, rule in self.rules.items():
            try:
                metric_value = rule["condition"](metrics)
                if metric_value >= rule["threshold"]:
                    triggered.append({
                        "rule": name,
                        "value": metric_value,
                        "threshold": rule["threshold"],
                        "timestamp": datetime.utcnow().isoformat(),
                    })
                    rule["action"]()
            except Exception:
                pass
        
        return triggered

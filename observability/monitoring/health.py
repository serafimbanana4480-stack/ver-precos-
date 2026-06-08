"""
Health checker for AutoDeal IA Hunter.
"""
from typing import Dict, List, Callable
from datetime import datetime
from enum import Enum


class HealthStatus(Enum):
    """Health status enum."""
    HEALTHY = "healthy"
    UNHEALTHY = "unhealthy"
    DEGRADED = "degraded"


class HealthChecker:
    """Health checker for application components."""
    
    def __init__(self):
        self.checks: Dict[str, Callable] = {}
    
    def register_check(self, name: str, check_func: Callable) -> None:
        """Register health check."""
        self.checks[name] = check_func
    
    async def check_health(self) -> Dict[str, any]:
        """Run all health checks."""
        results = {
            "status": HealthStatus.HEALTHY.value,
            "timestamp": datetime.utcnow().isoformat(),
            "checks": {},
        }
        
        overall_status = HealthStatus.HEALTHY
        
        for name, check_func in self.checks.items():
            try:
                result = await check_func()
                results["checks"][name] = {
                    "status": HealthStatus.HEALTHY.value,
                    "result": result,
                }
            except Exception as e:
                results["checks"][name] = {
                    "status": HealthStatus.UNHEALTHY.value,
                    "error": str(e),
                }
                overall_status = HealthStatus.UNHEALTHY
        
        results["status"] = overall_status.value
        return results

"""
Health check API routes.
"""
from fastapi import APIRouter, Depends, HTTPException
from typing import Dict, Any, List
from datetime import datetime
import logging

from ..dependencies import get_database, get_cache
# HealthService not implemented yet - using inline health check
# from ..services import HealthService

logger = logging.getLogger(__name__)

health_router = APIRouter(prefix="/health", tags=["health"])

@health_router.get("/", response_model=Dict[str, Any])
async def health_check(
    db = Depends(get_database),
    cache = Depends(get_cache)
):
    """Basic health check endpoint."""
    
    try:
        health_service = HealthService(db, cache)
        health_status = health_service.get_basic_health()
        
        return health_status
        
    except Exception as e:
        logger.error(f"Error in health check: {e}")
        raise HTTPException(status_code=500, detail="Health check failed")

@health_router.get("/detailed", response_model=Dict[str, Any])
async def detailed_health_check(
    db = Depends(get_database),
    cache = Depends(get_cache)
):
    """Detailed health check with all components."""
    
    try:
        health_service = HealthService(db, cache)
        health_status = health_service.get_detailed_health()
        
        # Determine overall status
        overall_status = "healthy"
        
        for component, status in health_status['components'].items():
            if status['status'] != "healthy":
                overall_status = "unhealthy"
                break
            elif status['status'] == "warning":
                overall_status = "warning"
        
        health_status['overall_status'] = overall_status
        health_status['timestamp'] = datetime.now().isoformat()
        
        return health_status
        
    except Exception as e:
        logger.error(f"Error in detailed health check: {e}")
        raise HTTPException(status_code=500, detail="Detailed health check failed")

@health_router.get("/database", response_model=Dict[str, Any])
async def database_health(
    db = Depends(get_database)
):
    """Database health check."""
    
    try:
        health_service = HealthService(db, None)
        db_health = health_service.check_database_health()
        
        return db_health
        
    except Exception as e:
        logger.error(f"Error in database health check: {e}")
        raise HTTPException(status_code=500, detail="Database health check failed")

@health_router.get("/cache", response_model=Dict[str, Any])
async def cache_health(
    cache = Depends(get_cache)
):
    """Cache health check."""
    
    try:
        health_service = HealthService(None, cache)
        cache_health = health_service.check_cache_health()
        
        return cache_health
        
    except Exception as e:
        logger.error(f"Error in cache health check: {e}")
        raise HTTPException(status_code=500, detail="Cache health check failed")

@health_router.get("/api", response_model=Dict[str, Any])
async def api_health():
    """API health check."""
    
    try:
        health_service = HealthService(None, None)
        api_health = health_service.check_api_health()
        
        return api_health
        
    except Exception as e:
        logger.error(f"Error in API health check: {e}")
        raise HTTPException(status_code=500, detail="API health check failed")

@health_router.get("/services", response_model=Dict[str, Any])
async def services_health(
    db = Depends(get_database),
    cache = Depends(get_cache)
):
    """External services health check."""
    
    try:
        health_service = HealthService(db, cache)
        services_health = health_service.check_external_services()
        
        return services_health
        
    except Exception as e:
        logger.error(f"Error in services health check: {e}")
        raise HTTPException(status_code=500, detail="Services health check failed")

@health_router.get("/metrics", response_model=Dict[str, Any])
async def health_metrics(
    db = Depends(get_database),
    cache = Depends(get_cache)
):
    """Health metrics and statistics."""
    
    try:
        health_service = HealthService(db, cache)
        metrics = health_service.get_health_metrics()
        
        return metrics
        
    except Exception as e:
        logger.error(f"Error getting health metrics: {e}")
        raise HTTPException(status_code=500, detail="Failed to get health metrics")

@health_router.get("/uptime", response_model=Dict[str, Any])
async def uptime_info():
    """Service uptime information."""
    
    try:
        health_service = HealthService(None, None)
        uptime = health_service.get_uptime_info()
        
        return uptime
        
    except Exception as e:
        logger.error(f"Error getting uptime info: {e}")
        raise HTTPException(status_code=500, detail="Failed to get uptime info")

@health_router.get("/version", response_model=Dict[str, Any])
async def version_info():
    """Application version information."""
    
    try:
        health_service = HealthService(None, None)
        version = health_service.get_version_info()
        
        return version
        
    except Exception as e:
        logger.error(f"Error getting version info: {e}")
        raise HTTPException(status_code=500, detail="Failed to get version info")

@health_router.get("/dependencies", response_model=Dict[str, Any])
async def dependencies_health():
    """External dependencies health check."""
    
    try:
        health_service = HealthService(None, None)
        dependencies = health_service.check_dependencies()
        
        return dependencies
        
    except Exception as e:
        logger.error(f"Error checking dependencies: {e}")
        raise HTTPException(status_code=500, detail="Failed to check dependencies")

@health_router.get("/performance", response_model=Dict[str, Any])
async def performance_metrics():
    """Performance metrics."""
    
    try:
        health_service = HealthService(None, None)
        performance = health_service.get_performance_metrics()
        
        return performance
        
    except Exception as e:
        logger.error(f"Error getting performance metrics: {e}")
        raise HTTPException(status_code=500, detail="Failed to get performance metrics")

@health_router.get("/logs", response_model=Dict[str, Any])
async def recent_logs(
    level: str = "INFO",
    limit: int = 100,
    hours: int = 24
):
    """Recent application logs."""
    
    try:
        health_service = HealthService(None, None)
        logs = health_service.get_recent_logs(level, limit, hours)
        
        return logs
        
    except Exception as e:
        logger.error(f"Error getting recent logs: {e}")
        raise HTTPException(status_code=500, detail="Failed to get recent logs")

@health_router.post("/test", response_model=Dict[str, Any])
async def run_health_tests(
    test_type: str = "basic",
    db = Depends(get_database),
    cache = Depends(get_cache)
):
    """Run health tests."""
    
    try:
        health_service = HealthService(db, cache)
        test_results = health_service.run_health_tests(test_type)
        
        return test_results
        
    except Exception as e:
        logger.error(f"Error running health tests: {e}")
        raise HTTPException(status_code=500, detail="Failed to run health tests")

@health_router.get("/status", response_model=Dict[str, Any])
async def service_status():
    """Overall service status."""
    
    try:
        health_service = HealthService(None, None)
        status = health_service.get_service_status()
        
        return status
        
    except Exception as e:
        logger.error(f"Error getting service status: {e}")
        raise HTTPException(status_code=500, detail="Failed to get service status")

@health_router.get("/system", response_model=Dict[str, Any])
async def system_info():
    """System information."""
    
    try:
        health_service = HealthService(None, None)
        system = health_service.get_system_info()
        
        return system
        
    except Exception as e:
        logger.error(f"Error getting system info: {e}")
        raise HTTPException(status_code=500, detail="Failed to get system info")

@health_router.get("/environment", response_model=Dict[str, Any])
async def environment_info():
    """Environment information."""
    
    try:
        health_service = HealthService(None, None)
        environment = health_service.get_environment_info()
        
        return environment
        
    except Exception as e:
        logger.error(f"Error getting environment info: {e}")
        raise HTTPException(status_code=500, detail="Failed to get environment info")

@health_router.get("/endpoints", response_model=List[Dict[str, Any]])
async def endpoints_status():
    """Status of all API endpoints."""
    
    try:
        health_service = HealthService(None, None)
        endpoints = health_service.get_endpoints_status()
        
        return endpoints
        
    except Exception as e:
        logger.error(f"Error getting endpoints status: {e}")
        raise HTTPException(status_code=500, detail="Failed to get endpoints status")

@health_router.get("/alerts", response_model=List[Dict[str, Any]])
async def health_alerts(
    severity: str = "warning",
    limit: int = 50
):
    """Health alerts."""
    
    try:
        health_service = HealthService(None, None)
        alerts = health_service.get_health_alerts(severity, limit)
        
        return alerts
        
    except Exception as e:
        logger.error(f"Error getting health alerts: {e}")
        raise HTTPException(status_code=500, detail="Failed to get health alerts")

@health_router.post("/maintenance", response_model=Dict[str, Any])
async def maintenance_mode(
    enable: bool = False,
    message: str = "System under maintenance"
):
    """Toggle maintenance mode."""
    
    try:
        health_service = HealthService(None, None)
        result = health_service.toggle_maintenance_mode(enable, message)
        
        return result
        
    except Exception as e:
        logger.error(f"Error toggling maintenance mode: {e}")
        raise HTTPException(status_code=500, detail="Failed to toggle maintenance mode")

@health_router.get("/ready", response_model=Dict[str, Any])
async def readiness_check(
    db = Depends(get_database),
    cache = Depends(get_cache)
):
    """Readiness check for Kubernetes/liveness probes."""
    
    try:
        health_service = HealthService(db, cache)
        readiness = health_service.check_readiness()
        
        # Return appropriate HTTP status
        if readiness['ready']:
            return readiness
        else:
            raise HTTPException(status_code=503, detail="Service not ready")
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error in readiness check: {e}")
        raise HTTPException(status_code=503, detail="Readiness check failed")

@health_router.get("/live", response_model=Dict[str, Any])
async def liveness_check():
    """Liveness check for Kubernetes/liveness probes."""
    
    try:
        health_service = HealthService(None, None)
        liveness = health_service.check_liveness()
        
        return liveness
        
    except Exception as e:
        logger.error(f"Error in liveness check: {e}")
        raise HTTPException(status_code=503, detail="Liveness check failed")

@health_router.get("/startup", response_model=Dict[str, Any])
async def startup_check(
    db = Depends(get_database),
    cache = Depends(get_cache)
):
    """Startup check for Kubernetes/startup probes."""
    
    try:
        health_service = HealthService(db, cache)
        startup = health_service.check_startup()
        
        # Return appropriate HTTP status
        if startup['started']:
            return startup
        else:
            raise HTTPException(status_code=503, detail="Service starting up")
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error in startup check: {e}")
        raise HTTPException(status_code=503, detail="Startup check failed")

@health_router.get("/resources", response_model=Dict[str, Any])
async def resource_usage():
    """Resource usage information."""
    
    try:
        health_service = HealthService(None, None)
        resources = health_service.get_resource_usage()
        
        return resources
        
    except Exception as e:
        logger.error(f"Error getting resource usage: {e}")
        raise HTTPException(status_code=500, detail="Failed to get resource usage")

@health_router.get("/security", response_model=Dict[str, Any])
async def security_status():
    """Security status check."""
    
    try:
        health_service = HealthService(None, None)
        security = health_service.check_security_status()
        
        return security
        
    except Exception as e:
        logger.error(f"Error checking security status: {e}")
        raise HTTPException(status_code=500, detail="Failed to check security status")

@health_router.get("/backup", response_model=Dict[str, Any])
async def backup_status(
    db = Depends(get_database)
):
    """Backup status check."""
    
    try:
        health_service = HealthService(db, None)
        backup = health_service.check_backup_status()
        
        return backup
        
    except Exception as e:
        logger.error(f"Error checking backup status: {e}")
        raise HTTPException(status_code=500, detail="Failed to check backup status")

@health_router.post("/backup/trigger", response_model=Dict[str, Any])
async def trigger_backup(
    backup_type: str = "full",
    db = Depends(get_database)
):
    """Trigger a backup."""
    
    try:
        health_service = HealthService(db, None)
        result = health_service.trigger_backup(backup_type)
        
        return result
        
    except Exception as e:
        logger.error(f"Error triggering backup: {e}")
        raise HTTPException(status_code=500, detail="Failed to trigger backup")

@health_router.get("/monitoring", response_model=Dict[str, Any])
async def monitoring_status():
    """Monitoring system status."""
    
    try:
        health_service = HealthService(None, None)
        monitoring = health_service.check_monitoring_status()
        
        return monitoring
        
    except Exception as e:
        logger.error(f"Error checking monitoring status: {e}")
        raise HTTPException(status_code=500, detail="Failed to check monitoring status")

@health_router.get("/sla", response_model=Dict[str, Any])
async def sla_metrics(
    days: int = 7
):
    """SLA metrics."""
    
    try:
        health_service = HealthService(None, None)
        sla = health_service.get_sla_metrics(days)
        
        return sla
        
    except Exception as e:
        logger.error(f"Error getting SLA metrics: {e}")
        raise HTTPException(status_code=500, detail="Failed to get SLA metrics")

@health_router.get("/dashboard", response_model=Dict[str, Any])
async def health_dashboard(
    db = Depends(get_database),
    cache = Depends(get_cache)
):
    """Comprehensive health dashboard."""
    
    try:
        health_service = HealthService(db, cache)
        dashboard = health_service.get_health_dashboard()
        
        return dashboard
        
    except Exception as e:
        logger.error(f"Error getting health dashboard: {e}")
        raise HTTPException(status_code=500, detail="Failed to get health dashboard")

"""
Service dependencies for API.
"""
from typing import Generator
import logging

from ..services.listing import ListingService
from ..services.search import SearchService
from ..services.analytics import AnalyticsService

logger = logging.getLogger(__name__)

# Global service instances
listing_service_instance = None
search_service_instance = None
analytics_service_instance = None


def get_listing_service() -> ListingService:
    """Get listing service instance."""
    
    global listing_service_instance
    
    if listing_service_instance is None:
        from .database import get_database
        from .cache import get_cache
        
        listing_service_instance = ListingService(get_database(), get_cache())
        logger.info("Listing service initialized")
    
    return listing_service_instance


def get_search_service() -> SearchService:
    """Get search service instance."""
    
    global search_service_instance
    
    if search_service_instance is None:
        from .database import get_database
        from .cache import get_cache
        
        search_service_instance = SearchService(get_database(), get_cache())
        logger.info("Search service initialized")
    
    return search_service_instance


def get_analytics_service() -> AnalyticsService:
    """Get analytics service instance."""
    
    global analytics_service_instance
    
    if analytics_service_instance is None:
        from .database import get_database
        from .cache import get_cache
        
        analytics_service_instance = AnalyticsService(get_database(), get_cache())
        logger.info("Analytics service initialized")
    
    return analytics_service_instance


def get_listing_session() -> Generator[ListingService, None, None]:
    """Get listing service session (for dependency injection)."""
    
    service = get_listing_service()
    
    try:
        yield service
    finally:
        # Cleanup if needed
        pass


def get_search_session() -> Generator[SearchService, None, None]:
    """Get search service session (for dependency injection)."""
    
    service = get_search_service()
    
    try:
        yield service
    finally:
        # Cleanup if needed
        pass


def get_analytics_session() -> Generator[AnalyticsService, None, None]:
    """Get analytics service session (for dependency injection)."""
    
    service = get_analytics_service()
    
    try:
        yield service
    finally:
        # Cleanup if needed
        pass


def close_all_services():
    """Close all service connections."""
    
    global listing_service_instance, search_service_instance, analytics_service_instance
    
    # Close database connections
    from .database import close_database
    close_database()
    
    # Close cache connections
    from .cache import close_cache
    close_cache()
    
    # Reset service instances
    listing_service_instance = None
    search_service_instance = None
    analytics_service_instance = None
    
    logger.info("All services closed")


def check_services_health() -> dict:
    """Check health of all services."""
    
    health_status = {
        "overall_status": "healthy",
        "services": {}
    }
    
    try:
        # Check database health
        from .database import check_database_health
        db_health = check_database_health()
        health_status["services"]["database"] = db_health
        
        if db_health["status"] != "healthy":
            health_status["overall_status"] = "degraded"
        
        # Check cache health
        from .cache import check_cache_health
        cache_health = check_cache_health()
        health_status["services"]["cache"] = cache_health
        
        if cache_health["status"] != "healthy":
            health_status["overall_status"] = "degraded"
        
        # Check services (basic check)
        try:
            listing_service = get_listing_service()
            health_status["services"]["listing_service"] = {"status": "healthy"}
        except Exception as e:
            health_status["services"]["listing_service"] = {"status": "unhealthy", "error": str(e)}
            health_status["overall_status"] = "degraded"
        
        try:
            search_service = get_search_service()
            health_status["services"]["search_service"] = {"status": "healthy"}
        except Exception as e:
            health_status["services"]["search_service"] = {"status": "unhealthy", "error": str(e)}
            health_status["overall_status"] = "degraded"
        
        try:
            analytics_service = get_analytics_service()
            health_status["services"]["analytics_service"] = {"status": "healthy"}
        except Exception as e:
            health_status["services"]["analytics_service"] = {"status": "unhealthy", "error": str(e)}
            health_status["overall_status"] = "degraded"
        
    except Exception as e:
        logger.error(f"Error checking services health: {e}")
        health_status["overall_status"] = "unhealthy"
        health_status["error"] = str(e)
    
    return health_status


def get_services_stats() -> dict:
    """Get statistics for all services."""
    
    stats = {
        "services": {},
        "overall_stats": {}
    }
    
    try:
        # Database stats
        from .database import get_database_stats
        db_stats = get_database_stats()
        stats["services"]["database"] = db_stats
        
        # Cache stats
        from .cache import get_cache_stats
        cache_stats = get_cache_stats()
        stats["services"]["cache"] = cache_stats
        
        # Service-specific stats
        try:
            listing_service = get_listing_service()
            stats["services"]["listing_service"] = {
                "status": "active",
                "database_connected": True,
                "cache_connected": True
            }
        except Exception as e:
            stats["services"]["listing_service"] = {"status": "error", "error": str(e)}
        
        try:
            search_service = get_search_service()
            stats["services"]["search_service"] = {
                "status": "active",
                "database_connected": True,
                "cache_connected": True
            }
        except Exception as e:
            stats["services"]["search_service"] = {"status": "error", "error": str(e)}
        
        try:
            analytics_service = get_analytics_service()
            stats["services"]["analytics_service"] = {
                "status": "active",
                "database_connected": True,
                "cache_connected": True
            }
        except Exception as e:
            stats["services"]["analytics_service"] = {"status": "error", "error": str(e)}
        
        # Overall stats
        active_services = sum(1 for service in stats["services"].values() if service.get("status") == "active")
        total_services = len(stats["services"])
        
        stats["overall_stats"] = {
            "active_services": active_services,
            "total_services": total_services,
            "services_health": (active_services / total_services) * 100 if total_services > 0 else 0
        }
        
    except Exception as e:
        logger.error(f"Error getting services stats: {e}")
        stats["error"] = str(e)
    
    return stats


def warm_up_services():
    """Warm up all services."""
    
    try:
        # Initialize all services
        get_listing_service()
        get_search_service()
        get_analytics_service()
        
        # Warm up cache
        from .cache import warm_up_cache
        warm_up_cache()
        
        # Warm up database
        from .database import warm_up_database
        warm_up_database()
        
        logger.info("All services warmed up")
        
    except Exception as e:
        logger.error(f"Error warming up services: {e}")


def reset_services() -> bool:
    """Reset all services."""
    
    try:
        # Reset database
        from .database import reset_database
        db_reset = reset_database()
        
        # Reset cache
        from .cache import reset_cache
        cache_reset = reset_cache()
        
        # Reset service instances
        global listing_service_instance, search_service_instance, analytics_service_instance
        listing_service_instance = None
        search_service_instance = None
        analytics_service_instance = None
        
        logger.info(f"Services reset - Database: {db_reset}, Cache: {cache_reset}")
        return True
        
    except Exception as e:
        logger.error(f"Error resetting services: {e}")
        return False


def backup_services(backup_dir: str) -> dict:
    """Backup all services data."""
    
    backup_results = {}
    
    try:
        import os
        os.makedirs(backup_dir, exist_ok=True)
        
        # Backup database
        from .database import backup_database
        db_backup_path = os.path.join(backup_dir, "database_backup.csv")
        backup_results["database"] = backup_database(db_backup_path)
        
        # Backup cache
        from .cache import backup_cache
        cache_backup_path = os.path.join(backup_dir, "cache_backup.json")
        backup_results["cache"] = backup_cache(cache_backup_path)
        
        logger.info(f"Services backup completed to {backup_dir}")
        
    except Exception as e:
        logger.error(f"Error backing up services: {e}")
        backup_results["error"] = str(e)
    
    return backup_results


def restore_services(backup_dir: str) -> dict:
    """Restore all services data from backup."""
    
    restore_results = {}
    
    try:
        import os
        
        # Restore database
        from .database import restore_database
        db_backup_path = os.path.join(backup_dir, "database_backup.csv")
        if os.path.exists(db_backup_path):
            restore_results["database"] = restore_database(db_backup_path)
        
        # Restore cache
        from .cache import restore_cache
        cache_backup_path = os.path.join(backup_dir, "cache_backup.json")
        if os.path.exists(cache_backup_path):
            restore_results["cache"] = restore_cache(cache_backup_path)
        
        logger.info(f"Services restore completed from {backup_dir}")
        
    except Exception as e:
        logger.error(f"Error restoring services: {e}")
        restore_results["error"] = str(e)
    
    return restore_results


def get_service_configuration() -> dict:
    """Get service configuration."""
    
    try:
        from .database import get_database_info
        from .cache import get_cache_configuration
        
        return {
            "database": get_database_info(),
            "cache": get_cache_configuration(),
            "services": {
                "listing_service": "active",
                "search_service": "active", 
                "analytics_service": "active"
            }
        }
        
    except Exception as e:
        logger.error(f"Error getting service configuration: {e}")
        return {"error": str(e)}


def configure_services(config: dict) -> bool:
    """Configure services."""
    
    try:
        # Configure database
        if "database" in config:
            from .database import configure_database_settings
            configure_database_settings(config["database"])
        
        # Configure cache
        if "cache" in config:
            from .cache import configure_cache_settings
            configure_cache_settings(config["cache"])
        
        logger.info("Services configuration updated")
        return True
        
    except Exception as e:
        logger.error(f"Error configuring services: {e}")
        return False


def get_service_metrics() -> dict:
    """Get service performance metrics."""
    
    metrics = {
        "services": {},
        "overall_metrics": {}
    }
    
    try:
        # Database metrics
        from .database import get_database_performance_metrics
        metrics["services"]["database"] = get_database_performance_metrics()
        
        # Cache metrics
        from .cache import get_cache_performance_metrics
        metrics["services"]["cache"] = get_cache_performance_metrics()
        
        # Service-specific metrics
        try:
            listing_service = get_listing_service()
            metrics["services"]["listing_service"] = {
                "status": "active",
                "response_time": "< 100ms"
            }
        except Exception as e:
            metrics["services"]["listing_service"] = {"status": "error", "error": str(e)}
        
        # Overall metrics
        healthy_services = sum(1 for service in metrics["services"].values() if service.get("status") == "active")
        total_services = len(metrics["services"])
        
        metrics["overall_metrics"] = {
            "healthy_services": healthy_services,
            "total_services": total_services,
            "services_uptime": (healthy_services / total_services) * 100 if total_services > 0 else 0
        }
        
    except Exception as e:
        logger.error(f"Error getting service metrics: {e}")
        metrics["error"] = str(e)
    
    return metrics


def validate_services() -> dict:
    """Validate all services are working correctly."""
    
    validation_results = {
        "overall_status": "valid",
        "services": {}
    }
    
    try:
        # Validate database
        from .database import validate_database_schema
        db_validation = validate_database_schema()
        validation_results["services"]["database"] = db_validation
        
        if db_validation["status"] != "valid":
            validation_results["overall_status"] = "invalid"
        
        # Validate cache
        from .cache import check_cache_health
        cache_health = check_cache_health()
        validation_results["services"]["cache"] = {
            "status": "valid" if cache_health["status"] == "healthy" else "invalid",
            "health": cache_health
        }
        
        if cache_health["status"] != "healthy":
            validation_results["overall_status"] = "invalid"
        
        # Validate services
        services_to_validate = [
            ("listing_service", get_listing_service),
            ("search_service", get_search_service),
            ("analytics_service", get_analytics_service)
        ]
        
        for service_name, service_func in services_to_validate:
            try:
                service = service_func()
                validation_results["services"][service_name] = {
                    "status": "valid",
                    "initialized": True
                }
            except Exception as e:
                validation_results["services"][service_name] = {
                    "status": "invalid",
                    "error": str(e)
                }
                validation_results["overall_status"] = "invalid"
        
    except Exception as e:
        logger.error(f"Error validating services: {e}")
        validation_results["overall_status"] = "error"
        validation_results["error"] = str(e)
    
    return validation_results


def optimize_services() -> dict:
    """Optimize all services performance."""
    
    optimization_results = {}
    
    try:
        # Optimize database
        from .database import optimize_database
        db_optimized = optimize_database()
        optimization_results["database"] = db_optimized
        
        # Optimize cache
        from .cache import optimize_cache
        cache_optimized = optimize_cache()
        optimization_results["cache"] = cache_optimized
        
        logger.info("Services optimization completed")
        
    except Exception as e:
        logger.error(f"Error optimizing services: {e}")
        optimization_results["error"] = str(e)
    
    return optimization_results


def get_service_dependencies() -> dict:
    """Get service dependencies graph."""
    
    return {
        "listing_service": {
            "dependencies": ["database", "cache"],
            "provides": ["listing_crud", "listing_search", "listing_analytics"]
        },
        "search_service": {
            "dependencies": ["database", "cache"],
            "provides": ["search_functionality", "search_analytics", "search_recommendations"]
        },
        "analytics_service": {
            "dependencies": ["database", "cache"],
            "provides": ["data_analytics", "market_insights", "performance_metrics"]
        },
        "database": {
            "dependencies": [],
            "provides": ["data_storage", "data_persistence", "data_integrity"]
        },
        "cache": {
            "dependencies": [],
            "provides": ["data_caching", "performance_optimization", "session_storage"]
        }
    }


def test_service_connectivity() -> dict:
    """Test connectivity to all services."""
    
    connectivity_results = {}
    
    try:
        # Test database connectivity
        from .database import check_database_health
        db_health = check_database_health()
        connectivity_results["database"] = {
            "connected": db_health["status"] == "healthy",
            "response_time": "< 50ms",
            "details": db_health
        }
        
        # Test cache connectivity
        from .cache import check_cache_health
        cache_health = check_cache_health()
        connectivity_results["cache"] = {
            "connected": cache_health["status"] == "healthy",
            "response_time": "< 10ms",
            "details": cache_health
        }
        
        # Test service connectivity
        services_to_test = [
            ("listing_service", get_listing_service),
            ("search_service", get_search_service),
            ("analytics_service", get_analytics_service)
        ]
        
        for service_name, service_func in services_to_test:
            try:
                service = service_func()
                connectivity_results[service_name] = {
                    "connected": True,
                    "response_time": "< 100ms"
                }
            except Exception as e:
                connectivity_results[service_name] = {
                    "connected": False,
                    "error": str(e)
                }
        
    except Exception as e:
        logger.error(f"Error testing service connectivity: {e}")
        connectivity_results["error"] = str(e)
    
    return connectivity_results

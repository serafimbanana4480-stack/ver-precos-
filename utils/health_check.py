"""
Health check utilities for system monitoring
"""
from __future__ import annotations
import os
from datetime import datetime, timezone
from pathlib import Path
from typing import Dict, Any, Optional
from sqlalchemy import text
from database.db import get_db_context
from config import settings
from utils.logging_config import get_validation_health
import httpx


def check_ollama_health() -> Dict[str, Any]:
    """
    Check Ollama API health and verify required models
    
    Returns:
        Dictionary with Ollama status and details
    """
    if not settings.use_ollama:
        return {
            "status": "healthy",
            "message": "Ollama is disabled in configuration",
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "error": None
        }
        
    try:
        url = f"{settings.ollama_url}/api/tags"
        with httpx.Client(timeout=3.0) as client:
            response = client.get(url)
            
        if response.status_code == 200:
            models_data = response.json().get("models", [])
            model_names = [m.get("name") for m in models_data]
            
            if len(model_names) > 0:
                return {
                    "status": "healthy",
                    "models_available": model_names,
                    "timestamp": datetime.now(timezone.utc).isoformat(),
                    "error": None
                }
            else:
                return {
                    "status": "degraded",
                    "message": "Ollama is running but no models are pulled. Run: ollama pull qwen2.5-coder:7b",
                    "timestamp": datetime.now(timezone.utc).isoformat(),
                    "error": "No models found"
                }
        else:
            return {
                "status": "unhealthy",
                "message": f"Ollama returned HTTP {response.status_code}",
                "timestamp": datetime.now(timezone.utc).isoformat(),
                "error": f"HTTP {response.status_code}"
            }
    except Exception as e:
        return {
            "status": "unhealthy",
            "message": "Ollama is not responding. Ensure the Ollama service is running.",
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "error": str(e)
        }



def check_database_connection() -> Dict[str, Any]:
    """
    Check database connection health
    
    Returns:
        Dictionary with connection status and details
    """
    try:
        with get_db_context() as session:
            # Execute a simple query to test connection
            result = session.execute(text("SELECT 1"))
            result.fetchone()
            
            return {
                "status": "healthy",
                "database": settings.database_url.split("///")[0].split(":")[-1] if "sqlite" in settings.database_url else "postgresql",
                "timestamp": datetime.now(timezone.utc).isoformat(),
                "error": None
            }
    except Exception as e:
        return {
            "status": "unhealthy",
            "database": settings.database_url.split("///")[0].split(":")[-1] if "sqlite" in settings.database_url else "postgresql",
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "error": str(e)
        }


def check_configuration() -> Dict[str, Any]:
    """
    Check configuration validity
    
    Returns:
        Dictionary with configuration status and details
    """
    try:
        # Validate settings
        is_valid = settings.validate_config()
        
        # Check critical configuration
        critical_checks = {
            "database_url_configured": bool(settings.database_url),
            "log_level_valid": settings.log_level in ["DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"],
            "dashboard_port_valid": 1 <= settings.dashboard_port <= 65535,
        }
        
        all_critical_passed = all(critical_checks.values())
        
        return {
            "status": "healthy" if (is_valid and all_critical_passed) else "degraded",
            "valid": is_valid,
            "critical_checks": critical_checks,
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "error": None
        }
    except Exception as e:
        return {
            "status": "unhealthy",
            "valid": False,
            "critical_checks": {},
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "error": str(e)
        }


def check_log_file_writability() -> Dict[str, Any]:
    """
    Check if log file is writable
    
    Returns:
        Dictionary with log file status and details
    """
    try:
        # Ensure logs directory exists
        settings.logs_dir.mkdir(parents=True, exist_ok=True)
        
        # Try to write to log file
        log_file = Path(settings.log_file)
        test_file = log_file.parent / f".test_write_{os.getpid()}"
        
        with open(test_file, 'w') as f:
            f.write("test")
        
        # Clean up test file
        test_file.unlink()
        
        return {
            "status": "healthy",
            "log_file": str(log_file),
            "writable": True,
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "error": None
        }
    except Exception as e:
        return {
            "status": "unhealthy",
            "log_file": str(settings.log_file),
            "writable": False,
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "error": str(e)
        }


def get_system_health() -> Dict[str, Any]:
    """
    Get overall system health status
    
    Returns:
        Dictionary with overall health status and component details
    """
    # Check all components
    db_health = check_database_connection()
    config_health = check_configuration()
    log_health = check_log_file_writability()
    validation_health = get_validation_health()
    ollama_health = check_ollama_health()
    
    # Determine overall status
    component_statuses = [
        db_health["status"],
        config_health["status"],
        log_health["status"],
        ollama_health["status"]
    ]
    
    if "unhealthy" in component_statuses:
        overall_status = "unhealthy"
    elif "degraded" in component_statuses:
        overall_status = "degraded"
    else:
        overall_status = "healthy"
    
    return {
        "status": overall_status,
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "components": {
            "database": db_health,
            "configuration": config_health,
            "logging": log_health,
            "validation": validation_health,
            "ollama": ollama_health
        }
    }


def health_check_endpoint() -> Dict[str, Any]:
    """
    Health check endpoint response (for HTTP API)
    
    Returns:
        Dictionary suitable for HTTP JSON response
    """
    health = get_system_health()
    
    # Add HTTP-specific fields
    return {
        "status": health["status"],
        "timestamp": health["timestamp"],
        "components": {
            name: {
                "status": component["status"],
                "error": component.get("error")
            }
            for name, component in health["components"].items()
        }
    }

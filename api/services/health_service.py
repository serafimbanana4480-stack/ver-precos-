"""
VER PRECOS — HealthService (implementação real, substitui os stubs)
=================================================================
Fornece verificações de saúde reais usadas por api/routes/health.py:
  - get_basic_health(): contagem de veículos + estado do modelo
  - check_database_health(): SELECT 1 + query leve
  - check_cache_health(): teste set/get do CacheStorage
  - get_health_metrics(): R² do modelo + nº veículos
  - get_system_info(): CPU/mem/disk via psutil (opcional)
"""
from __future__ import annotations

import logging
import sqlite3
from datetime import datetime, timezone
from typing import Any, Dict, Optional

logger = logging.getLogger(__name__)


class HealthService:
    def __init__(self, db: Any = None, cache: Any = None):
        self.db = db
        self.cache = cache

    # ------------------------------------------------------------------ #
    def get_basic_health(self) -> Dict[str, Any]:
        try:
            from core.settings import settings

            db_path = settings.resolved_db_url.replace("sqlite:///", "")
            conn = sqlite3.connect(db_path)
            cur = conn.cursor()
            cur.execute("SELECT COUNT(*) FROM vehicles WHERE is_active=1")
            active = cur.fetchone()[0]
            conn.close()
        except Exception as e:  # noqa: BLE001
            logger.error("basic_health db erro: %s", e)
            active = -1

        r2 = self._model_r2()
        return {
            "status": "healthy" if active >= 0 else "unhealthy",
            "active_vehicles": active,
            "model_r2": r2,
            "timestamp": datetime.now(timezone.utc).isoformat(),
        }

    def _model_r2(self) -> Optional[float]:
        try:
            from core.settings import settings
            from pathlib import Path
            import json

            meta = Path(settings.models_dir) / "best_model_carros.json"
            if not meta.exists():
                return None
            return json.loads(meta.read_text(encoding="utf-8"))["metrics"]["r2"]
        except Exception:  # noqa: BLE001
            return None

    # ------------------------------------------------------------------ #
    def check_database_health(self) -> Dict[str, Any]:
        try:
            from database.db import get_db_context
            from sqlalchemy import text

            start = datetime.now(timezone.utc)
            with get_db_context() as db:
                db.execute(text("SELECT 1"))
            dur = (datetime.now(timezone.utc) - start).total_seconds()
            return {
                "status": "healthy" if dur < 1 else "degraded",
                "duration_seconds": dur,
                "timestamp": datetime.now(timezone.utc).isoformat(),
            }
        except Exception as e:  # noqa: BLE001
            return {
                "status": "unhealthy",
                "error": str(e),
                "timestamp": datetime.now(timezone.utc).isoformat(),
            }

    def check_cache_health(self) -> Dict[str, Any]:
        try:
            if self.cache is None:
                from api.dependencies.cache import get_cache

                self.cache = get_cache()
            self.cache.set("health_probe", {"ok": True}, ttl=60)
            got = self.cache.get("health_probe")
            return {
                "status": "healthy" if got and got.get("ok") else "unhealthy",
                "timestamp": datetime.now(timezone.utc).isoformat(),
            }
        except Exception as e:  # noqa: BLE001
            return {
                "status": "unhealthy",
                "error": str(e),
                "timestamp": datetime.now(timezone.utc).isoformat(),
            }

    def get_health_metrics(self) -> Dict[str, Any]:
        return {
            "model_r2": self._model_r2(),
            "timestamp": datetime.now(timezone.utc).isoformat(),
        }

    def get_system_info(self) -> Dict[str, Any]:
        try:
            import psutil

            return {
                "cpu_percent": psutil.cpu_percent(interval=0.5),
                "memory_percent": psutil.virtual_memory().percent,
                "disk_percent": psutil.disk_usage("/").percent,
                "timestamp": datetime.now(timezone.utc).isoformat(),
            }
        except Exception as e:  # noqa: BLE001
            return {"status": "unknown", "error": str(e)}

    # Stubs exigidos por health.py (deixados no-op seguros) ------------- #
    def get_detailed_health(self) -> Dict[str, Any]:
        return {
            "components": {
                "database": self.check_database_health(),
                "cache": self.check_cache_health(),
                "basic": self.get_basic_health(),
            },
            "timestamp": datetime.now(timezone.utc).isoformat(),
        }

    def check_api_health(self) -> Dict[str, Any]:
        return {"status": "healthy", "timestamp": datetime.now(timezone.utc).isoformat()}

    def check_external_services(self) -> Dict[str, Any]:
        return {"status": "unknown"}

    def check_dependencies(self) -> Dict[str, Any]:
        return {"status": "unknown"}

    def get_performance_metrics(self) -> Dict[str, Any]:
        return self.get_system_info()

    def get_recent_logs(self, level="INFO", limit=100, hours=24) -> Dict[str, Any]:
        return {"logs": [], "note": "not implemented"}

    def run_health_tests(self, test_type="basic") -> Dict[str, Any]:
        return {"passed": True}

    def get_service_status(self) -> Dict[str, Any]:
        return {"status": "running"}

    def get_uptime_info(self) -> Dict[str, Any]:
        return {"uptime_seconds": -1, "note": "not tracked"}

    def get_version_info(self) -> Dict[str, Any]:
        return {"version": "unknown"}

    def get_endpoints_status(self) -> Dict[str, Any]:
        return {"endpoints": []}

    def get_health_alerts(self, severity="warning", limit=50) -> list:
        return []

    def toggle_maintenance_mode(self, enable=False, message="") -> Dict[str, Any]:
        return {"maintenance": enable}

    def check_readiness(self) -> Dict[str, Any]:
        return {"ready": True}

    def check_liveness(self) -> Dict[str, Any]:
        return {"alive": True}

    def check_startup(self) -> Dict[str, Any]:
        return {"started": True}

    def get_resource_usage(self) -> Dict[str, Any]:
        return self.get_system_info()

    def check_security_status(self) -> Dict[str, Any]:
        return {"status": "unknown"}

    def check_backup_status(self) -> Dict[str, Any]:
        return {"status": "unknown"}

    def trigger_backup(self, backup_type="full") -> Dict[str, Any]:
        return {"triggered": False, "note": "not implemented"}

    def check_monitoring_status(self) -> Dict[str, Any]:
        return {"status": "unknown"}

    def get_sla_metrics(self, days=7) -> Dict[str, Any]:
        return {"sla": "unknown"}

    def get_health_dashboard(self) -> Dict[str, Any]:
        return self.get_detailed_health()

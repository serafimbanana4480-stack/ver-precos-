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
import json
import os
import importlib
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any, Callable, Dict, Iterable, Mapping, Optional

logger = logging.getLogger(__name__)

PROJECT_ROOT = Path(__file__).resolve().parents[2]
DEFAULT_LIVE_SCRAPE_REPORT = PROJECT_ROOT / "reports" / "scrape_last_run.json"
_WARNING_STATUSES = {"warning", "degraded", "not_measured", "unknown"}


def _as_utc(value: Any) -> Optional[datetime]:
    """Parse a persisted timestamp without inventing a measurement."""
    if isinstance(value, datetime):
        parsed = value
    elif isinstance(value, str) and value.strip():
        try:
            parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
        except ValueError:
            return None
    else:
        return None
    return parsed.replace(tzinfo=timezone.utc) if parsed.tzinfo is None else parsed.astimezone(timezone.utc)


class HealthService:
    def __init__(
        self,
        db: Any = None,
        cache: Any = None,
        live_report_path: Optional[str | Path] = None,
        clock: Optional[Callable[[], datetime]] = None,
    ):
        self.db = db
        self.cache = cache
        self.live_report_path = Path(live_report_path) if live_report_path else DEFAULT_LIVE_SCRAPE_REPORT
        self._clock = clock

    def _now(self) -> datetime:
        now = self._clock() if self._clock else datetime.now(timezone.utc)
        return now.replace(tzinfo=timezone.utc) if now.tzinfo is None else now.astimezone(timezone.utc)

    @staticmethod
    def aggregate_status(results: Iterable[Mapping[str, Any]]) -> str:
        """Aggregate health without collapsing warning/not-measured into failure."""
        statuses = {str(result.get("status", "unknown")) for result in results}
        if "unhealthy" in statuses:
            return "unhealthy"
        if statuses & _WARNING_STATUSES:
            return "warning"
        return "healthy" if statuses and statuses <= {"healthy", "disabled", "not_configured"} else "unknown"

    # ------------------------------------------------------------------ #
    def get_basic_health(self) -> Dict[str, Any]:
        active = self._active_vehicle_count()

        r2 = self._model_r2()
        models = self.check_model_artifacts()
        freshness = self.check_data_freshness()
        status = self.aggregate_status([
            {"status": "healthy" if active >= 0 else "unhealthy"},
            models,
            freshness,
        ])
        return {
            "status": status,
            "active_vehicles": active,
            "model_r2": r2,
            "models": models,
            "freshness": freshness,
            "timestamp": datetime.now(timezone.utc).isoformat(),
        }

    def _active_vehicle_count(self) -> int:
        """Count active vehicles through the configured SQLAlchemy backend.

        The previous implementation opened a SQLite connection directly,
        which reported a false failure whenever production used PostgreSQL.
        """
        try:
            from database.db import get_db_context
            from sqlalchemy import text

            with get_db_context() as db:
                result = db.execute(text("SELECT COUNT(*) FROM vehicles WHERE is_active = 1"))
                return int(result.scalar_one())
        except Exception as e:  # noqa: BLE001
            logger.error("basic_health db erro: %s", e)
            return -1

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
            from database.db import database_integrity_check, get_db_context
            from sqlalchemy import text

            start = datetime.now(timezone.utc)
            with get_db_context() as db:
                db.execute(text("SELECT 1"))
            dur = (datetime.now(timezone.utc) - start).total_seconds()
            integrity = database_integrity_check()
            integrity_ok = integrity.get("status") in ("healthy", "not_applicable")
            return {
                "status": (
                    "healthy"
                    if dur < 1 and integrity_ok
                    else "degraded" if integrity_ok else "unhealthy"
                ),
                "duration_seconds": dur,
                "integrity": integrity,
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
            "models": self.check_model_artifacts(),
            "timestamp": datetime.now(timezone.utc).isoformat(),
        }

    def check_model_artifacts(self) -> Dict[str, Any]:
        """Verify that every declared production model artifact is present.

        Metadata alone is not a usable model.  This check deliberately fails
        closed when a referenced model, scaler, or category index is absent,
        so a service cannot advertise healthy ML while silently falling back
        to non-ML valuation.
        """
        try:
            from core.settings import settings

            model_dir = Path(settings.models_dir)
            model_root = model_dir.resolve()
            models: Dict[str, Any] = {}
            missing = []
            invalid = []
            for vehicle_type in ("carros", "motos"):
                metadata_path = model_dir / f"best_model_{vehicle_type}.json"
                entry: Dict[str, Any] = {"metadata": str(metadata_path), "status": "healthy"}
                if not metadata_path.exists():
                    entry.update(status="unhealthy", error="metadata_missing")
                    missing.append(f"{vehicle_type}:metadata")
                    models[vehicle_type] = entry
                    continue
                try:
                    metadata = json.loads(metadata_path.read_text(encoding="utf-8"))
                except Exception as e:  # noqa: BLE001
                    entry.update(status="unhealthy", error=f"metadata_invalid:{type(e).__name__}")
                    missing.append(f"{vehicle_type}:metadata_invalid")
                    models[vehicle_type] = entry
                    continue

                required = {
                    "model": metadata.get("model_path"),
                    "scaler": metadata.get("scaler_path"),
                    "brand_index": metadata.get("brand_index_path"),
                }
                entry["model_type"] = metadata.get("model_type")
                entry["files"] = {}
                absent = []
                for label, relative in required.items():
                    path = model_dir / str(relative) if relative else None
                    safe_path = False
                    if path is not None:
                        try:
                            path.resolve().relative_to(model_root)
                            safe_path = True
                        except ValueError:
                            safe_path = False
                    exists = bool(safe_path and path and path.is_file())
                    nonempty = bool(exists and path.stat().st_size > 0)
                    entry["files"][label] = {
                        "path": str(path) if path else None,
                        "exists": exists,
                        "nonempty": nonempty,
                    }
                    if not exists:
                        absent.append(label)
                        missing.append(f"{vehicle_type}:{label}")
                    elif not nonempty:
                        invalid.append(f"{vehicle_type}:{label}:empty")
                brand_path = model_dir / str(required["brand_index"]) if required["brand_index"] else None
                brand_safe = False
                if brand_path:
                    try:
                        brand_path.resolve().relative_to(model_root)
                        brand_safe = True
                    except ValueError:
                        brand_safe = False
                if brand_safe and brand_path and brand_path.is_file() and brand_path.stat().st_size > 0:
                    try:
                        if not isinstance(json.loads(brand_path.read_text(encoding="utf-8")), dict):
                            invalid.append(f"{vehicle_type}:brand_index:not_object")
                    except Exception as e:  # noqa: BLE001
                        invalid.append(f"{vehicle_type}:brand_index:invalid_json:{type(e).__name__}")
                if absent:
                    entry.update(status="unhealthy", error="artifact_missing", missing=absent)
                elif any(item.startswith(f"{vehicle_type}:") for item in invalid):
                    entry.update(status="unhealthy", error="artifact_invalid")
                models[vehicle_type] = entry

            return {
                "status": "healthy" if not missing and not invalid else "unhealthy",
                "missing": missing,
                "invalid": invalid,
                "models": models,
            }
        except Exception as e:  # noqa: BLE001
            logger.exception("model artifact health check failed")
            return {"status": "unhealthy", "error": str(e), "models": {}}

    def check_data_freshness(self, max_age_hours: int = 48) -> Dict[str, Any]:
        """Measure whether active inventory has been observed recently.

        This is deliberately read-only.  Stale rows are reported and block
        readiness, but are never silently deactivated by a health endpoint.
        """
        if max_age_hours < 1:
            return {
                "status": "unhealthy",
                "error": "max_age_hours_must_be_positive",
                "max_age_hours": max_age_hours,
                "checked_at": datetime.now(timezone.utc).isoformat(),
            }
        try:
            from database.db import get_db_context
            from database.models import Vehicle

            cutoff = datetime.now(timezone.utc).timestamp() - (max_age_hours * 3600)
            with get_db_context() as db:
                rows = db.query(Vehicle.last_seen).filter(Vehicle.is_active.is_(True)).all()

            total = len(rows)
            missing = 0
            stale = 0
            latest = None
            for (last_seen,) in rows:
                if last_seen is None:
                    missing += 1
                    continue
                current = last_seen
                if current.tzinfo is None:
                    current = current.replace(tzinfo=timezone.utc)
                if latest is None or current > latest:
                    latest = current
                if current.timestamp() < cutoff:
                    stale += 1

            stale_ratio = (stale / total) if total else 1.0
            if total == 0:
                status = "degraded"
            elif missing or stale_ratio >= 0.5:
                status = "unhealthy"
            elif stale or stale_ratio > 0:
                status = "degraded"
            else:
                status = "healthy"
            return {
                "status": status,
                "active_total": total,
                "stale_count": stale,
                "missing_last_seen": missing,
                "stale_ratio": round(stale_ratio, 4),
                "max_age_hours": max_age_hours,
                "latest_seen": latest.isoformat() if latest else None,
                "checked_at": datetime.now(timezone.utc).isoformat(),
            }
        except Exception as e:  # noqa: BLE001
            logger.exception("data freshness check failed")
            return {
                "status": "unhealthy",
                "error": str(e),
                "checked_at": datetime.now(timezone.utc).isoformat(),
            }

    def check_scraper_registry(self, *, include_live: bool = False) -> Dict[str, Any]:
        """Validate configured scraper dispatch without making network calls.

        A registry check proves that a source is configured and importable; it
        does not prove that the remote site is reachable or that its parser is
        currently returning listings.  That runtime health is intentionally
        exposed separately as ``live_health=not_measured`` until a scrape run
        persists a real result.
        """
        try:
            from scrapers.registry import build_registry_report

            report = build_registry_report()
            entries = report.get("sources", [])
            invalid = report.get("invalid_sources", [])
            # The default registry contract is importability-only.  Health and
            # readiness may explicitly opt into the durable live result.
            live = self.check_live_scraper_health() if include_live else self._not_measured_live("registry_only")
            live_sources = live.get("sources", {})
            for entry in entries:
                if not isinstance(entry, dict):
                    continue
                dispatch_name = str(entry.get("dispatch_name", ""))
                source_live = live_sources.get(dispatch_name)
                if source_live is None:
                    source_live = live_sources.get(f"{dispatch_name}:carros")
                entry["live_status"] = (
                    source_live.get("status", "not_measured")
                    if isinstance(source_live, dict)
                    else "not_measured"
                )
            return {
                "status": "healthy" if report.get("status") == "healthy" else "unhealthy",
                "registry_status": "healthy" if report.get("status") == "healthy" else "unhealthy",
                "configured_sources": len(entries),
                "invalid_sources": invalid,
                "live_health": live["live_health"],
                "live_status": live["live_status"],
                "registry": report,
                "live": live,
                "checked_at": datetime.now(timezone.utc).isoformat(),
            }
        except Exception as e:  # noqa: BLE001
            logger.exception("scraper registry health check failed")
            return {
                "status": "unhealthy",
                "registry_status": "unhealthy",
                "configured_sources": 0,
                "invalid_sources": [],
                "live_health": "not_measured",
                "live_status": "not_measured",
                "live": self._not_measured_live("registry_check_failed"),
                "error": f"{type(e).__name__}: {e}",
                "checked_at": datetime.now(timezone.utc).isoformat(),
            }

    def _not_measured_live(self, reason: str, *, path: Optional[Path] = None) -> Dict[str, Any]:
        return {
            "status": "not_measured",
            "live_health": "not_measured",
            "live_status": "not_measured",
            "measured": False,
            "reason": reason,
            "report_path": str(path or self.live_report_path),
            "sources": {},
            "healthy_sources": [],
            "failed_sources": [],
        }

    def check_live_scraper_health(
        self,
        report_path: Optional[str | Path] = None,
        *,
        report: Optional[Mapping[str, Any]] = None,
        max_age_hours: int = 48,
    ) -> Dict[str, Any]:
        """Read a durable runner result; never probes remote sources.

        ``live_health`` is ``measured`` only when a valid, fresh runner report
        exists.  A registry import or an empty source result is not a live
        measurement.  This method is intentionally read-only so health probes
        cannot mutate the operational database or contact external services.
        """
        path = Path(report_path) if report_path else self.live_report_path
        if report is None:
            try:
                report = json.loads(path.read_text(encoding="utf-8"))
            except FileNotFoundError:
                return self._not_measured_live("report_missing", path=path)
            except (OSError, json.JSONDecodeError, TypeError) as exc:
                return self._not_measured_live(f"report_invalid:{type(exc).__name__}", path=path)

        if not isinstance(report, Mapping) or max_age_hours < 1:
            return self._not_measured_live("report_invalid" if isinstance(report, Mapping) is False else "max_age_hours_invalid", path=path)

        finished_at = _as_utc(report.get("finished_at"))
        if finished_at is None:
            return self._not_measured_live("finished_at_missing", path=path)
        age_seconds = (self._now() - finished_at).total_seconds()
        if age_seconds < -300 or age_seconds > max_age_hours * 3600:
            stale = self._not_measured_live("report_stale", path=path)
            stale.update({"measured_at": finished_at.isoformat(), "age_seconds": max(0.0, age_seconds)})
            return stale

        raw_sources = report.get("scrapers")
        if not isinstance(raw_sources, Mapping) or not raw_sources:
            return self._not_measured_live("source_results_missing", path=path)

        sources: Dict[str, Dict[str, Any]] = {}
        healthy_sources: list[str] = []
        failed_sources: list[str] = []
        for name, raw in raw_sources.items():
            key = str(name)
            if not isinstance(raw, Mapping):
                sources[key] = {"status": "unhealthy", "source_state": "invalid", "error": "invalid_source_result"}
                failed_sources.append(key)
                continue
            errors = raw.get("errors")
            has_errors = isinstance(errors, (list, tuple, set)) and bool(errors)
            success = raw.get("success") is True and not has_errors
            count = raw.get("count")
            has_observations = isinstance(count, (int, float)) and count > 0
            source_status = "healthy" if success else "warning" if has_observations else "unhealthy"
            source_entry = {
                "status": source_status,
                "source_state": raw.get("status") or ("ok" if success else "failed"),
                "success": bool(success),
                "count": count,
                "errors": list(errors) if isinstance(errors, (list, tuple)) else ([] if not errors else [str(errors)]),
            }
            sources[key] = source_entry
            if source_status == "healthy":
                healthy_sources.append(key)
            else:
                failed_sources.append(key)

        declared_failed = report.get("failed_sources")
        if isinstance(declared_failed, list):
            failed_sources = sorted(set(failed_sources).union(str(item) for item in declared_failed))
        overall_success = report.get("overall_success") is True
        if not failed_sources and overall_success:
            live_status = "healthy"
        elif healthy_sources:
            live_status = "warning"
        else:
            live_status = "unhealthy"
        return {
            "status": live_status,
            "live_health": "measured",
            "live_status": live_status,
            "measured": True,
            "measured_at": finished_at.isoformat(),
            "age_seconds": max(0.0, age_seconds),
            "report_path": str(path),
            "overall_success": overall_success,
            "sources": sources,
            "healthy_sources": sorted(healthy_sources),
            "failed_sources": sorted(set(failed_sources)),
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
        external = self.check_external_services(probe=False)
        return {
            "components": {
                "database": self.check_database_health(),
                "cache": self.check_cache_health(),
                "models": self.check_model_artifacts(),
                "freshness": self.check_data_freshness(),
                "scrapers": self.check_scraper_registry(include_live=True),
                "external": external,
                "basic": self.get_basic_health(),
            },
            "overall_status": self.aggregate_status([]),
            "timestamp": datetime.now(timezone.utc).isoformat(),
        }

    def check_api_health(self) -> Dict[str, Any]:
        database = self.check_database_health()
        models = self.check_model_artifacts()
        freshness = self.check_data_freshness()
        scrapers = self.check_scraper_registry(include_live=True)
        external = self.check_external_services(probe=False)
        status = "healthy" if (
            database["status"] == "healthy"
            and models["status"] == "healthy"
            and freshness["status"] == "healthy"
            and scrapers["status"] == "healthy"
        ) else "unhealthy"
        return {
            "status": status,
            "database": database,
            "models": models,
            "freshness": freshness,
            "scrapers": scrapers,
            "external": external,
            "status_detail": self.aggregate_status([database, models, freshness, scrapers]),
            "timestamp": datetime.now(timezone.utc).isoformat(),
        }

    def check_external_services(self, *, probe: bool = False) -> Dict[str, Any]:
        try:
            from core.settings import settings

            if not settings.use_ollama:
                return {
                    "status": "healthy",
                    "ollama": {"status": "disabled", "configured": False},
                    "checked_at": datetime.now(timezone.utc).isoformat(),
                }
            if not probe:
                return {
                    "status": "warning",
                    "ollama": {
                        "status": "not_measured",
                        "configured": True,
                        "url": settings.ollama_url,
                    },
                    "live_health": "not_measured",
                    "probe_performed": False,
                    "checked_at": datetime.now(timezone.utc).isoformat(),
                }
            available = settings.check_ollama_available()
            return {
                "status": "healthy" if available else "degraded",
                "ollama": {
                    "status": "healthy" if available else "unavailable",
                    "configured": True,
                    "url": settings.ollama_url,
                },
                "live_health": "measured",
                "probe_performed": True,
                "checked_at": datetime.now(timezone.utc).isoformat(),
            }
        except Exception as e:  # noqa: BLE001
            return {
                "status": "unhealthy",
                "error": type(e).__name__,
                "checked_at": datetime.now(timezone.utc).isoformat(),
            }

    def check_dependencies(self) -> Dict[str, Any]:
        required = ("fastapi", "sqlalchemy", "pydantic")
        optional = ("xgboost", "sklearn", "requests")

        def probe(names):
            result = {}
            for name in names:
                try:
                    importlib.import_module(name)
                    result[name] = "available"
                except Exception as e:  # noqa: BLE001
                    result[name] = f"unavailable:{type(e).__name__}"
            return result

        required_status = probe(required)
        optional_status = probe(optional)
        missing_required = [name for name, status in required_status.items() if status != "available"]
        missing_optional = [name for name, status in optional_status.items() if status != "available"]
        models = self.check_model_artifacts()
        model_status = models.get("status")
        return {
            "status": (
                "unhealthy"
                if missing_required or model_status != "healthy"
                else ("degraded" if missing_optional else "healthy")
            ),
            "required": required_status,
            "optional": optional_status,
            "missing_required": missing_required,
            "missing_optional": missing_optional,
            "models": models,
        }

    def get_performance_metrics(self) -> Dict[str, Any]:
        return self.get_system_info()

    def get_recent_logs(self, level="INFO", limit=100, hours=24) -> Dict[str, Any]:
        return {
            "status": "not_measured",
            "logs": [],
            "level": level,
            "limit": limit,
            "hours": hours,
            "note": "structured log query is not wired to this legacy endpoint",
        }

    def run_health_tests(self, test_type="basic") -> Dict[str, Any]:
        checks = {
            "database": self.check_database_health(),
            "models": self.check_model_artifacts(),
            "freshness": self.check_data_freshness(),
        }
        if test_type != "basic":
            checks["cache"] = self.check_cache_health()
        failed = [name for name, result in checks.items() if result.get("status") != "healthy"]
        return {
            "passed": not failed,
            "status": "healthy" if not failed else "unhealthy",
            "failed_checks": failed,
            "checks": checks,
        }

    def get_service_status(self) -> Dict[str, Any]:
        return {"status": "running", "liveness": True}

    def get_uptime_info(self) -> Dict[str, Any]:
        try:
            import psutil

            started = datetime.fromtimestamp(psutil.Process().create_time(), timezone.utc)
            return {
                "uptime_seconds": max(0.0, (datetime.now(timezone.utc) - started).total_seconds()),
                "started_at": started.isoformat(),
            }
        except Exception as e:  # noqa: BLE001
            return {"uptime_seconds": None, "status": "not_measured", "error": type(e).__name__}

    def get_version_info(self) -> Dict[str, Any]:
        try:
            from config.base import config

            return {
                "version": config.APP_VERSION,
                "api_version": "v1",
                "environment": os.getenv("ENV", "development"),
                "source": "config.base",
            }
        except Exception as e:  # noqa: BLE001
            return {"version": None, "status": "not_measured", "error": type(e).__name__}

    def get_endpoints_status(self) -> list:
        """Return the currently registered canonical FastAPI routes."""
        try:
            from app.api.main import app

            endpoints = []
            for route in app.routes:
                path = getattr(route, "path", None)
                methods = sorted(getattr(route, "methods", set()))
                if path and methods:
                    endpoints.append({"path": path, "methods": methods, "status": "registered"})
            return endpoints
        except Exception as e:  # noqa: BLE001
            logger.warning("endpoint inventory unavailable: %s", e)
            return [{"status": "not_measured", "error": type(e).__name__}]

    def get_health_alerts(self, severity="warning", limit=50) -> list:
        alerts = []
        health = self.check_api_health()
        for component in ("database", "models", "freshness", "scrapers"):
            result = health.get(component, {})
            if result.get("status") != "healthy":
                alerts.append({
                    "severity": "critical" if result.get("status") == "unhealthy" else "warning",
                    "component": component,
                    "status": result.get("status"),
                    "details": result,
                })
        live = health.get("scrapers", {}).get("live", {})
        if live.get("live_status") not in (None, "healthy"):
            alerts.append({
                "severity": "critical" if live.get("live_status") == "unhealthy" else "warning",
                "component": "scrapers_live",
                "status": live.get("live_status", "not_measured"),
                "details": live,
            })
        return alerts[: max(0, limit)]

    def toggle_maintenance_mode(self, enable=False, message="") -> Dict[str, Any]:
        return {
            "status": "not_configured",
            "maintenance": None,
            "requested": bool(enable),
            "message": message,
            "note": "maintenance state is not persisted by this legacy endpoint",
        }

    def check_readiness(self) -> Dict[str, Any]:
        database = self.check_database_health()
        models = self.check_model_artifacts()
        freshness = self.check_data_freshness()
        scrapers = self.check_scraper_registry(include_live=True)
        core_ready = (
            database["status"] == "healthy"
            and models["status"] == "healthy"
            and freshness["status"] == "healthy"
            and scrapers["status"] == "healthy"
        )
        live_status = scrapers.get("live_status", "not_measured")
        live_ready = scrapers.get("live_health") == "measured" and live_status == "healthy"
        ready = core_ready and live_ready
        blocking_reasons = []
        for name, result in (("database", database), ("models", models), ("freshness", freshness), ("scrapers_registry", scrapers)):
            if result.get("status") != "healthy":
                blocking_reasons.append(name)
        if not live_ready:
            blocking_reasons.append(f"scrapers_live:{live_status}")
        status = "healthy" if ready else (
            "unhealthy" if any(result.get("status") == "unhealthy" for result in (database, models, freshness, scrapers)) else "warning"
        )
        return {
            "ready": ready,
            "status": status,
            "core_ready": core_ready,
            "live_ready": live_ready,
            "blocking_reasons": blocking_reasons,
            "database": database,
            "models": models,
            "freshness": freshness,
            "scrapers": scrapers,
            "live_health": scrapers.get("live_health", "not_measured"),
            "live_status": live_status,
            "timestamp": datetime.now(timezone.utc).isoformat(),
        }

    def check_liveness(self) -> Dict[str, Any]:
        return {"alive": True}

    def check_startup(self) -> Dict[str, Any]:
        return {"started": True}

    def get_resource_usage(self) -> Dict[str, Any]:
        return self.get_system_info()

    def get_environment_info(self) -> Dict[str, Any]:
        """Expose non-secret runtime configuration facts for diagnostics."""
        try:
            from core.settings import settings

            return {
                "environment": settings.env,
                "database": "sqlite" if settings.use_sqlite else ("postgresql" if settings.use_postgresql else "other"),
                "ai_enabled": settings.use_ollama,
                "scraping_enabled": settings.ai_scraping_enabled,
                "model_directory": str(Path(settings.models_dir)),
                "timestamp": datetime.now(timezone.utc).isoformat(),
            }
        except Exception as e:  # noqa: BLE001
            return {"status": "unhealthy", "error": type(e).__name__}

    def check_security_status(self) -> Dict[str, Any]:
        try:
            from core.settings import settings

            secret_configured = bool((settings.jwt_secret or os.getenv("JWT_SECRET", "")).strip())
            cors_safe = "*" not in settings.cors_origins_list
            production_secret_ok = not settings.is_production or secret_configured
            checks = {
                "jwt_secret_configured": secret_configured,
                "production_secret_ok": production_secret_ok,
                "cors_origins_explicit": cors_safe,
            }
            failed = [name for name, value in checks.items() if not value]
            return {
                "status": "healthy" if not failed else "unhealthy",
                "checks": checks,
                "failed_checks": failed,
            }
        except Exception as e:  # noqa: BLE001
            return {"status": "unhealthy", "error": type(e).__name__}

    def check_backup_status(self) -> Dict[str, Any]:
        try:
            from core.settings import settings

            backup_dir = Path(settings.data_dir) / "backups"
            files = sorted(
                (path for path in backup_dir.glob("*") if path.is_file()),
                key=lambda path: path.stat().st_mtime,
                reverse=True,
            ) if backup_dir.exists() else []
            return {
                "status": "configured" if files else "not_configured",
                "configured": bool(files),
                "backup_count": len(files),
                "latest_backup": str(files[0]) if files else None,
            }
        except Exception as e:  # noqa: BLE001
            return {"status": "unhealthy", "error": type(e).__name__}

    def trigger_backup(self, backup_type="full") -> Dict[str, Any]:
        return {
            "status": "not_implemented",
            "triggered": False,
            "backup_type": backup_type,
            "note": "backup execution requires an explicit durable backend",
        }

    def check_monitoring_status(self) -> Dict[str, Any]:
        return {
            "status": "configured",
            "metrics_endpoint": "/metrics",
            "structured_logging": True,
            "alert_delivery": "not_configured",
        }

    def get_sla_metrics(self, days=7) -> Dict[str, Any]:
        return {
            "status": "not_measured",
            "days": days,
            "availability": None,
            "error_rate": None,
            "latency_p95_seconds": None,
        }

    def get_health_dashboard(self) -> Dict[str, Any]:
        return self.get_detailed_health()

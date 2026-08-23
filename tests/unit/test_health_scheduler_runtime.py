"""Focused contracts for read-only health and bounded scheduler runtime."""

from __future__ import annotations

import asyncio
import json
import threading
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timedelta, timezone
from pathlib import Path


def _registry_report() -> dict:
    return {
        "status": "healthy",
        "invalid_sources": [],
        "sources": [
            {
                "dispatch_name": "example",
                "source": "EXAMPLE",
                "implementation_exists": True,
                "dispatchable": True,
                "healthy": "not_measured",
            }
        ],
    }


def test_registry_is_importability_only_and_live_is_explicit(tmp_path, monkeypatch):
    from api.services.health_service import HealthService

    report_path = tmp_path / "scrape_last_run.json"
    now = datetime.now(timezone.utc)
    report_path.write_text(
        json.dumps(
            {
                "finished_at": now.isoformat(),
                "overall_success": False,
                "failed_sources": ["example:carros"],
                "scrapers": {
                    "example:carros": {"success": False, "count": 3, "errors": ["blocked"]},
                    "other:carros": {"success": True, "count": 2, "errors": []},
                },
            }
        ),
        encoding="utf-8",
    )
    monkeypatch.setattr("scrapers.registry.build_registry_report", _registry_report)
    service = HealthService(live_report_path=report_path, clock=lambda: now)

    registry = service.check_scraper_registry()
    assert registry["status"] == "healthy"
    assert registry["live_health"] == "not_measured"
    assert registry["live_status"] == "not_measured"
    assert registry["registry"]["sources"][0]["healthy"] == "not_measured"

    measured = service.check_scraper_registry(include_live=True)
    assert measured["live_health"] == "measured"
    assert measured["live_status"] == "warning"
    assert measured["live"]["failed_sources"]


def test_stale_live_report_does_not_make_readiness_ready(tmp_path):
    from api.services.health_service import HealthService

    now = datetime.now(timezone.utc)
    service = HealthService(live_report_path=tmp_path / "missing.json", clock=lambda: now)
    service.check_database_health = lambda: {"status": "healthy"}  # type: ignore[method-assign]
    service.check_model_artifacts = lambda: {"status": "healthy"}  # type: ignore[method-assign]
    service.check_data_freshness = lambda: {"status": "healthy"}  # type: ignore[method-assign]
    service.check_scraper_registry = lambda **_: {  # type: ignore[method-assign]
        "status": "healthy",
        "live_health": "not_measured",
        "live_status": "not_measured",
        "live": {"live_status": "not_measured"},
    }

    readiness = service.check_readiness()
    assert readiness["ready"] is False
    assert readiness["status"] == "warning"
    assert readiness["live_ready"] is False
    assert "scrapers_live:not_measured" in readiness["blocking_reasons"]


def test_ollama_health_does_not_probe_by_default(monkeypatch):
    from utils import health_check

    monkeypatch.setattr(health_check.settings, "use_ollama", True)

    class UnexpectedClient:
        def __init__(self, *args, **kwargs):  # pragma: no cover - should never run
            raise AssertionError("health must not make an implicit external probe")

    monkeypatch.setattr(health_check.httpx, "Client", UnexpectedClient)
    result = health_check.check_ollama_health()
    assert result["status"] == "not_measured"
    assert result["measured"] is False


def test_scheduler_lease_allows_one_concurrent_owner(tmp_path):
    from scheduler.daily_job import SchedulerLease

    path = tmp_path / "scheduler.lease.json"
    barrier = threading.Barrier(8)

    def attempt(index: int) -> bool:
        lease = SchedulerLease(path, owner_id=f"worker-{index}", lease_seconds=2, heartbeat_timeout=2)
        barrier.wait()
        acquired = lease.acquire()
        barrier.wait()
        if acquired:
            lease.heartbeat()
            lease.release()
        return acquired

    with ThreadPoolExecutor(max_workers=8) as pool:
        results = list(pool.map(attempt, range(8)))

    assert sum(results) == 1
    assert not path.exists()


def test_scheduler_lease_recovers_expired_orphan_and_heartbeats(tmp_path):
    from scheduler.daily_job import SchedulerLease

    path = tmp_path / "orphan.lease.json"
    old = (datetime.now(timezone.utc) - timedelta(minutes=5)).isoformat()
    path.write_text(
        json.dumps(
            {
                "owner_id": "dead-worker",
                "pid": 999999999,
                "token": "dead-token",
                "heartbeat_at": old,
                "lease_until": old,
            }
        ),
        encoding="utf-8",
    )

    lease = SchedulerLease(path, owner_id="recovery", lease_seconds=2, heartbeat_timeout=2)
    assert lease.recover_orphan() is True
    assert lease.acquire() is True
    snapshot = lease.snapshot()
    assert snapshot and snapshot["owner_id"] == "recovery"
    assert lease.heartbeat() is True
    assert lease.release() is True
    assert not path.exists()


def test_daily_job_dry_run_is_not_success_and_real_path_is_explicit(tmp_path, monkeypatch):
    from scheduler.daily_job import DailyJob

    job = DailyJob(lease_path=tmp_path / "daily.lease.json")
    dry = asyncio.run(job.run())
    assert dry["status"] == "dry_run"
    assert dry["success"] is False
    assert dry["executed_contract"] is False

    called = []

    def fake_scrape(*, dry_run=False, send_notifications=True):
        called.append((dry_run, send_notifications))
        return {
            "status": "completed",
            "success": True,
            "executed": True,
            "executed_contract": True,
        }

    monkeypatch.setattr(job, "run_scraping_job", fake_scrape)
    real = asyncio.run(job.run(dry_run=False))
    assert real["success"] is True
    assert called == [(False, False)]


def test_autonomous_dry_run_skips_real_runner_and_alert(monkeypatch, tmp_path):
    import scheduler.autonomous as autonomous

    monkeypatch.setattr(autonomous, "_run", lambda *_: (_ for _ in ()).throw(AssertionError("runner called")))
    monkeypatch.setattr(autonomous, "_alert", lambda *_: (_ for _ in ()).throw(AssertionError("alert sent")))
    result = autonomous.job_scrape(
        dry_run=True,
        send_alerts=True,
        lease_path=tmp_path / "autonomous.lease.json",
    )
    assert result["status"] == "dry_run"
    assert result["success"] is False
    assert result["executed_contract"] is False

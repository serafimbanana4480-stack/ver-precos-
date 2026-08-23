"""
Daily job scheduler for automated scraping, analysis, and watchlist checking
"""
from __future__ import annotations
import json
import logging
import asyncio
import os
import secrets
import socket
import threading
import time as time_module
from datetime import datetime, time, timezone
from pathlib import Path
from typing import Any, Callable, Dict, Mapping, Optional
from apscheduler.schedulers.background import BackgroundScheduler
from apscheduler.triggers.cron import CronTrigger
import pytz

from core.settings import settings
from scrapers.olx_scraper import OLXScraper
from scrapers.standvirtual_scraper import StandvirtualScraper
from scrapers.autosapo_scraper import AutoSapoScraper
from valuation.predict import update_vehicle_valuations
from ai_agent.deal_finder import DealFinder
from database.db import init_db
from alerts.watchlist_matcher import WatchlistMatcher
from alerts.watchlist_notifier import WatchlistNotifier

logger = logging.getLogger(__name__)

# Default timezone for scheduler
SCHEDULER_TZ = "Europe/Lisbon"
SCHEDULER_RUNTIME_DIR = Path(__file__).resolve().parents[1] / "logs"
DEFAULT_LEASE_PATH = SCHEDULER_RUNTIME_DIR / "scheduler.lease.json"
DEFAULT_LEASE_SECONDS = 300.0
DEFAULT_HEARTBEAT_INTERVAL_SECONDS = 30.0


class LeaseUnavailableError(RuntimeError):
    """Raised by the context-manager form when another worker owns a lease."""


_LEASE_GUARDS: dict[str, threading.Lock] = {}
_LEASE_GUARDS_LOCK = threading.Lock()


def _lease_guard(path: Path) -> threading.Lock:
    key = str(path.resolve())
    with _LEASE_GUARDS_LOCK:
        return _LEASE_GUARDS.setdefault(key, threading.Lock())


def _lease_datetime(value: Any) -> Optional[datetime]:
    if isinstance(value, (int, float)):
        try:
            return datetime.fromtimestamp(float(value), tz=timezone.utc)
        except (OverflowError, OSError, ValueError):
            return None
    if isinstance(value, str) and value:
        try:
            parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
        except ValueError:
            return None
        return parsed.replace(tzinfo=timezone.utc) if parsed.tzinfo is None else parsed.astimezone(timezone.utc)
    return None


class SchedulerLease:
    """Small cross-process file lease with heartbeat and stale-owner recovery.

    Acquisition uses ``O_EXCL`` so two scheduler processes cannot both become
    owners.  The JSON is diagnostic state only; it is never an operational DB
    lock.  A lease is considered orphaned only after its expiry/heartbeat
    boundary (or when its recorded PID is definitely gone).
    """

    def __init__(
        self,
        path: str | Path = DEFAULT_LEASE_PATH,
        *,
        owner_id: Optional[str] = None,
        lease_seconds: float = DEFAULT_LEASE_SECONDS,
        heartbeat_timeout: Optional[float] = None,
        clock: Optional[Callable[[], datetime]] = None,
    ) -> None:
        if lease_seconds <= 0:
            raise ValueError("lease_seconds must be positive")
        self.path = Path(path)
        self.owner_id = owner_id or f"{socket.gethostname()}:{os.getpid()}:{threading.get_ident()}"
        self.lease_seconds = float(lease_seconds)
        self.heartbeat_timeout = float(heartbeat_timeout or lease_seconds)
        self._clock = clock
        self.token = secrets.token_hex(16)
        self._acquired = False
        self._heartbeat_stop = threading.Event()
        self._heartbeat_thread: Optional[threading.Thread] = None

    @property
    def acquired(self) -> bool:
        return self._acquired

    @property
    def held(self) -> bool:
        return self._acquired

    def _now(self) -> datetime:
        now = self._clock() if self._clock else datetime.now(timezone.utc)
        return now.replace(tzinfo=timezone.utc) if now.tzinfo is None else now.astimezone(timezone.utc)

    def _payload(self, now: Optional[datetime] = None) -> Dict[str, Any]:
        current = now or self._now()
        return {
            "owner_id": self.owner_id,
            "pid": os.getpid(),
            "token": self.token,
            "acquired_at": current.isoformat(),
            "heartbeat_at": current.isoformat(),
            "lease_until": (current.timestamp() + self.lease_seconds),
            "status": "running",
        }

    @staticmethod
    def _read(path: Path) -> Optional[Dict[str, Any]]:
        try:
            value = json.loads(path.read_text(encoding="utf-8"))
        except (FileNotFoundError, OSError, json.JSONDecodeError, TypeError):
            return None
        return value if isinstance(value, dict) else None

    @staticmethod
    def _pid_alive(pid: Any) -> bool:
        try:
            value = int(pid)
        except (TypeError, ValueError):
            return False
        if value <= 0:
            return False
        try:
            os.kill(value, 0)
        except ProcessLookupError:
            return False
        except PermissionError:
            return True
        except OSError:
            return False
        return True

    def _is_live(self, payload: Mapping[str, Any], now: datetime) -> bool:
        lease_until = _lease_datetime(payload.get("lease_until"))
        heartbeat_at = _lease_datetime(payload.get("heartbeat_at"))
        if lease_until is None or heartbeat_at is None:
            return False
        if now >= lease_until or (now - heartbeat_at).total_seconds() > self.heartbeat_timeout:
            return False
        pid = payload.get("pid")
        return pid is None or self._pid_alive(pid)

    def _write_atomic(self, payload: Mapping[str, Any]) -> None:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        temporary = self.path.with_name(f".{self.path.name}.{self.token}.tmp")
        try:
            temporary.write_text(json.dumps(dict(payload), sort_keys=True), encoding="utf-8")
            os.replace(str(temporary), str(self.path))
        finally:
            try:
                temporary.unlink()
            except FileNotFoundError:
                pass

    def _recover_locked(self, *, now: Optional[datetime] = None) -> bool:
        current = self._read(self.path)
        if current and self._is_live(current, now or self._now()):
            return False
        try:
            self.path.unlink()
        except FileNotFoundError:
            return False
        except OSError as exc:
            logger.warning("Could not recover orphaned scheduler lease %s: %s", self.path, exc)
            return False
        return True

    def recover_orphan(self) -> bool:
        """Remove an expired/corrupt lease and report whether recovery occurred."""
        with _lease_guard(self.path):
            return self._recover_locked()

    def acquire(self) -> bool:
        if self._acquired:
            return True
        guard = _lease_guard(self.path)
        with guard:
            now = self._now()
            current = self._read(self.path)
            if current is not None and self._is_live(current, now):
                return False
            if current is None and self.path.exists():
                try:
                    age = time_module.time() - self.path.stat().st_mtime
                except OSError:
                    age = 0.0
                if age <= self.heartbeat_timeout:
                    return False
            if self.path.exists():
                self._recover_locked(now=now)
            payload = self._payload(now)
            try:
                self.path.parent.mkdir(parents=True, exist_ok=True)
                descriptor = os.open(
                    str(self.path), os.O_CREAT | os.O_EXCL | os.O_WRONLY,
                    0o600,
                )
                with os.fdopen(descriptor, "w", encoding="utf-8") as handle:
                    json.dump(payload, handle, sort_keys=True)
            except FileExistsError:
                return False
            except OSError:
                return False
            self._acquired = True
            return True

    def heartbeat(self) -> bool:
        if not self._acquired:
            return False
        with _lease_guard(self.path):
            current = self._read(self.path)
            if not current or current.get("token") != self.token:
                self._acquired = False
                return False
            now = self._now()
            current.update({
                "heartbeat_at": now.isoformat(),
                "lease_until": now.timestamp() + self.lease_seconds,
                "status": "running",
            })
            self._write_atomic(current)
            return True

    def start_heartbeat(self, interval: Optional[float] = None) -> None:
        if not self._acquired or self._heartbeat_thread is not None:
            return
        delay = float(interval or min(DEFAULT_HEARTBEAT_INTERVAL_SECONDS, self.lease_seconds / 3))
        delay = max(0.01, delay)
        self._heartbeat_stop.clear()

        def loop() -> None:
            while not self._heartbeat_stop.wait(delay):
                if not self.heartbeat():
                    break

        self._heartbeat_thread = threading.Thread(
            target=loop,
            name=f"scheduler-heartbeat-{self.token[:8]}",
            daemon=True,
        )
        self._heartbeat_thread.start()

    def stop_heartbeat(self) -> None:
        self._heartbeat_stop.set()
        thread = self._heartbeat_thread
        self._heartbeat_thread = None
        if thread and thread is not threading.current_thread():
            thread.join(timeout=1.0)

    def release(self) -> bool:
        self.stop_heartbeat()
        if not self._acquired:
            return False
        released = False
        with _lease_guard(self.path):
            current = self._read(self.path)
            if current and current.get("token") == self.token:
                try:
                    self.path.unlink()
                    released = True
                except FileNotFoundError:
                    released = True
                except OSError as exc:
                    logger.warning("Could not release scheduler lease %s: %s", self.path, exc)
        self._acquired = False
        return released

    def snapshot(self) -> Optional[Dict[str, Any]]:
        return self._read(self.path)

    def __enter__(self) -> "SchedulerLease":
        if not self.acquire():
            raise LeaseUnavailableError(f"scheduler lease is held: {self.path}")
        self.start_heartbeat()
        return self

    def __exit__(self, exc_type, exc, tb) -> None:
        self.release()


# Compatibility aliases for callers that described the primitive as a lock.
SchedulerLock = SchedulerLease
FileLease = SchedulerLease


class DailyJob:
    """Daily automated job for scraping, analysis, and watchlist monitoring"""

    def __init__(
        self,
        *,
        lease_path: Optional[str | Path] = None,
        lease_seconds: float = DEFAULT_LEASE_SECONDS,
        heartbeat_interval_seconds: float = DEFAULT_HEARTBEAT_INTERVAL_SECONDS,
    ) -> None:
        self.scheduler = BackgroundScheduler(timezone=SCHEDULER_TZ)
        self.olx_scraper = OLXScraper()
        self.standvirtual_scraper = StandvirtualScraper()
        self.autosapo_scraper = AutoSapoScraper()
        self.deal_finder = DealFinder()
        self.watchlist_matcher = WatchlistMatcher()
        self.watchlist_notifier = WatchlistNotifier()

        self.lease_path = Path(lease_path) if lease_path else DEFAULT_LEASE_PATH
        self.lease_seconds = float(lease_seconds)
        self.heartbeat_interval_seconds = float(heartbeat_interval_seconds)

    def _lease(self, job_name: str) -> SchedulerLease:
        return SchedulerLease(
            self.lease_path,
            owner_id=f"daily:{job_name}:{os.getpid()}",
            lease_seconds=self.lease_seconds,
            heartbeat_timeout=max(self.lease_seconds, self.heartbeat_interval_seconds * 2),
        )

    def _run_with_lease(
        self,
        job_name: str,
        contract: Callable[[], Optional[Dict[str, object]]],
    ) -> Dict[str, object]:
        lease = self._lease(job_name)
        if not lease.acquire():
            return {
                "status": "blocked",
                "success": False,
                "executed": False,
                "executed_contract": False,
                "job": job_name,
                "reason": "lease_held",
                "lease_path": str(self.lease_path),
            }
        lease.start_heartbeat(self.heartbeat_interval_seconds)
        try:
            result = contract()
            if not isinstance(result, dict):
                return {
                    "status": "failed",
                    "success": False,
                    "executed": False,
                    "executed_contract": False,
                    "job": job_name,
                    "reason": "contract_returned_no_result",
                }
            return result
        except Exception as exc:  # noqa: BLE001
            logger.exception("Scheduler contract %s failed", job_name)
            return {
                "status": "failed",
                "success": False,
                "executed": False,
                "executed_contract": False,
                "job": job_name,
                "error": f"{type(exc).__name__}: {exc}",
            }
        finally:
            lease.release()

    def _dry_run(self, job_name: str = "daily") -> Dict[str, object]:
        def contract() -> Dict[str, object]:
            registry_status = "not_measured"
            configured_sources: Optional[int] = None
            try:
                from scrapers.registry import build_registry_report

                report = build_registry_report()
                registry_status = str(report.get("status", "unknown"))
                sources = report.get("sources")
                configured_sources = len(sources) if isinstance(sources, list) else None
            except Exception as exc:  # noqa: BLE001
                registry_status = f"unavailable:{type(exc).__name__}"
            return {
                "status": "dry_run",
                "success": False,
                "executed": False,
                "executed_contract": False,
                "dry_run": True,
                "job": job_name,
                "registry_status": registry_status,
                "configured_sources": configured_sources,
                "note": "no database, network, model, notification, or scheduler side effect was executed",
            }

        return self._run_with_lease(f"{job_name}:dry_run", contract)

    async def run(
        self,
        *,
        dry_run: bool = True,
        send_notifications: bool = False,
    ) -> Dict[str, object]:
        """Execute the real daily contract, or return an explicit dry-run state.

        The legacy method returned ``status=ok`` without doing any work.  A
        dry-run is intentionally not success; callers must request the real
        contract explicitly and receive measured phase evidence.
        """
        if dry_run:
            return await asyncio.to_thread(self._dry_run, "daily")
        return await asyncio.to_thread(
            self.run_scraping_job,
            dry_run=False,
            send_notifications=send_notifications,
        )

    def run_scraping_job(
        self,
        *,
        dry_run: bool = False,
        send_notifications: bool = True,
    ) -> Dict[str, object]:
        if dry_run:
            return self._dry_run("daily_scraping")
        return self._run_with_lease(
            "daily_scraping",
            lambda: self._run_scraping_contract(send_notifications=send_notifications),
        )

    def _run_scraping_contract(self, *, send_notifications: bool = True) -> Dict[str, object]:
        """Run complete scraping pipeline"""
        logger.info("=" * 60)
        logger.info("Starting daily scraping job")
        logger.info("=" * 60)

        phases: list[str] = []
        try:
            # Initialize database
            init_db()
            phases.append("database_initialized")

            async def _run_async_scraping() -> None:
                from database.db import get_db_context
                from database.models import Vehicle, Source
                from sqlalchemy import select

                def save_deduped(listings, source_name, vehicle_type):
                    """Save listings with deduplication by source + source_id"""
                    if not listings:
                        return 0
                    added = 0
                    updated = 0
                    with get_db_context() as db:
                        for listing in listings:
                            source_id = listing.get("source_id") or listing.get("id")
                            if not source_id:
                                continue
                            existing = db.execute(
                                select(Vehicle).where(
                                    Vehicle.source == Source(source_name),
                                    Vehicle.source_id == str(source_id)
                                )
                            ).scalar_one_or_none()
                            if existing:
                                # Update price and last_seen
                                existing.price = listing.get("price", existing.price)
                                existing.last_seen = datetime.now(timezone.utc)
                                existing.scrape_count = (existing.scrape_count or 1) + 1
                                
                                # Update detailed fields if available
                                if listing.get("horsepower") is not None:
                                    existing.horsepower = listing.get("horsepower")
                                if listing.get("engine_size") is not None:
                                    existing.engine_size = listing.get("engine_size")
                                if listing.get("doors") is not None:
                                    existing.doors = listing.get("doors")
                                if listing.get("color"):
                                    existing.color = listing.get("color")
                                if listing.get("description"):
                                    existing.description = listing.get("description")
                                if listing.get("fuel_type"):
                                    existing.fuel_type = listing.get("fuel_type")
                                if listing.get("transmission"):
                                    existing.transmission = listing.get("transmission")
                                if listing.get("images"):
                                    existing.images = listing.get("images")
                                
                                updated += 1
                            else:
                                vehicle = Vehicle(
                                    source=Source(source_name),
                                    source_id=str(source_id),
                                    url=listing.get("url", ""),
                                    vehicle_type=vehicle_type,
                                    brand=listing.get("brand", "Unknown"),
                                    model=listing.get("model", "Unknown"),
                                    year=listing.get("year"),
                                    km=listing.get("km"),
                                    price=listing.get("price", 0),
                                    title=listing.get("title", ""),
                                    location=listing.get("location"),
                                    description=listing.get("description"),
                                    images=listing.get("images"),
                                    fuel_type=listing.get("fuel_type"),
                                    transmission=listing.get("transmission"),
                                    horsepower=listing.get("horsepower"),
                                    engine_size=listing.get("engine_size"),
                                    doors=listing.get("doors"),
                                    color=listing.get("color"),
                                    seller_name=listing.get("seller_name"),
                                    seller_type=listing.get("seller_type"),
                                    extras=listing.get("extras"),
                                )
                                db.add(vehicle)
                                added += 1
                        db.commit()
                    logger.info(f"[{source_name}] Adicionados: {added}, Atualizados: {updated}")
                    return added + updated

                scraper_failures = []

                def record_source(name, listings, saved):
                    if not listings:
                        scraper_failures.append(name)
                        logger.error("[%s] devolveu 0 anúncios; ciclo marcado como falhado", name)
                    logger.info("[%s] encontrados=%d persistidos=%d", name, len(listings or []), saved)

                logger.info("Scraping OLX...")
                olx_listings = await self.olx_scraper.scrape_listings("carros", max_listings=50, scrape_details=True)
                record_source("OLX:carros", olx_listings, save_deduped(olx_listings, "OLX", "carros"))

                olx_motos = await self.olx_scraper.scrape_listings("motos", max_listings=30, scrape_details=True)
                record_source("OLX:motos", olx_motos, save_deduped(olx_motos, "OLX", "motos"))

                logger.info("Scraping Standvirtual...")
                sv_listings = await self.standvirtual_scraper.scrape_listings("carros", max_listings=50, scrape_details=True)
                record_source("STANDVIRTUAL", sv_listings, save_deduped(sv_listings, "STANDVIRTUAL", "carros"))

                logger.info("Scraping AutoSapo...")
                as_listings = await self.autosapo_scraper.scrape_listings("carros", max_listings=50, scrape_details=True)
                record_source("AUTOSAPO", as_listings, save_deduped(as_listings, "AUTOSAPO", "carros"))
                if scraper_failures:
                    raise RuntimeError("Fontes sem anúncios ou bloqueadas: " + ", ".join(scraper_failures))

            try:
                asyncio.get_running_loop()
            except RuntimeError:
                asyncio.run(_run_async_scraping())
            else:
                raise RuntimeError("run_scraping_job não pode ser chamado dentro de um event loop ativo")
            phases.append("scrape_completed")
            
            # Update valuations
            logger.info("Updating vehicle valuations...")
            update_vehicle_valuations(batch_size=200)
            phases.append("valuations_updated")

            # Find and analyze best deals
            logger.info("Finding best deals...")
            best_deals = self.deal_finder.run_daily_analysis()

            # Send notifications
            if best_deals and send_notifications:
                logger.info(f"Sending notifications for {len(best_deals)} deals")
                self.send_notifications(best_deals)
            phases.append("deals_analyzed")
            if best_deals and send_notifications:
                phases.append("notifications_sent")

            logger.info("Daily scraping job completed successfully")
            return {
                "status": "completed",
                "success": True,
                "executed": True,
                "executed_contract": True,
                "job": "daily_scraping",
                "phases": phases,
            }

        except Exception as e:
            logger.error(f"Error in daily scraping job: {e}")
            return {
                "status": "failed",
                "success": False,
                "executed": bool(phases),
                "executed_contract": False,
                "job": "daily_scraping",
                "phases": phases,
                "error": f"{type(e).__name__}: {e}",
            }

    def run_analysis_job(
        self,
        *,
        dry_run: bool = False,
        send_notifications: bool = True,
    ) -> Dict[str, object]:
        if dry_run:
            return self._dry_run("periodic_analysis")
        return self._run_with_lease(
            "periodic_analysis",
            lambda: self._run_analysis_contract(send_notifications=send_notifications),
        )

    def _run_analysis_contract(self, *, send_notifications: bool = True) -> Dict[str, object]:
        """Run AI analysis on existing vehicles"""
        logger.info("Starting AI analysis job")

        try:
            # Update valuations
            update_vehicle_valuations(batch_size=100)
            
            # Find best deals
            best_deals = self.deal_finder.run_daily_analysis()
            
            # Send notifications
            if best_deals and send_notifications:
                self.send_notifications(best_deals)

            logger.info("AI analysis job completed")
            return {
                "status": "completed",
                "success": True,
                "executed": True,
                "executed_contract": True,
                "job": "periodic_analysis",
            }
        except Exception as e:
            logger.error(f"Error in AI analysis job: {e}")
            return {
                "status": "failed",
                "success": False,
                "executed": True,
                "executed_contract": False,
                "job": "periodic_analysis",
                "error": f"{type(e).__name__}: {e}",
            }

    def run_watchlist_checker(
        self,
        *,
        dry_run: bool = False,
        send_notifications: bool = True,
    ) -> Dict[str, object]:
        if dry_run:
            return self._dry_run("watchlist_checker")
        return self._run_with_lease(
            "watchlist_checker",
            lambda: self._run_watchlist_contract(send_notifications=send_notifications),
        )

    def _run_watchlist_contract(self, *, send_notifications: bool = True) -> Dict[str, object]:
        """Check all watchlists for matching vehicles"""
        logger.info("=" * 40)
        logger.info("Running watchlist checker")
        logger.info("=" * 40)
        
        try:
            matches = self.watchlist_matcher.check_all_watchlists()
            
            if matches and send_notifications:
                logger.info(f"Found {len(matches)} watchlist matches — sending notifications")
                self.watchlist_notifier.notify_matches(matches)
            else:
                logger.info("No watchlist matches found")
                
            return {
                "status": "completed",
                "success": True,
                "executed": True,
                "executed_contract": True,
                "job": "watchlist_checker",
                "matches": len(matches) if isinstance(matches, list) else None,
            }
        except Exception as e:
            logger.error(f"Error in watchlist checker: {e}")
            return {
                "status": "failed",
                "success": False,
                "executed": True,
                "executed_contract": False,
                "job": "watchlist_checker",
                "error": f"{type(e).__name__}: {e}",
            }

    # ── Re-treino periódico controlado ───────────────────────────────────────
    RETRAIN_STATE_PATH = "models/retrain_state.json"
    RETRAIN_MIN_NEW_LISTINGS = 500  # só re-treina com pelo menos este volume novo

    def run_retrain_job(
        self,
        *,
        dry_run: bool = False,
    ) -> Dict[str, object]:
        if dry_run:
            return self._dry_run("weekly_retrain")
        return self._run_with_lease("weekly_retrain", self._run_retrain_contract)

    def _run_retrain_contract(self) -> Dict[str, object]:
        """Re-treino semanal CONTROLADO do modelo de avaliação.

        Só re-treina se houver >= RETRAIN_MIN_NEW_LISTINGS anúncios novos desde
        o último treino (evita re-treinos vazios e oscilação do modelo).
        Ordem: treino segmentado (LOW/FULL) -> treino HIGH -> ligação do routing
        HIGH aos metadados -> re-avaliação -> métricas de observabilidade.
        """
        import json
        import subprocess
        import sys
        from pathlib import Path

        logger.info("=" * 60)
        logger.info("Re-treino periódico controlado — verificação")
        logger.info("=" * 60)

        try:
            from database.db import get_db_context
            from database.models import Vehicle

            state_path = Path(self.RETRAIN_STATE_PATH)
            state = {}
            if state_path.exists():
                try:
                    state = json.loads(state_path.read_text(encoding="utf-8"))
                except Exception:
                    state = {}

            with get_db_context() as db:
                current_n = db.query(Vehicle).filter(Vehicle.is_active == True).count()  # noqa: E712

            last_n = int(state.get("n_listings_at_train", 0))
            new_since = current_n - last_n
            logger.info("Anúncios ativos: %d | no último treino: %d | novos: %d",
                        current_n, last_n, new_since)

            if last_n > 0 and new_since < self.RETRAIN_MIN_NEW_LISTINGS:
                logger.info("Re-treino adiado: apenas %d novos (< %d mínimo)",
                            new_since, self.RETRAIN_MIN_NEW_LISTINGS)
                return {
                    "status": "skipped",
                    "success": False,
                    "executed": True,
                    "executed_contract": True,
                    "job": "weekly_retrain",
                    "reason": "insufficient_new_listings",
                    "new_since": new_since,
                }

            py = sys.executable
            for script in ("scripts/train_segmented.py", "scripts/train_high.py"):
                logger.info("A correr %s ...", script)
                proc = subprocess.run([py, "-u", script], capture_output=True, text=True)
                if proc.returncode != 0:
                    logger.error("Falha em %s:\n%s", script, proc.stderr[-2000:])
                    return {
                        "status": "failed",
                        "success": False,
                        "executed": True,
                        "executed_contract": False,
                        "job": "weekly_retrain",
                        "failed_script": script,
                        "returncode": proc.returncode,
                    }
                logger.info("%s OK", script)

            # Ligar modelo HIGH aos metadados de produção
            mdir = Path(settings.models_dir)
            meta = json.loads((mdir / "best_model_carros.json").read_text(encoding="utf-8"))
            high_meta = json.loads((mdir / "model_carros_high.meta.json").read_text(encoding="utf-8"))
            meta.update({
                "high_model_path": "model_carros_high.json",
                "high_threshold": high_meta["high_threshold"],
                "high_log_target": high_meta["high_log_target"],
                "high_cat_features": high_meta["high_cat_features"],
                "high_metrics_true_ge_20k": high_meta["metrics_true_ge_20k_after"],
            })
            (mdir / "best_model_carros.json").write_text(json.dumps(meta, indent=2), encoding="utf-8")

            # Re-avaliação incremental (só quem não tem a versão atual)
            total = 0
            while True:
                n = update_vehicle_valuations(batch_size=300)
                total += n
                if n == 0:
                    break
            logger.info("Re-avaliados %d anúncios", total)

            # Métricas de observabilidade
            subprocess.run([py, "-u", "scripts/valuation_metrics.py"],
                           capture_output=True, text=True)

            state_path.write_text(json.dumps({
                "n_listings_at_train": current_n,
                "trained_at": datetime.now().isoformat(),
                "r2": meta.get("metrics", {}).get("r2"),
                "mape_pct": meta.get("metrics", {}).get("mape_pct"),
            }, indent=2), encoding="utf-8")
            logger.info("Re-treino controlado concluído (R²=%s)",
                        meta.get("metrics", {}).get("r2"))
            return {
                "status": "completed",
                "success": True,
                "executed": True,
                "executed_contract": True,
                "job": "weekly_retrain",
                "revaluated": total,
            }

        except Exception as e:
            logger.error(f"Error in retrain job: {e}")
            return {
                "status": "failed",
                "success": False,
                "executed": True,
                "executed_contract": False,
                "job": "weekly_retrain",
                "error": f"{type(e).__name__}: {e}",
            }
    
    def send_notifications(self, deals: list[dict[str, object]]) -> None:
        """Send notifications via configured channels"""
        # Discord
        if settings.discord_webhook:
            self.send_discord_notification(deals)

        # Email
        if settings.email_to:
            self.send_email_notification(deals)

        # Telegram
        if settings.telegram_bot_token and settings.telegram_chat_id:
            self.send_telegram_notification(deals)
    
    def send_discord_notification(self, deals: list[dict[str, object]]) -> None:
        """Send notification to Discord webhook"""
        try:
            import requests
        except ImportError:
            logger.warning("Requests not installed, skipping Discord notification")
            return

        if not settings.discord_webhook:
            return
        
        # Build message
        message = f"**🚗 Top {len(deals)} Auto Deals Found**\n\n"
        
        for deal in deals:
            message += f"\n**{deal.get('brand')} {deal.get('model')} ({deal.get('year')})**\n"
            message += f"Price: €{deal.get('price')}\n"
            message += f"Score: {deal.get('deal_score')}\n"
            message += f"Profit: €{deal.get('profit_potential')}\n"
            if deal.get('ai_review'):
                message += f"Review: {str(deal.get('ai_review'))[:200]}...\n"
            message += f"{deal.get('url')}\n\n"
        
        data = {"content": message}

        try:
            response = requests.post(settings.discord_webhook, json=data, timeout=10)
            if response.status_code == 204:
                logger.info("Discord notification sent successfully")
            else:
                logger.warning(f"Discord notification failed: {response.status_code}")
        except Exception as e:
            logger.error(f"Error sending Discord notification: {e}")
    
    def send_email_notification(self, deals: list[dict[str, object]]) -> None:
        """Send notification via email"""
        try:
            import smtplib
            from email.mime.text import MIMEText
            from email.mime.multipart import MIMEMultipart
        except ImportError:
            logger.warning("Email libraries not available, skipping email notification")
            return

        if not all([settings.email_smtp_server, settings.email_smtp_user, settings.email_smtp_password, settings.email_from]):
            return
        
        # Build email content
        subject = f"Top {len(deals)} Auto Deals Found - {datetime.now().strftime('%Y-%m-%d')}"
        
        body = f"<h2>Top {len(deals)} Auto Deals Found</h2>\n"
        
        for i, deal in enumerate(deals[:10], 1):
            body += f"""
            <h3>{i}. {deal.get('brand')} {deal.get('model')} ({deal.get('year')})</h3>
            <ul>
                <li><strong>Price:</strong> €{deal.get('price'):,}</li>
                <li><strong>Estimated Value:</strong> €{deal.get('estimated_value'):,}</li>
                <li><strong>Profit:</strong> €{deal.get('profit_potential'):,}</li>
                <li><strong>Profit %:</strong> {deal.get('profit_percentage'):.1f}%</li>
                <li><strong>Score:</strong> {deal.get('deal_score'):.1f}/10</li>
                <li><strong>URL:</strong> <a href="{deal.get('url')}">View Listing</a></li>
            </ul>
            <hr>
            """
        
        msg = MIMEMultipart()
        msg['From'] = settings.email_from
        recipients = settings.email_to
        if isinstance(recipients, list):
            msg['To'] = ", ".join(recipients)
        else:
            msg['To'] = recipients
        msg['Subject'] = subject
        msg.attach(MIMEText(body, 'html'))

        try:
            with smtplib.SMTP(settings.email_smtp_server, settings.email_smtp_port) as server:
                server.starttls()
                server.login(settings.email_smtp_user, settings.email_smtp_password)
                server.send_message(msg)
            logger.info("Email notification sent successfully")
        except Exception as e:
            logger.error(f"Error sending email notification: {e}")
    
    def send_telegram_notification(self, deals: list[dict[str, object]]) -> None:
        """Send notification via Telegram"""
        try:
            import requests
        except ImportError:
            logger.warning("Requests not installed, skipping Telegram notification")
            return

        if not settings.telegram_bot_token or not settings.telegram_chat_id:
            return
        
        # Build message
        message = f"🚗 *Top {len(deals)} Auto Deals Found*\n\n"
        
        for i, deal in enumerate(deals[:10], 1):
            message += (
                f"*{i}. {deal.get('brand')} {deal.get('model')} ({deal.get('year')})*\n"
                f"💰 Price: €{deal.get('price'):,} | Est: €{deal.get('estimated_value'):,}\n"
                f"📈 Profit: €{deal.get('profit_potential'):,} ({deal.get('profit_percentage'):.1f}%)\n"
                f"⭐ Score: {deal.get('deal_score'):.1f}/10\n"
                f"🔗 {deal.get('url')}\n\n"
            )
        
        url = f"https://api.telegram.org/bot{settings.telegram_bot_token}/sendMessage"
        data = {
            "chat_id": settings.telegram_chat_id,
            "text": message,
            "parse_mode": "Markdown"
        }
        
        try:
            response = requests.post(url, json=data, timeout=10)
            if response.status_code == 200:
                logger.info("Telegram notification sent successfully")
            else:
                logger.warning(f"Telegram notification failed: {response.status_code}")
        except Exception as e:
            logger.error(f"Error sending Telegram notification: {e}")
    
    def start(self) -> None:
        """Start the scheduler"""
        logger.info("Starting scheduler")

        # Parse scraping time
        hour, minute = settings.daily_scraping_time.split(":")

        # Add daily scraping job
        self.scheduler.add_job(
            self.run_scraping_job,
            trigger=CronTrigger(hour=hour, minute=minute),
            id='daily_scraping',
            name='Daily Scraping Job',
            replace_existing=True,
            max_instances=1,
            coalesce=True,
        )

        # Add periodic analysis job (every 6 hours)
        self.scheduler.add_job(
            self.run_analysis_job,
            trigger='interval',
            hours=settings.scraping_interval_hours if hasattr(settings, 'scraping_interval_hours') else settings.scrape_interval_hours,
            id='periodic_analysis',
            name='Periodic Analysis Job',
            replace_existing=True,
            max_instances=1,
            coalesce=True,
        )
        
        # Add watchlist checker job (every hour)
        self.scheduler.add_job(
            self.run_watchlist_checker,
            trigger='interval',
            hours=1,
            id='watchlist_checker',
            name='Watchlist Match Checker',
            replace_existing=True,
            max_instances=1,
            coalesce=True,
        )

        # Re-treino semanal controlado (domingo de madrugada, minuto fora da hora cheia)
        self.scheduler.add_job(
            self.run_retrain_job,
            trigger=CronTrigger(day_of_week='sun', hour=4, minute=17),
            id='weekly_retrain',
            name='Weekly Controlled Model Retrain',
            replace_existing=True,
            max_instances=1,
            coalesce=True,
        )

        self.scheduler.start()
        logger.info("Scheduler started successfully")
    
    def stop(self) -> None:
        """Stop the scheduler"""
        logger.info("Stopping scheduler")
        self.scheduler.shutdown()
        logger.info("Scheduler stopped")


def run_scheduler() -> None:
    """Run the scheduler (blocking)"""
    job = DailyJob()
    job.start()
    
    try:
        # Keep running
        import time
        while True:
            time.sleep(60)
    except KeyboardInterrupt:
        logger.info("Received interrupt signal")
        job.stop()


if __name__ == "__main__":
    # Run scheduler
    run_scheduler()

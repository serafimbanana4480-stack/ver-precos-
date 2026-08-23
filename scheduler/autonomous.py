"""
VER PRECOS — Scheduler Autónomo (cron nativo Python)
====================================================
Substitui/complementa o APScheduler de daily_job.py com:
  - scrape diário (via parallel_runner / scrapers configurados)
  - retrain semanal (scripts/pipeline.train_model) com self-monitoring de R²
  - relatório de saúde diário (reports/health_report.py)
  - ALERTA se R² cair > 10% vs. baseline OU se algum scraper falhar

Usa a biblioteca `schedule` (mais leve que APScheduler, nativa,
sem dependência de TZ externa). Pode correr como processo de fundo
no Windows, ou como target `scheduler` num container Docker.

Uso:
  .venv/Scripts/python.exe -m scheduler.autonomous
  .venv/Scripts/python.exe -m scheduler.autonomous --once   # corre 1 ciclo e sai
"""
from __future__ import annotations

import argparse
import json
import logging
import os
import subprocess
import sys
import threading
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Callable, Dict, Optional

import schedule

from scheduler.daily_job import DEFAULT_LEASE_PATH, SchedulerLease

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)s %(message)s",
)
logger = logging.getLogger("autonomous")

ROOT = Path(__file__).resolve().parent.parent
ALERTS_PATH = ROOT / "logs" / "health_alerts.json"
R2_BASELINE_PATH = ROOT / "logs" / "r2_baseline.json"

# Limiar de degradação: se R² cair > 10% em relação ao baseline, alerta.
R2_DEGRADATION_PCT = 0.10
AUTONOMOUS_LEASE_SECONDS = 300.0


def _with_lease(
    job_name: str,
    contract: Callable[[], Dict[str, Any]],
    *,
    lease_path: Optional[str | Path] = None,
    lease_seconds: float = AUTONOMOUS_LEASE_SECONDS,
) -> Dict[str, Any]:
    path = Path(lease_path) if lease_path else DEFAULT_LEASE_PATH
    lease = SchedulerLease(
        path,
        owner_id=f"autonomous:{job_name}:{os.getpid() if hasattr(os, 'getpid') else 'unknown'}",
        lease_seconds=lease_seconds,
        heartbeat_timeout=lease_seconds,
    )
    if not lease.acquire():
        return {
            "status": "blocked",
            "success": False,
            "executed": False,
            "executed_contract": False,
            "job": job_name,
            "reason": "lease_held",
            "lease_path": str(path),
        }
    lease.start_heartbeat(min(30.0, max(0.01, lease_seconds / 3)))
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
        logger.exception("Autonomous contract %s failed", job_name)
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


def _dry_run(job_name: str, *, lease_path: Optional[str | Path] = None) -> Dict[str, Any]:
    def contract() -> Dict[str, Any]:
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
            "note": "no database, network, model, report, baseline, or alert side effect was executed",
        }

    return _with_lease(f"{job_name}:dry_run", contract, lease_path=lease_path)


def _python() -> str:
    # Usa o interpretador que está a correr este processo
    return sys.executable or "python"


def _run(cmd: list[str]) -> tuple[int, str]:
    """Executa um subcomando e devolve (returncode, stdout+stderr)."""
    logger.info("EXEC: %s", " ".join(cmd))
    try:
        proc = subprocess.run(
            cmd, cwd=str(ROOT), capture_output=True, text=True, timeout=1800
        )
        out = (proc.stdout or "") + (proc.stderr or "")
        if proc.returncode != 0:
            logger.warning("Comando saiu com %s:\n%s", proc.returncode, out[-2000:])
        return proc.returncode, out
    except subprocess.TimeoutExpired:
        logger.error("TIMEOUT no comando: %s", " ".join(cmd))
        return 124, "timeout"
    except Exception as e:  # noqa: BLE001
        logger.error("Erro ao executar %s: %s", cmd, e)
        return 1, str(e)


def job_scrape(
    *,
    dry_run: bool = False,
    send_alerts: bool = True,
    lease_path: Optional[str | Path] = None,
) -> dict:
    """Run the real scrape contract, or an explicit side-effect-free dry run."""
    if dry_run:
        return _dry_run("scrape", lease_path=lease_path)
    return _with_lease(
        "scrape",
        lambda: _job_scrape_contract(send_alerts=send_alerts),
        lease_path=lease_path,
    )


def _job_scrape_contract(*, send_alerts: bool = True) -> Dict[str, Any]:
    """Scrape all configured sources and persist a truthful live result."""
    logger.info("=== JOB: scrape diário ===")
    failed: list[str] = []
    summary: Dict[str, Any] = {}
    try:
        # Chamada direta devolve métricas por fonte e evita declarar sucesso
        # só porque o subprocesso terminou com código 0.
        from scrapers.parallel_runner import run_all_scrapers
        lightweight = run_all_scrapers(
            max_per_scraper=200,
            save_to_db=True,
            max_workers=4,
            vehicle_type="carros",
        )
        if not isinstance(lightweight, dict) or not isinstance(lightweight.get("scrapers"), dict):
            raise RuntimeError("lightweight scraper returned no complete runtime summary")
        summary["lightweight"] = lightweight
        failed.extend(str(item) for item in lightweight.get("failed_sources", []) or [])
        if lightweight.get("overall_success") is not True:
            failed.append("lightweight:overall_failure")

        # Fontes Playwright complementares; cada retorno vazio/bloqueio é falha
        # explícita. Não há tentativa de contornar CAPTCHA/WAF/login.
        for mod, cls, name in [
            ("scrapers.olx_scraper", "OlxScraper", "OLX_PLAYWRIGHT"),
            ("scrapers.standvirtual_scraper", "StandvirtualScraper", "STANDVIRTUAL"),
            ("scrapers.autosapo_scraper", "AutoSapoScraper", "AUTOSAPO"),
        ]:
            code = (
                f"import asyncio,sys; from {mod} import {cls}; "
                f"rows=asyncio.run({cls}().scrape_listings('carros', max_listings=50)); "
                "sys.exit(0 if rows else 1)"
            )
            rc, output = _run([_python(), "-c", code])
            summary[name] = {"returncode": rc, "output_tail": output[-1000:]}
            if rc != 0:
                failed.append(name)
    except Exception as e:  # noqa: BLE001
        logger.error("Scrape falhou globalmente: %s", e)
        failed.append("global")

    failed = sorted(set(failed))
    _write_alerts(failed)
    if failed:
        logger.error("SCRAPERS FALHADOS: %s", ", ".join(failed))
        if send_alerts:
            _alert("Scrapers falhados: " + ", ".join(failed))
    else:
        logger.info("Scrape concluído sem falhas registadas.")
    summary["failed_scrapers"] = failed
    summary["success"] = not failed
    summary["status"] = "completed" if not failed else (
        "warning" if summary.get("lightweight", {}).get("scrapers") and len(failed) < len(summary["lightweight"]["scrapers"]) else "unhealthy"
    )
    summary["executed"] = True
    summary["executed_contract"] = not ("global" in failed and "lightweight" not in summary)
    summary["alerts_sent"] = bool(send_alerts and failed)
    return summary


def job_retrain(
    *,
    dry_run: bool = False,
    send_alerts: bool = True,
    lease_path: Optional[str | Path] = None,
) -> Dict[str, Any]:
    if dry_run:
        return _dry_run("retrain", lease_path=lease_path)
    return _with_lease(
        "retrain",
        lambda: _job_retrain_contract(send_alerts=send_alerts),
        lease_path=lease_path,
    )


def _job_retrain_contract(*, send_alerts: bool = True) -> Dict[str, Any]:
    """Retrain semanal com self-monitoring de R²."""
    logger.info("=== JOB: retrain semanal ===")
    rc, out = _run([_python(), "-m", "scripts.pipeline", "train"])
    if rc != 0:
        if send_alerts:
            _alert("Retrain falhou (rc=%s)" % rc)
        return {
            "status": "failed",
            "success": False,
            "executed": True,
            "executed_contract": False,
            "job": "retrain",
            "returncode": rc,
            "alerts_sent": bool(send_alerts),
        }
    r2 = _read_current_r2()
    if r2 is None:
        logger.warning("R² indisponível após retrain.")
        return {
            "status": "not_measured",
            "success": False,
            "executed": True,
            "executed_contract": False,
            "job": "retrain",
            "reason": "r2_missing_after_retrain",
        }
    baseline = _load_baseline()
    status = "completed"
    success = True
    alerts_sent = False
    if baseline is not None and baseline > 0:
        drop = (baseline - r2) / baseline
        if drop > R2_DEGRADATION_PCT:
            msg = (
                f"R² DEGRADADO: {r2:.4f} (base {baseline:.4f}, "
                f"-{drop*100:.1f}%)"
            )
            logger.error(msg)
            status = "warning"
            success = False
            if send_alerts:
                _alert(msg)
                alerts_sent = True
        else:
            logger.info("R² estável: %.4f (base %.4f)", r2, baseline)
    else:
        logger.info("Baseline de R² definido: %.4f", r2)
    _save_baseline(r2)
    return {
        "status": status,
        "success": success,
        "executed": True,
        "executed_contract": True,
        "job": "retrain",
        "r2": r2,
        "baseline": baseline,
        "alerts_sent": alerts_sent,
    }


def job_health_report(
    *,
    dry_run: bool = False,
    lease_path: Optional[str | Path] = None,
) -> Dict[str, Any]:
    if dry_run:
        return _dry_run("health_report", lease_path=lease_path)
    return _with_lease("health_report", _job_health_report_contract, lease_path=lease_path)


def _job_health_report_contract() -> Dict[str, Any]:
    """Generate the daily health report and verify its artifact."""
    logger.info("=== JOB: relatório de saúde ===")
    report_path = ROOT / "reports" / "health_report_latest.md"
    before = report_path.stat().st_mtime_ns if report_path.exists() else None
    rc, output = _run([_python(), "-m", "reports.health_report"])
    after = report_path.stat().st_mtime_ns if report_path.exists() else None
    generated = rc == 0 and after is not None and (before is None or after > before)
    return {
        "status": "completed" if generated else "failed",
        "success": generated,
        "executed": True,
        "executed_contract": generated,
        "job": "health_report",
        "returncode": rc,
        "report_generated": generated,
        "output_tail": output[-1000:],
    }


# ---------------------------------------------------------------------------
# Helpers de self-monitoring / alertas
# ---------------------------------------------------------------------------
def _read_current_r2() -> float | None:
    meta = ROOT / "models" / "best_model_carros.json"
    if not meta.exists():
        return None
    try:
        data = json.loads(meta.read_text(encoding="utf-8"))
        return data.get("metrics", {}).get("r2")
    except Exception:  # noqa: BLE001
        return None


def _load_baseline() -> float | None:
    if R2_BASELINE_PATH.exists():
        try:
            return float(R2_BASELINE_PATH.read_text(encoding="utf-8").strip())
        except Exception:  # noqa: BLE001
            return None
    return None


def _save_baseline(r2: float) -> None:
    try:
        R2_BASELINE_PATH.write_text(str(r2), encoding="utf-8")
    except Exception as e:  # noqa: BLE001
        logger.warning("Não gravou baseline R²: %s", e)


def _write_alerts(failed: list[str]) -> None:
    """Persiste falhas de scraper para o health_report consumir."""
    ROOT.joinpath("logs").mkdir(parents=True, exist_ok=True)
    payload = {
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "failed_scrapers": failed,
    }
    try:
        ALERTS_PATH.write_text(json.dumps(payload, indent=2), encoding="utf-8")
    except Exception as e:  # noqa: BLE001
        logger.warning("Não gravou health_alerts.json: %s", e)


def _alert(message: str) -> None:
    """Envio leve de alerta. Tenta Discord/Telegram se configurado no .env;
    sempre regista no log. Sem dependências obrigatórias."""
    logger.warning("ALERTA: %s", message)
    # Tenta Discord via webhook se existir env
    try:
        from config import settings  # type: ignore
        webhook = getattr(settings, "discord_webhook", None)
        if webhook:
            import requests  # type: ignore

            requests.post(webhook, json={"content": f"⚠️ VER PRECOS: {message}"}, timeout=10)
    except Exception:  # noqa: BLE001
        pass


def setup_schedule() -> None:
    # Scrape diário às 03:00 (hora de Lisboa ~ UTC; ajustável)
    schedule.every().day.at("03:00").do(job_scrape)
    # Relatório de saúde diário às 03:30
    schedule.every().day.at("03:30").do(job_health_report)
    # Retrain semanal (domingo 04:00)
    schedule.every(7).days.at("04:00").do(job_retrain)
    # Também corre o relatório de saúde logo a seguir ao retrain
    schedule.every(7).days.at("04:30").do(job_health_report)
    logger.info("Agendamento configurado: scrape 03:00, health 03:30, retrain dom 04:00.")


def run_once(
    *,
    dry_run: bool = False,
    send_alerts: bool = True,
    lease_path: Optional[str | Path] = None,
) -> Dict[str, Any]:
    """Run a bounded cycle and only report success from successful contracts."""
    results = {
        "scrape": job_scrape(dry_run=dry_run, send_alerts=send_alerts, lease_path=lease_path),
        "retrain": job_retrain(dry_run=dry_run, send_alerts=send_alerts, lease_path=lease_path),
        "health_report": job_health_report(dry_run=dry_run, lease_path=lease_path),
    }
    successful = all(result.get("success") is True and result.get("executed_contract") is True for result in results.values())
    result = {
        "status": "completed" if successful else ("dry_run" if dry_run else "warning"),
        "success": successful,
        "executed": not dry_run,
        "executed_contract": successful,
        "dry_run": dry_run,
        "jobs": results,
    }
    logger.info("Ciclo único concluído: status=%s success=%s", result["status"], successful)
    return result


def main() -> None:
    parser = argparse.ArgumentParser(description="VER PRECOS Autonomous Scheduler")
    parser.add_argument("--once", action="store_true", help="Corre 1 ciclo e sai")
    parser.add_argument("--dry-run", action="store_true", help="Valida contratos sem BD, rede, relatórios ou alertas")
    parser.add_argument("--no-alerts", action="store_true", help="Não envia alertas externos")
    args = parser.parse_args()

    if args.once:
        run_once(dry_run=args.dry_run, send_alerts=not args.no_alerts)
        return

    setup_schedule()
    logger.info("Scheduler autónomo iniciado. Ctrl+C para parar.")
    try:
        while True:
            schedule.run_pending()
            time.sleep(30)
    except KeyboardInterrupt:
        logger.info("Scheduler parado pelo utilizador.")


if __name__ == "__main__":
    main()

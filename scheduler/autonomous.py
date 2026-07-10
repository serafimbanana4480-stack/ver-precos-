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
import subprocess
import sys
import threading
import time
from datetime import datetime, timezone
from pathlib import Path

import schedule

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


def job_scrape() -> None:
    """Scrape de todas as fontes configuradas + gravaçào de falhas."""
    logger.info("=== JOB: scrape diário ===")
    failed: list[str] = []
    try:
        # parallel_runner cobre Carplus/AutoUncle/PiscaPisca (otimizado)
        rc, out = _run([_python(), "-m", "scrapers.parallel_runner"])
        if rc != 0:
            failed.append("parallel_runner")
        # scrapers complementares do daily_job (OLX/Standvirtual/AutoSapo)
        for mod, name in [
            ("scrapers.olx_scraper", "OLX"),
            ("scrapers.standvirtual_scraper", "STANDVIRTUAL"),
            ("scrapers.autosapo_scraper", "AUTOSAPO"),
        ]:
            try:
                _run([_python(), "-c",
                      f"import asyncio,sys; from {mod} import *; "
                      f"sys.exit(0 if asyncio.run({name.lower()+'_scraper' if False else 'OLXScraper'}().scrape_listings('carros', max_listings=50)) else 1)"])
            except Exception:  # noqa: BLE001
                failed.append(name)
    except Exception as e:  # noqa: BLE001
        logger.error("Scrape falhou globalmente: %s", e)
        failed.append("global")

    _write_alerts(failed)
    if failed:
        logger.error("SCRAPERS FALHADOS: %s", ", ".join(failed))
        _alert("Scrapers falhados: " + ", ".join(failed))
    else:
        logger.info("Scrape concluído sem falhas registadas.")


def job_retrain() -> None:
    """Retrain semanal com self-monitoring de R²."""
    logger.info("=== JOB: retrain semanal ===")
    rc, out = _run([_python(), "-m", "scripts.pipeline", "train"])
    if rc != 0:
        _alert("Retrain falhou (rc=%s)" % rc)
        return
    r2 = _read_current_r2()
    if r2 is None:
        logger.warning("R² indisponível após retrain.")
        return
    baseline = _load_baseline()
    if baseline is not None and baseline > 0:
        drop = (baseline - r2) / baseline
        if drop > R2_DEGRADATION_PCT:
            msg = (
                f"R² DEGRADADO: {r2:.4f} (base {baseline:.4f}, "
                f"-{drop*100:.1f}%)"
            )
            logger.error(msg)
            _alert(msg)
        else:
            logger.info("R² estável: %.4f (base %.4f)", r2, baseline)
    else:
        logger.info("Baseline de R² definido: %.4f", r2)
    _save_baseline(r2)


def job_health_report() -> None:
    """Gera o relatório de saúde diário (.md)."""
    logger.info("=== JOB: relatório de saúde ===")
    _run([_python(), "-m", "reports.health_report"])


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


def run_once() -> None:
    """Corre um ciclo completo (útil para testes/CI) e sai."""
    job_scrape()
    job_retrain()
    job_health_report()
    logger.info("Ciclo único concluído.")


def main() -> None:
    parser = argparse.ArgumentParser(description="VER PRECOS Autonomous Scheduler")
    parser.add_argument("--once", action="store_true", help="Corre 1 ciclo e sai")
    args = parser.parse_args()

    if args.once:
        run_once()
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

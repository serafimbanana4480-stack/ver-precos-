"""
VER PRECOS — Relatório de Saúde Diário (self-monitoring)
=========================================================
Gera um ficheiro Markdown diário em reports/ com:
  - nº de veículos ativos (e por fonte)
  - R² do modelo em produção (best_model_carros.json)
  - scrapers falhados (lê logs/health_alerts.json gerado pelo scheduler)
  - top 5 deals (veículos com maior margem estimada)

Desenhado para ser SEM dependências pesadas (sqlite3 + stdlib).
Corre como:  .venv/Scripts/python.exe reports/health_report.py
"""
from __future__ import annotations

import json
import logging
import sqlite3
import sys
from datetime import datetime, timezone
from pathlib import Path

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(message)s")
logger = logging.getLogger(__name__)

ROOT = Path(__file__).resolve().parent.parent
DB_PATH = ROOT / "data" / "autodeal.db"
MODELS_DIR = ROOT / "models"
REPORTS_DIR = ROOT / "reports"
ALERTS_PATH = ROOT / "logs" / "health_alerts.json"

# Deals com potencial = preço < 85% do valor estimado (maior desconto = melhor deal)
DEAL_DISCOUNT_THRESHOLD = 0.85


def count_vehicles(cur: sqlite3.Cursor) -> tuple[int, list[tuple[str, int]]]:
    cur.execute("SELECT COUNT(*) FROM vehicles WHERE is_active=1")
    total = cur.fetchone()[0]
    cur.execute(
        "SELECT source, COUNT(*) FROM vehicles WHERE is_active=1 "
        "GROUP BY source ORDER BY COUNT(*) DESC"
    )
    by_source = cur.fetchall()
    return total, by_source


def model_r2() -> dict:
    meta_path = MODELS_DIR / "best_model_carros.json"
    if not meta_path.exists():
        return {"available": False, "reason": "best_model_carros.json ausente"}
    try:
        meta = json.loads(meta_path.read_text(encoding="utf-8"))
        m = meta.get("metrics", {})
        return {
            "available": True,
            "type": meta.get("model_type"),
            "r2": m.get("r2"),
            "mae": m.get("mae"),
            "mape_pct": m.get("mape_pct"),
            "n_samples": meta.get("n_samples"),
            "trained_at": meta.get("trained_at"),
        }
    except Exception as e:
        return {"available": False, "reason": f"erro a ler metadata: {e}"}


def failed_scrapers() -> list[str]:
    """Lê falhas registadas pelo scheduler autónomo (logs/health_alerts.json)."""
    if not ALERTS_PATH.exists():
        return []
    try:
        data = json.loads(ALERTS_PATH.read_text(encoding="utf-8"))
        # Espera lista de alertas com campo 'source' e 'level'=='error'
        if isinstance(data, dict) and "failed_scrapers" in data:
            return data["failed_scrapers"]
        if isinstance(data, list):
            return [a.get("source") for a in data if a.get("level") == "error"]
    except Exception:
        pass
    return []


def top_deals(cur: sqlite3.Cursor, limit: int = 5) -> list[dict]:
    cur.execute(
        """
        SELECT brand, model, year, price, estimated_value, source, url
        FROM vehicles
        WHERE is_active=1
          AND price IS NOT NULL
          AND estimated_value IS NOT NULL
          AND estimated_value > 0
          AND price < ?
        ORDER BY (1 - CAST(price AS REAL)/CAST(estimated_value AS REAL)) DESC
        LIMIT ?
        """,
        (DEAL_DISCOUNT_THRESHOLD, limit),
    )
    rows = cur.fetchall()
    deals = []
    for brand, model, year, price, est, source, url in rows:
        margin = (est or 0) - (price or 0)
        pct = (margin / est * 100) if est else 0
        deals.append(
            {
                "title": f"{brand} {model or ''} ({year or '?'})".strip(),
                "price": round(price, 0),
                "estimated": round(est, 0),
                "margin": round(margin, 0),
                "margin_pct": round(pct, 1),
                "source": source,
                "url": url or "",
            }
        )
    return deals


def build_markdown(total, by_source, r2, failed, deals) -> str:
    now = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M UTC")
    lines = [
        f"# VER PRECOS — Relatório de Saúde ({now})",
        "",
        "## Resumo",
        f"- **Veículos ativos:** {total:,}",
    ]

    if r2.get("available"):
        lines.append(
            f"- **Modelo (R²):** {r2['r2']:.4f} "
            f"(MAE €{r2['mae']:.0f}, MAPE {r2['mape_pct']:.1f}%, "
            f"n={r2['n_samples']:,}, {r2['type']})"
        )
        lines.append(f"- **Treinado em:** {r2.get('trained_at')}")
    else:
        lines.append(f"- **Modelo (R²):** ⚠️ indisponível — {r2.get('reason')}")

    if failed:
        lines.append(f"- **Scrapers falhados:** ❌ {', '.join(failed)}")
    else:
        lines.append("- **Scrapers falhados:** ✅ nenhum registado")

    lines.append("")
    lines.append("## Volume por Fonte")
    if by_source:
        for src, cnt in by_source:
            lines.append(f"- {src}: {cnt:,}")
    else:
        lines.append("- (sem dados)")

    lines.append("")
    lines.append(f"## Top 5 Deals (desconto > {int((1-DEAL_DISCOUNT_THRESHOLD)*100)}%)")
    if deals:
        for i, d in enumerate(deals, 1):
            lines.append(
                f"{i}. **{d['title']}** — €{d['price']:,.0f} "
                f"(est. €{d['estimated']:,.0f}, +€{d['margin']:,.0f} / {d['margin_pct']:.1f}%) "
                f"[{d['source']}]({d['url']})"
            )
    else:
        lines.append("- Nenhum deal acima do limiar neste momento.")

    lines.append("")
    lines.append("---")
    lines.append("*Gerado automaticamente por reports/health_report.py*")
    return "\n".join(lines)


def main() -> int:
    if not DB_PATH.exists():
        logger.error(f"Base de dados não encontrada: {DB_PATH}")
        return 1

    REPORTS_DIR.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(str(DB_PATH))
    cur = conn.cursor()
    try:
        total, by_source = count_vehicles(cur)
        r2 = model_r2()
        failed = failed_scrapers()
        deals = top_deals(cur)
    finally:
        conn.close()

    md = build_markdown(total, by_source, r2, failed, deals)

    today = datetime.now(timezone.utc).strftime("%Y-%m-%d")
    report_path = REPORTS_DIR / f"health_report_{today}.md"
    report_path.write_text(md, encoding="utf-8")

    # Também mantém um ficheiro "latest" para fácil consulta
    latest = REPORTS_DIR / "health_report_latest.md"
    latest.write_text(md, encoding="utf-8")

    logger.info(f"Relatório escrito: {report_path}")
    print(md)
    return 0


if __name__ == "__main__":
    sys.exit(main())

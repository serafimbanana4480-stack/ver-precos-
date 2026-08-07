"""Verify stored vehicle prices without treating auction bids as retail prices."""
from __future__ import annotations

import argparse
import json
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from core.settings import settings
from database.db import get_db_context
from database.models import Vehicle
from scrapers.schema import parse_price_evidence


NON_RETAIL = {"monthly", "entry", "installment", "auction_start", "auction_current", "auction_adjudicated"}


def verify() -> dict:
    report = {
        "checked_at": datetime.now(timezone.utc).isoformat(),
        "rows": 0,
        "retail_rows": 0,
        "non_retail_rows": 0,
        "quality_status": {},
        "price_kind": {},
        "hard_failures": [],
        "warnings": [],
        "samples": {},
    }
    with get_db_context() as db:
        rows = db.query(Vehicle).filter(Vehicle.is_active.is_(True)).all()
        report["rows"] = len(rows)
        status = Counter(str(v.quality_status or "unknown") for v in rows)
        kinds = Counter(str(v.price_kind or "unknown") for v in rows)
        report["quality_status"] = dict(status)
        report["price_kind"] = dict(kinds)
        for v in rows:
            kind = str(v.price_kind or "unknown")
            if kind in NON_RETAIL:
                report["non_retail_rows"] += 1
            else:
                report["retail_rows"] += 1
            price = float(v.price or 0)
            observed = float(v.price_observed_value or 0)
            if kind not in NON_RETAIL and price <= 0:
                report["hard_failures"].append({
                    "id": v.id, "source": getattr(v.source, "value", v.source),
                    "reason": "retail_price_missing_or_non_positive", "title": v.title,
                })
            if price < 0 or observed < 0:
                report["hard_failures"].append({
                    "id": v.id, "source": getattr(v.source, "value", v.source),
                    "reason": "negative_price", "title": v.title,
                })
            if v.price_raw:
                evidence = parse_price_evidence(
                    v.price_raw,
                    context=f"{v.title or ''} {v.brand or ''} {v.model or ''}",
                    declared_currency=v.currency,
                    declared_kind=v.price_kind,
                )
                if evidence.value and observed and abs(float(evidence.value) - observed) > 0.01:
                    report["hard_failures"].append({
                        "id": v.id, "source": getattr(v.source, "value", v.source),
                        "reason": "raw_observed_price_mismatch",
                        "raw": v.price_raw, "observed": observed,
                    })
            if price > 500_000:
                report["warnings"].append({
                    "id": v.id, "source": getattr(v.source, "value", v.source),
                    "reason": "high_price_review", "price": price, "title": v.title,
                })
    report["samples"] = {
        "hard_failures": report["hard_failures"][:20],
        "warnings": report["warnings"][:20],
    }
    report["hard_failure_count"] = len(report["hard_failures"])
    report["warning_count"] = len(report["warnings"])
    report["overall_success"] = report["hard_failure_count"] == 0
    return report


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--output", default="reports/price_integrity_latest.json")
    args = parser.parse_args()
    report = verify()
    output = ROOT / args.output
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(report, indent=2, ensure_ascii=False), encoding="utf-8")
    print(json.dumps({
        k: report[k] for k in (
            "rows", "retail_rows", "non_retail_rows", "hard_failure_count",
            "warning_count", "overall_success", "price_kind",
        )
    }, ensure_ascii=False))
    return 0 if report["overall_success"] else 1


if __name__ == "__main__":
    raise SystemExit(main())

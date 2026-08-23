"""Read-only audit for source labels against listing URL authority."""
from __future__ import annotations

import json
import sys
from collections import Counter
from pathlib import Path
from typing import Any, Iterable

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from utils.source_normalize import UNKNOWN_SOURCE, normalize_source, source_from_url


def audit_source_rows(rows: Iterable[Any], example_limit: int = 20) -> dict:
    """Compare persisted source labels with the canonical URL-derived source."""
    total = 0
    mismatches = 0
    unknown_hosts = 0
    unknown_sources = 0
    pairs: Counter[str] = Counter()
    examples = []
    for row in rows:
        if isinstance(row, dict):
            actual = row.get("source")
            url = row.get("url")
        else:
            actual, url = row
        actual_value = (
            actual.value if hasattr(actual, "value") else str(actual or "").strip().upper()
        )
        actual_value = actual_value or UNKNOWN_SOURCE
        host_expected = source_from_url(url)
        if url and host_expected is None:
            # A label supplied by a parser is not URL evidence.  Keep it in
            # the report, but do not call an unknown host healthy (especially
            # not by silently treating it as OLX).
            expected = UNKNOWN_SOURCE
            unknown_hosts += 1
            reason = "host_desconhecido"
        else:
            expected = host_expected or normalize_source(actual_value, url)
            reason = None
        if actual_value == UNKNOWN_SOURCE:
            unknown_sources += 1
        total += 1
        if expected != actual_value:
            mismatches += 1
            pair = f"{actual_value}->{expected}"
            pairs[pair] += 1
            if len(examples) < example_limit:
                example = {"actual": actual_value, "expected": expected, "url": url}
                if reason:
                    example["reason"] = reason
                examples.append(example)

    return {
        "status": "healthy" if not (mismatches or unknown_hosts or unknown_sources) else "unhealthy",
        "rows": total,
        "mismatches": mismatches,
        "unknown_hosts": unknown_hosts,
        "unknown_sources": unknown_sources,
        "by_pair": dict(pairs.most_common()),
        "examples": examples,
    }


def main() -> int:
    from database.db import get_db_context
    from database.models import Vehicle

    with get_db_context() as db:
        rows = db.query(Vehicle.source, Vehicle.url).filter(Vehicle.is_active.is_(True)).all()
    report = audit_source_rows(rows)
    print(json.dumps(report, indent=2, ensure_ascii=False))
    return 0 if report["status"] == "healthy" else 1


if __name__ == "__main__":
    raise SystemExit(main())

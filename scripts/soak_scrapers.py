"""Run the live scraper audit for a bounded duration.

The default cadence is intentionally conservative: one bounded audit cycle
every 15 minutes for five hours.  This exercises every registered scraper,
records failures and price anomalies, and avoids turning the soak into a tight
polling loop against third-party sites.
"""
from __future__ import annotations

import argparse
import asyncio
import json
import logging
import time
from datetime import datetime, timezone
from pathlib import Path

from audit_scrapers import ROOT, audit_once

logger = logging.getLogger("scraper_soak")


async def run_soak(
    *,
    duration_seconds: float,
    interval_seconds: float,
    max_listings: int,
    timeout: float,
    concurrency: int,
    vehicle_type: str,
    output: str,
) -> dict:
    started = time.monotonic()
    started_at = datetime.now(timezone.utc)
    output_path = ROOT / output
    output_path.parent.mkdir(parents=True, exist_ok=True)
    cycles = 0
    status_counts: dict[str, int] = {}
    source_runs: dict[str, int] = {}
    source_failures: dict[str, int] = {}

    with output_path.open("a", encoding="utf-8") as log:
        while time.monotonic() - started < duration_seconds:
            cycle_started = time.monotonic()
            report = await audit_once(
                max_listings=max_listings,
                timeout=timeout,
                vehicle_type=vehicle_type,
                concurrency=concurrency,
            )
            cycles += 1
            for status, count in report.get("status_counts", {}).items():
                status_counts[status] = status_counts.get(status, 0) + count
            for row in report.get("scrapers", []):
                name = str(row["name"])
                source_runs[name] = source_runs.get(name, 0) + 1
                if row.get("status") not in {"ok", "empty"}:
                    source_failures[name] = source_failures.get(name, 0) + 1
            log.write(json.dumps({"cycle": cycles, **report}, ensure_ascii=False) + "\n")
            log.flush()
            print(json.dumps({
                "cycle": cycles,
                "status_counts": report.get("status_counts", {}),
                "duration_seconds": round(time.monotonic() - cycle_started, 1),
            }, ensure_ascii=False), flush=True)
            remaining = duration_seconds - (time.monotonic() - started)
            if remaining <= 0:
                break
            await asyncio.sleep(min(interval_seconds, remaining))

    return {
        "started_at": started_at.isoformat(),
        "finished_at": datetime.now(timezone.utc).isoformat(),
        "duration_seconds": round(time.monotonic() - started, 1),
        "cycles": cycles,
        "status_counts": status_counts,
        "source_runs": source_runs,
        "source_failures": source_failures,
        "log": str(output_path),
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--duration-hours", type=float, default=5.0)
    parser.add_argument("--interval-minutes", type=float, default=15.0)
    parser.add_argument("--max-listings", type=int, default=3)
    parser.add_argument("--timeout", type=float, default=90.0)
    parser.add_argument("--concurrency", type=int, default=3)
    parser.add_argument("--vehicle-type", choices=("carros", "motos"), default="carros")
    parser.add_argument("--output", default="reports/scraper_soak.jsonl")
    parser.add_argument("--summary", default="reports/scraper_soak_summary.json")
    args = parser.parse_args()
    logging.basicConfig(level=logging.WARNING, format="%(asctime)s %(levelname)s %(message)s")
    summary = asyncio.run(run_soak(
        duration_seconds=max(1.0, args.duration_hours * 3600.0),
        interval_seconds=max(30.0, args.interval_minutes * 60.0),
        max_listings=max(1, args.max_listings),
        timeout=max(5.0, args.timeout),
        concurrency=max(1, args.concurrency),
        vehicle_type=args.vehicle_type,
        output=args.output,
    ))
    summary_path = ROOT / args.summary
    summary_path.parent.mkdir(parents=True, exist_ok=True)
    summary_path.write_text(json.dumps(summary, indent=2, ensure_ascii=False), encoding="utf-8")
    print(json.dumps(summary, indent=2, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

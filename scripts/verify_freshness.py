"""Read-only freshness gate for active vehicle inventory."""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

# Make direct execution (`python scripts/verify_freshness.py`) behave like
# module execution from the repository root.
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from api.services.health_service import HealthService


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--max-age-hours", type=int, default=48)
    args = parser.parse_args()
    if args.max_age_hours < 1:
        parser.error("--max-age-hours must be positive")
    report = HealthService().check_data_freshness(args.max_age_hours)
    print(json.dumps(report, indent=2, ensure_ascii=False))
    return 0 if report.get("status") == "healthy" else 1


if __name__ == "__main__":
    raise SystemExit(main())

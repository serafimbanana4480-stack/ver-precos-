#!/usr/bin/env python3
"""Validate scraper configuration/dispatch without making network requests."""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from scrapers.parallel_runner import DEFAULT_SOURCES  # noqa: E402
from scrapers.registry import build_registry_report  # noqa: E402


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--json", dest="json_path", help="gravar relatório JSON")
    parser.add_argument(
        "--default-only", action="store_true",
        help="validar apenas as fontes selecionadas por omissão",
    )
    args = parser.parse_args()

    report = build_registry_report(selected=DEFAULT_SOURCES if args.default_only else None)
    print(json.dumps(report, indent=2, ensure_ascii=False))
    if args.json_path:
        path = Path(args.json_path)
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(report, indent=2, ensure_ascii=False), encoding="utf-8")
    return 0 if report["status"] == "healthy" else 1


if __name__ == "__main__":
    raise SystemExit(main())

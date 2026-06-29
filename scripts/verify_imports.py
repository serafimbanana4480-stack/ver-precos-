#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Verify core imports and basic module wiring.
Run with: py -3 scripts/verify_imports.py
"""
from __future__ import annotations

import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_ROOT))


def main() -> int:
    print("=" * 60)
    print("AutoDeal IA Hunter - Import Verification")
    print("=" * 60)
    print()

    errors: list[str] = []
    warnings: list[str] = []

    def check(label: str, fn) -> None:
        print(f"[{label}]")
        try:
            fn()
            print("  [OK]")
        except Exception as exc:
            errors.append(f"{label}: {exc}")
            print(f"  [FAIL] {exc}")
        print()

    check("config", lambda: __import__("config").settings)
    check(
        "database",
        lambda: (
            __import__("database.db", fromlist=["init_db"]),
            __import__("database.models", fromlist=["Vehicle", "Source"]),
        ),
    )
    check("scrapers.olx", lambda: __import__("scrapers.olx_scraper", fromlist=["OLXScraper"]))
    check(
        "production_safeguards",
        lambda: __import__("utils.production_safeguards", fromlist=["validate_environment"]),
    )
    check("health_check", lambda: __import__("utils.health_check", fromlist=["get_system_health"]))
    check("cli_models", lambda: __import__("validation.cli_models", fromlist=["ScrapeArgs"]))

    print("=" * 60)
    print("SUMMARY")
    print("=" * 60)
    if errors:
        for err in errors:
            print(f"  ERROR: {err}")
        print()
        print("System NOT ready.")
        return 1
    if warnings:
        for warn in warnings:
            print(f"  WARN: {warn}")
    print("Core imports OK.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

"""Read-only registry diagnostics for every configured scraper source.

The runner and the audit scripts used to maintain separate lists. This
module derives one matrix from ``scrapers.sources`` and explicitly marks
runtime health as ``not_measured`` until a live run records it.
"""
from __future__ import annotations

import importlib
from datetime import datetime, timezone
from typing import Any, Dict, Iterable, Optional


_ENUM_ALIASES = {"AUTOUNCLE": "AUTO_UNCLE"}


def _enum_exists(name: str) -> bool:
    from database.models import Source

    return hasattr(Source, _ENUM_ALIASES.get(str(name).upper(), str(name).upper()))


def _implementation(module_name: str, class_name: str) -> tuple[bool, Optional[str]]:
    try:
        module = importlib.import_module(module_name)
        getattr(module, class_name)
        return True, None
    except Exception as exc:  # noqa: BLE001 - report, do not hide registry drift
        return False, f"{type(exc).__name__}: {exc}"


def build_registry_report(
    *, selected: Optional[Iterable[str]] = None
) -> Dict[str, Any]:
    """Build a deterministic source matrix without making network requests."""
    from scrapers.sources import ALL_CONFIGS, LEGACY_SOURCES

    wanted = {str(name).lower() for name in selected} if selected is not None else None
    entries = []

    for key, config in sorted(ALL_CONFIGS.items()):
        if wanted is not None and key not in wanted:
            continue
        enum_exists = _enum_exists(config.source_enum)
        entry = {
            "source": config.source_enum,
            "dispatch_name": key,
            "enum_exists": enum_exists,
            "configured": True,
            "implementation_exists": True,
            "dispatchable": True,
            "enabled": True,
            "country": config.country,
            "requires_js": config.requires_js,
            "role": "leilao" if config.is_auction else "importacao" if config.country != "PT" else "retalho",
            "healthy": "not_measured",
            "last_success": None,
            "last_failure": None,
            "errors": [] if enum_exists else [f"source_enum_missing:{config.source_enum}"],
        }
        entries.append(entry)

    for key, spec in sorted(LEGACY_SOURCES.items()):
        if wanted is not None and key not in wanted:
            continue
        module_name = str(spec["module"])
        class_name = str(spec["cls"])
        impl, error = _implementation(module_name, class_name)
        enum_name = str(spec["enum"])
        errors = [] if _enum_exists(enum_name) else [f"source_enum_missing:{enum_name}"]
        if error:
            errors.append(f"implementation:{error}")
        entries.append({
            "source": enum_name,
            "dispatch_name": key,
            "enum_exists": _enum_exists(enum_name),
            "configured": True,
            "implementation_exists": impl,
            "dispatchable": impl,
            "enabled": bool(spec.get("enabled", True)),
            "country": str(spec.get("country", "PT")),
            "requires_js": bool(spec.get("ground_truth", False)),
            "role": (
                "leilao"
                if spec.get("auction")
                else "importacao" if str(spec.get("country", "PT")).upper() != "PT" else "retalho"
            ),
            "healthy": "not_measured",
            "last_success": None,
            "last_failure": None,
            "errors": errors,
        })

    invalid = [
        entry["dispatch_name"]
        for entry in entries
        if not entry["enum_exists"]
        or not entry["implementation_exists"]
        or not entry["dispatchable"]
    ]
    return {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "status": "healthy" if not invalid else "unhealthy",
        "invalid_sources": invalid,
        "sources": entries,
        "health_note": "live health is not measured by this read-only registry check",
    }

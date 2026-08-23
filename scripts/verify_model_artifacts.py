"""Fail-closed verification of model manifests and their referenced files.

This is intentionally independent from model loading: it is safe to run in a
container build/healthcheck and catches the common case where metadata is
present but the binary model was omitted from the deployment context.
"""
from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any, Dict


def verify_model_artifacts(model_dir: Path, vehicle_types: tuple[str, ...] = ("carros", "motos")) -> Dict[str, Any]:
    model_root = model_dir.resolve()
    models: Dict[str, Any] = {}
    missing: list[str] = []
    invalid: list[str] = []

    for vehicle_type in vehicle_types:
        metadata_path = model_dir / f"best_model_{vehicle_type}.json"
        entry: Dict[str, Any] = {"status": "healthy", "metadata": str(metadata_path)}
        if not metadata_path.is_file():
            entry.update(status="unhealthy", error="metadata_missing")
            missing.append(f"{vehicle_type}:metadata")
            models[vehicle_type] = entry
            continue

        try:
            metadata = json.loads(metadata_path.read_text(encoding="utf-8"))
        except Exception as exc:  # noqa: BLE001
            entry.update(status="unhealthy", error=f"metadata_invalid:{type(exc).__name__}")
            missing.append(f"{vehicle_type}:metadata_invalid")
            models[vehicle_type] = entry
            continue

        files: Dict[str, Any] = {}
        absent: list[str] = []
        for label, key in (
            ("model", "model_path"),
            ("scaler", "scaler_path"),
            ("brand_index", "brand_index_path"),
        ):
            relative = metadata.get(key)
            path = model_dir / str(relative) if relative else None
            safe_path = False
            if path is not None:
                try:
                    path.resolve().relative_to(model_root)
                    safe_path = True
                except ValueError:
                    safe_path = False
            exists = bool(safe_path and path and path.is_file())
            nonempty = bool(exists and path.stat().st_size > 0)
            files[label] = {
                "path": str(path) if path else None,
                "exists": exists,
                "nonempty": nonempty,
            }
            if not exists:
                absent.append(label)
                missing.append(f"{vehicle_type}:{label}")
            elif not nonempty:
                invalid.append(f"{vehicle_type}:{label}:empty")

        brand_path = model_dir / str(metadata.get("brand_index_path")) if metadata.get("brand_index_path") else None
        brand_safe = False
        if brand_path:
            try:
                brand_path.resolve().relative_to(model_root)
                brand_safe = True
            except ValueError:
                brand_safe = False
        if brand_safe and brand_path and brand_path.is_file() and brand_path.stat().st_size > 0:
            try:
                parsed_brand_index = json.loads(brand_path.read_text(encoding="utf-8"))
                if not isinstance(parsed_brand_index, dict):
                    invalid.append(f"{vehicle_type}:brand_index:not_object")
            except Exception as exc:  # noqa: BLE001
                invalid.append(f"{vehicle_type}:brand_index:invalid_json:{type(exc).__name__}")

        entry["model_type"] = metadata.get("model_type")
        entry["files"] = files
        if absent:
            entry.update(status="unhealthy", error="artifact_missing", missing=absent)
        elif any(item.startswith(f"{vehicle_type}:") for item in invalid):
            entry.update(status="unhealthy", error="artifact_invalid")
        models[vehicle_type] = entry

    return {
        "status": "healthy" if not missing and not invalid else "unhealthy",
        "missing": missing,
        "invalid": invalid,
        "models": models,
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--model-dir", default="models")
    args = parser.parse_args()
    report = verify_model_artifacts(Path(args.model_dir))
    print(json.dumps(report, indent=2, ensure_ascii=False))
    return 0 if report["status"] == "healthy" else 1


if __name__ == "__main__":
    raise SystemExit(main())

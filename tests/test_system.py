"""
Legacy system import script — not a pytest module.

Use: py -3 scripts/verify_imports.py
"""
import pytest

pytest.skip(
    "Moved to scripts/verify_imports.py (avoids sys.exit during pytest collection)",
    allow_module_level=True,
)

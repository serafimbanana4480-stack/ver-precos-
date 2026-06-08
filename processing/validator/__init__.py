"""
Data validator module.
"""

from .data_validator import DataValidator as _PackageDataValidator
from .schema_validator import SchemaValidator
from .business_validator import BusinessValidator

# The pipeline imports `from processing.validator import validator` and calls
# validator.validate_vehicle() — that method lives in processing/validator.py
# (the flat-file sibling of this package).  Import it here so the package
# re-exports the correct singleton.
try:
    import importlib, sys
    # Load the flat-file module directly by path to avoid recursive import
    import importlib.util as _ilu
    import pathlib as _pl
    _spec = _ilu.spec_from_file_location(
        "processing.validator_flat",
        _pl.Path(__file__).resolve().parent.parent / "validator.py"
    )
    _mod = _ilu.module_from_spec(_spec)
    _spec.loader.exec_module(_mod)
    DataValidator = _mod.DataValidator
    validator = _mod.validator
except Exception:
    # Fallback: use the package version (validate_vehicle will be missing)
    DataValidator = _PackageDataValidator
    validator = _PackageDataValidator()

# Backwards-compatible aliases expected by the pipeline and tests.
Validator = DataValidator

__all__ = [
    'DataValidator',
    'Validator',
    'validator',
    'SchemaValidator',
    'BusinessValidator'
]

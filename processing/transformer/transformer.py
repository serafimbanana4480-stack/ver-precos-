"""Legacy compatibility wrapper for processing.transformer.transformer."""
from __future__ import annotations

from .data_transformer import DataTransformer


class Transformer(DataTransformer):
    """Backward-compatible alias for the data transformer."""
    pass

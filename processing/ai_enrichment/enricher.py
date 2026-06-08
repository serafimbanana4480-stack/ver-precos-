"""Legacy compatibility wrapper for processing.ai_enrichment.enricher."""
from __future__ import annotations

from .deal_analyzer import DealAnalyzer


class AIEnricher(DealAnalyzer):
    """Backward-compatible alias for the deal analyzer."""
    pass

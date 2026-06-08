"""
Unit test for processing AI enrichment.
"""
import pytest
from processing.ai_enrichment.enricher import AIEnricher


def test_ai_enricher_init():
    """Test AI enricher initialization."""
    enricher = AIEnricher()
    assert enricher is not None

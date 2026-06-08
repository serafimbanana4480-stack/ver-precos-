"""
Unit test for scrapers AI extractor.
"""
import pytest
from scrapers.ai_extractor import AIExtractor


def test_ai_extractor_init():
    """Test AI extractor initialization."""
    extractor = AIExtractor()
    assert extractor is not None

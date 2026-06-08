"""
Unit test for utils html change.
"""
import pytest
from utils.html_change_detector import HTMLChangeDetector


def test_html_change_detector():
    """Test HTML change detector."""
    detector = HTMLChangeDetector()
    result = detector.has_changed("html1", "html2")
    assert result is not None

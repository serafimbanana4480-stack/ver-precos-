"""
Unit test for utils error classifier.
"""
import pytest
from utils.error_classifier import ErrorClassifier


def test_error_classifier():
    """Test error classifier."""
    classifier = ErrorClassifier()
    result = classifier.classify("test error")
    assert result is not None

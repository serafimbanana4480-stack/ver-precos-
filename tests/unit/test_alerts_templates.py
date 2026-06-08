"""
Unit test for alerts templates.
"""
import pytest
from alerts.templates import TemplateEngine


def test_template_engine_init():
    """Test template engine initialization."""
    engine = TemplateEngine()
    assert engine is not None

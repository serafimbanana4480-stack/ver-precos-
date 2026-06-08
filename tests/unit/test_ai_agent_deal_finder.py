"""
Unit test for AI agent deal finder.
"""
import pytest
from ai_agent.deal_finder import DealFinder


def test_deal_finder_init():
    """Test deal finder initialization."""
    finder = DealFinder()
    assert finder is not None

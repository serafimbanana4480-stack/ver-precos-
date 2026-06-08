"""
Unit test for AI agent vision.
"""
import pytest
from ai_agent.vision_analysis import VisionAnalyzer


def test_vision_analyzer_init():
    """Test vision analyzer initialization."""
    analyzer = VisionAnalyzer()
    assert analyzer is not None

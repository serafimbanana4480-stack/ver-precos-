"""
Unit test for AI agent LLM.
"""
import pytest
from ai_agent.llm_review import LLMReviewer


def test_llm_reviewer_init():
    """Test LLM reviewer initialization."""
    reviewer = LLMReviewer()
    assert reviewer is not None

"""
Integration test for AI.
"""
import pytest
from ai_agent.llm_review import LLMReviewer


@pytest.mark.integration
async def test_llm_reviewer():
    """Test LLM reviewer integration."""
    reviewer = LLMReviewer()
    result = await reviewer.analyze("Test description")
    assert result is not None

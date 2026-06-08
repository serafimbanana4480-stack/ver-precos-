"""
E2E test for AI flow.
"""
import pytest
from ai_agent.llm_review import LLMReviewer


@pytest.mark.e2e
async def test_ai_flow():
    """Test complete AI flow."""
    reviewer = LLMReviewer()
    result = await reviewer.analyze("Test listing description")
    assert result is not None

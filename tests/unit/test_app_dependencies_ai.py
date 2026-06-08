"""
Unit test for app dependencies AI.
"""
import pytest
from app.dependencies.ai import get_llm_reviewer


def test_get_llm_reviewer():
    """Test get_llm_reviewer function."""
    reviewer = get_llm_reviewer()
    assert reviewer is not None

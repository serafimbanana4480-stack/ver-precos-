"""
Unit test for ingestion orchestrator.
"""
import pytest
from ingestion.orchestrator import Orchestrator


def test_orchestrator_init():
    """Test orchestrator initialization."""
    orchestrator = Orchestrator()
    assert orchestrator is not None

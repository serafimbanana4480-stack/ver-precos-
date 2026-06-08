"""
Unit test for processing pipeline.
"""
import pytest
from processing.pipeline import Pipeline


def test_pipeline_init():
    """Test pipeline initialization."""
    pipeline = Pipeline()
    assert pipeline is not None

"""
Unit test for ingestion pipelines pipeline.
"""
import pytest
from ingestion.pipelines.pipeline import Pipeline


def test_pipeline_init():
    """Test pipeline initialization."""
    pipeline = Pipeline()
    assert pipeline is not None

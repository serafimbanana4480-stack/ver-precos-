"""
Unit test for processing transformer.
"""
import pytest
from processing.transformer.transformer import DataTransformer


def test_data_transformer_init():
    """Test data transformer initialization."""
    transformer = DataTransformer()
    assert transformer is not None

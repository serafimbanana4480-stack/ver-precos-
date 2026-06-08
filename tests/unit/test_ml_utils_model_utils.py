"""
Unit test for ML utils model utils.
"""
import pytest
from ml.utils.model_utils import ModelUtils


def test_model_utils_init():
    """Test model utils initialization."""
    utils = ModelUtils()
    assert utils is not None

"""
Unit test for processing cleaner.
"""
import pytest
from processing.cleaner.cleaner import DataCleaner


def test_data_cleaner_init():
    """Test data cleaner initialization."""
    cleaner = DataCleaner()
    assert cleaner is not None

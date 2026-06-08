"""
Unit test for utils retry.
"""
import pytest
from utils.retry import retry


def test_retry_decorator():
    """Test retry decorator."""
    @retry(max_attempts=3)
    def test_func():
        return True
    
    result = test_func()
    assert result is True

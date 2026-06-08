"""
Unit test for utils captcha.
"""
import pytest
from utils.captcha_solver import CaptchaSolver


def test_captcha_solver():
    """Test captcha solver."""
    solver = CaptchaSolver()
    result = solver.solve("test_captcha")
    assert result is not None

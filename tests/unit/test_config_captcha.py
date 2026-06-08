"""
Unit test for config captcha.
"""
import pytest
from config.captcha_config import CaptchaConfig


def test_captcha_config_init():
    """Test captcha config initialization."""
    config = CaptchaConfig()
    assert config is not None

"""
Web scrapers module.
"""

from .base_scraper import BaseScraper
from .olx_scraper import OLXScraper
from .standvirtual_scraper import StandVirtualScraper
from .facebook_scraper import FacebookScraper

__all__ = [
    'BaseScraper',
    'OLXScraper',
    'StandVirtualScraper',
    'FacebookScraper'
]

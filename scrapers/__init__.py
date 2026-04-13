"""
Scrapers package initialization
"""
from .olx_scraper import OLXScraper
from .standvirtual_scraper import StandvirtualScraper
from .autosapo_scraper import AutoSapoScraper

__all__ = [
    "OLXScraper",
    "StandvirtualScraper",
    "AutoSapoScraper",
]

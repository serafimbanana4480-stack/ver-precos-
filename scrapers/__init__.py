"""
Scrapers package initialization
"""
from .olx_scraper import OLXScraper
from .standvirtual_scraper import StandvirtualScraper
from .autosapo_scraper import AutoSapoScraper
from .custojusto_scraper import CustoJustoScraper
from .piscapisca_scraper import PiscaPiscaScraper
from .carplus_scraper import CarplusScraper
from .autopt_scraper import AutoPtScraper

__all__ = [
    "OLXScraper",
    "StandvirtualScraper",
    "AutoSapoScraper",
    "CustoJustoScraper",
    "PiscaPiscaScraper",
    "CarplusScraper",
    "AutoPtScraper",
]

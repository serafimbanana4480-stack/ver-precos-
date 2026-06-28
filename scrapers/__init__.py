"""
Scrapers package - lazy imports to avoid circular dependencies and missing deps.
"""
import importlib
from typing import Any


def __getattr__(name: str) -> Any:
    module_map = {
        "OLXScraper": ".olx_scraper",
        "StandvirtualScraper": ".standvirtual_scraper",
        "AutoSapoScraper": ".autosapo_scraper",
        "CustoJustoScraper": ".custojusto_scraper",
        "PiscaPiscaScraper": ".piscapisca_scraper",
        "CarplusScraper": ".carplus_scraper",
        "AutoPtScraper": ".autopt_scraper",
        "AutoScout24Scraper": ".autoscout24_scraper",
        "PiscaPiscaLightweight": ".piscapisca_lightweight",
        "CarplusLightweightScraper": ".carplus_lightweight",
        "AutoPtLightweightScraper": ".autopt_lightweight",
        "AutoScout24Lightweight": ".autoscout24_lightweight",
        "eBayMotorsAPI": ".ebay_motors",
        "AuctionScraper": ".auction_scraper",
        "ImoVirtualScraper": ".imovirtual_scraper",
        "AuctionMultiScraper": ".auction_multi_scraper",
        "ManheimScraper": ".auction_multi_scraper",
        "AutorolaScraper": ".auction_multi_scraper",
        "BCAScraper": ".auction_multi_scraper",
        "get_auction_multi_scraper": ".auction_multi_scraper",
        "FacebookScraper": ".facebook_scraper",
    }
    if name in module_map:
        module = importlib.import_module(module_map[name], __package__)
        return getattr(module, name)
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")


__all__ = [
    "OLXScraper", "StandvirtualScraper", "AutoSapoScraper",
    "CustoJustoScraper", "PiscaPiscaScraper", "CarplusScraper",
    "AutoPtScraper", "AutoScout24Scraper", "PiscaPiscaLightweight", "eBayMotorsAPI",
    "AuctionScraper", "ImoVirtualScraper",
    "AuctionMultiScraper", "ManheimScraper", "AutorolaScraper",
    "BCAScraper", "get_auction_multi_scraper",
    "FacebookScraper",
]

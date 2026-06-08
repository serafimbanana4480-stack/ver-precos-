"""
Scrapers configuration for AutoDeal IA Hunter.
"""
from pydantic import BaseModel
from typing import Dict, List, Optional


class ScraperConfig(BaseModel):
    """Configuration for individual scrapers."""
    
    enabled: bool = True
    max_listings: int = 50
    timeout_seconds: int = 30
    delay_between_requests: float = 1.0
    use_proxies: bool = False
    rotate_user_agents: bool = True
    headless_mode: bool = True
    stealth_mode: bool = False
    retry_attempts: int = 3
    retry_delay_seconds: float = 5.0


class OLXConfig(ScraperConfig):
    """Configuration for OLX scraper."""
    
    base_url: str = "https://www.olx.pt"
    vehicle_type: str = "carros"
    location: Optional[str] = None
    price_min: Optional[int] = None
    price_max: Optional[int] = None


class StandvirtualConfig(ScraperConfig):
    """Configuration for Standvirtual scraper."""
    
    base_url: str = "https://www.standvirtual.com"
    vehicle_type: str = "carros"
    location: Optional[str] = None


class AutoSapoConfig(ScraperConfig):
    """Configuration for AutoSapo scraper."""
    
    base_url: str = "https://autosapo.pt"
    vehicle_type: str = "carros"


class PiscaPiscaConfig(ScraperConfig):
    """Configuration for PiscaPisca scraper."""
    base_url: str = "https://www.piscapisca.pt"


class CarplusConfig(ScraperConfig):
    """Configuration for Carplus scraper."""
    base_url: str = "https://www.carplus.pt"


class ScrapersConfig(BaseModel):
    """Configuration for all scrapers."""
    
    olx: OLXConfig = OLXConfig()
    standvirtual: StandvirtualConfig = StandvirtualConfig()
    autosapo: AutoSapoConfig = AutoSapoConfig()
    custojusto: ScraperConfig = ScraperConfig(enabled=True)
    imovirtual: ScraperConfig = ScraperConfig(enabled=False)
    piscapisca: PiscaPiscaConfig = PiscaPiscaConfig()
    carplus: CarplusConfig = CarplusConfig()
    
    # Global settings
    parallel_scrapers: int = 6
    global_timeout_seconds: int = 300
    save_raw_html: bool = False
    save_screenshots: bool = False


scrapers_config = ScrapersConfig()

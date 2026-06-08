"""
Scheduler configuration for AutoDeal IA Hunter.
"""
from pydantic import BaseModel
from typing import Optional


class SchedulerConfig(BaseModel):
    """Configuration for scheduler settings."""
    
    enabled: bool = True
    timezone: str = "Europe/Lisbon"
    
    # Scraping schedule
    scraping_enabled: bool = True
    scraping_cron: str = "0 */6 * * *"  # Every 6 hours
    
    # AI analysis schedule
    ai_analysis_enabled: bool = True
    ai_analysis_cron: str = "0 */2 * * *"  # Every 2 hours
    
    # ML valuation schedule
    ml_valuation_enabled: bool = True
    ml_valuation_cron: str = "0 */12 * * *"  # Every 12 hours
    
    # Deal finding schedule
    deal_finding_enabled: bool = True
    deal_finding_cron: str = "0 */1 * * *"  # Every hour
    
    # Notification schedule
    notification_enabled: bool = True
    notification_cron: str = "0 */1 * * *"  # Every hour
    
    # Health check schedule
    health_check_enabled: bool = True
    health_check_cron: str = "*/5 * * * *"  # Every 5 minutes
    
    # Max workers
    max_workers: int = 4


scheduler_config = SchedulerConfig()

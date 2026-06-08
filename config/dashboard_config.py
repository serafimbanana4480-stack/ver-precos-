"""
Dashboard configuration for AutoDeal IA Hunter.
"""
from pydantic import BaseModel
from typing import List, Optional


class DashboardConfig(BaseModel):
    """Configuration for Streamlit dashboard."""
    
    enabled: bool = True
    host: str = "localhost"
    port: int = 8501
    theme: str = "light"
    
    # Page configuration
    default_page: str = "Overview"
    show_sidebar: bool = True
    show_page_navigation: bool = True
    
    # Data display
    max_rows_per_page: int = 50
    show_export_button: bool = True
    export_formats: List[str] = ["csv", "json"]
    
    # Refresh settings
    auto_refresh: bool = True
    refresh_interval_seconds: int = 300
    
    # Charts
    enable_charts: bool = True
    chart_theme: str = "default"
    
    # Filters
    enable_filters: bool = True
    default_filters: dict = {}


dashboard_config = DashboardConfig()

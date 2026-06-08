"""
Feature flags configuration for AutoDeal IA Hunter.
"""
from pydantic import BaseModel
from typing import Dict


class FeatureFlagsConfig(BaseModel):
    """Configuration for feature flags."""
    
    # Scraping features
    enable_parallel_scraping: bool = True
    enable_smart_scraping: bool = True
    enable_adaptive_scraping: bool = False
    
    # AI features
    enable_llm_analysis: bool = True
    enable_vision_analysis: bool = True
    enable_ai_enrichment: bool = True
    
    # ML features
    enable_auto_retraining: bool = True
    enable_model_ensemble: bool = False
    enable_online_learning: bool = False
    
    # Dashboard features
    enable_real_time_updates: bool = False
    enable_advanced_filters: bool = True
    enable_export_scheduling: bool = False
    
    # Notification features
    enable_smart_notifications: bool = True
    enable_notification_aggregation: bool = True
    enable_notification_throttling: bool = True
    
    # Performance features
    enable_query_caching: bool = True
    enable_result_caching: bool = True
    enable_compression: bool = True
    
    # Monitoring features
    enable_distributed_tracing: bool = False
    enable_performance_profiling: bool = False
    enable_resource_monitoring: bool = True


feature_flags_config = FeatureFlagsConfig()

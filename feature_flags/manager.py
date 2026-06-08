"""
Feature flag management
Based on Obsidian Vault documentation for Hub - Feature Flags
"""
import logging
from typing import Dict, Any, List, Optional, Set
from datetime import datetime
import json
from pathlib import Path

logger = logging.getLogger(__name__)


class FeatureFlagManager:
    """Manage feature flags for the application"""
    
    def __init__(self, config_file: Optional[str] = None):
        self.flags: Dict[str, Dict[str, Any]] = {}
        self.config_file = config_file or "config/feature_flags.json"
        self._load_flags()
    
    def _load_flags(self):
        """Load feature flags from configuration file"""
        try:
            config_path = Path(self.config_file)
            if config_path.exists():
                with open(config_path, 'r') as f:
                    self.flags = json.load(f)
                logger.info(f"Loaded {len(self.flags)} feature flags")
            else:
                # Default flags
                self.flags = self._get_default_flags()
                logger.info("Using default feature flags")
        except Exception as e:
            logger.error(f"Error loading feature flags: {e}")
            self.flags = self._get_default_flags()
    
    def _get_default_flags(self) -> Dict[str, Dict[str, Any]]:
        """Get default feature flags"""
        return {
            "new_scraping_pipeline": {
                "enabled": False,
                "description": "Use new scraping pipeline architecture",
                "rollout_percentage": 0,
                "user_whitelist": [],
                "user_blacklist": []
            },
            "ai_vision_analysis": {
                "enabled": True,
                "description": "Enable AI vision analysis for vehicle images",
                "rollout_percentage": 100,
                "user_whitelist": [],
                "user_blacklist": []
            },
            "elasticsearch_search": {
                "enabled": False,
                "description": "Use Elasticsearch for search instead of database",
                "rollout_percentage": 0,
                "user_whitelist": [],
                "user_blacklist": []
            },
            "real_time_notifications": {
                "enabled": True,
                "description": "Enable real-time notifications for new deals",
                "rollout_percentage": 100,
                "user_whitelist": [],
                "user_blacklist": []
            },
            "advanced_analytics": {
                "enabled": False,
                "description": "Enable advanced analytics dashboard",
                "rollout_percentage": 10,
                "user_whitelist": [],
                "user_blacklist": []
            },
            "multi_category_scraping": {
                "enabled": False,
                "description": "Enable scraping of multiple vehicle categories",
                "rollout_percentage": 0,
                "user_whitelist": [],
                "user_blacklist": []
            }
        }
    
    def is_enabled(
        self,
        flag_name: str,
        user_id: Optional[str] = None
    ) -> bool:
        """
        Check if a feature flag is enabled for a user
        
        Args:
            flag_name: Name of the feature flag
            user_id: Optional user ID for user-specific flags
            
        Returns:
            True if flag is enabled
        """
        flag = self.flags.get(flag_name)
        
        if not flag:
            logger.warning(f"Feature flag '{flag_name}' not found")
            return False
        
        # Check if globally disabled
        if not flag.get("enabled", False):
            return False
        
        # Check user blacklist
        if user_id and user_id in flag.get("user_blacklist", []):
            return False
        
        # Check user whitelist
        if user_id and flag.get("user_whitelist"):
            if user_id in flag["user_whitelist"]:
                return True
            else:
                return False
        
        # Check rollout percentage
        rollout = flag.get("rollout_percentage", 0)
        if rollout < 100:
            if not user_id:
                return False
            # Hash user ID to determine if they're in rollout
            user_hash = hash(user_id) % 100
            return user_hash < rollout
        
        return True
    
    def enable_flag(self, flag_name: str, rollout_percentage: int = 100):
        """
        Enable a feature flag
        
        Args:
            flag_name: Name of the feature flag
            rollout_percentage: Rollout percentage (0-100)
        """
        if flag_name not in self.flags:
            logger.warning(f"Feature flag '{flag_name}' not found")
            return
        
        self.flags[flag_name]["enabled"] = True
        self.flags[flag_name]["rollout_percentage"] = rollout_percentage
        self._save_flags()
        logger.info(f"Enabled feature flag '{flag_name}' at {rollout_percentage}%")
    
    def disable_flag(self, flag_name: str):
        """
        Disable a feature flag
        
        Args:
            flag_name: Name of the feature flag
        """
        if flag_name not in self.flags:
            logger.warning(f"Feature flag '{flag_name}' not found")
            return
        
        self.flags[flag_name]["enabled"] = False
        self._save_flags()
        logger.info(f"Disabled feature flag '{flag_name}'")
    
    def add_user_to_whitelist(self, flag_name: str, user_id: str):
        """
        Add a user to the whitelist for a feature flag
        
        Args:
            flag_name: Name of the feature flag
            user_id: User ID to add
        """
        if flag_name not in self.flags:
            logger.warning(f"Feature flag '{flag_name}' not found")
            return
        
        if "user_whitelist" not in self.flags[flag_name]:
            self.flags[flag_name]["user_whitelist"] = []
        
        if user_id not in self.flags[flag_name]["user_whitelist"]:
            self.flags[flag_name]["user_whitelist"].append(user_id)
            self._save_flags()
            logger.info(f"Added user {user_id} to whitelist for '{flag_name}'")
    
    def remove_user_from_whitelist(self, flag_name: str, user_id: str):
        """
        Remove a user from the whitelist for a feature flag
        
        Args:
            flag_name: Name of the feature flag
            user_id: User ID to remove
        """
        if flag_name not in self.flags:
            logger.warning(f"Feature flag '{flag_name}' not found")
            return
        
        if "user_whitelist" in self.flags[flag_name]:
            if user_id in self.flags[flag_name]["user_whitelist"]:
                self.flags[flag_name]["user_whitelist"].remove(user_id)
                self._save_flags()
                logger.info(f"Removed user {user_id} from whitelist for '{flag_name}'")
    
    def add_user_to_blacklist(self, flag_name: str, user_id: str):
        """
        Add a user to the blacklist for a feature flag
        
        Args:
            flag_name: Name of the feature flag
            user_id: User ID to add
        """
        if flag_name not in self.flags:
            logger.warning(f"Feature flag '{flag_name}' not found")
            return
        
        if "user_blacklist" not in self.flags[flag_name]:
            self.flags[flag_name]["user_blacklist"] = []
        
        if user_id not in self.flags[flag_name]["user_blacklist"]:
            self.flags[flag_name]["user_blacklist"].append(user_id)
            self._save_flags()
            logger.info(f"Added user {user_id} to blacklist for '{flag_name}'")
    
    def remove_user_from_blacklist(self, flag_name: str, user_id: str):
        """
        Remove a user from the blacklist for a feature flag
        
        Args:
            flag_name: Name of the feature flag
            user_id: User ID to remove
        """
        if flag_name not in self.flags:
            logger.warning(f"Feature flag '{flag_name}' not found")
            return
        
        if "user_blacklist" in self.flags[flag_name]:
            if user_id in self.flags[flag_name]["user_blacklist"]:
                self.flags[flag_name]["user_blacklist"].remove(user_id)
                self._save_flags()
                logger.info(f"Removed user {user_id} from blacklist for '{flag_name}'")
    
    def set_rollout_percentage(self, flag_name: str, percentage: int):
        """
        Set rollout percentage for a feature flag
        
        Args:
            flag_name: Name of the feature flag
            percentage: Rollout percentage (0-100)
        """
        if flag_name not in self.flags:
            logger.warning(f"Feature flag '{flag_name}' not found")
            return
        
        if not 0 <= percentage <= 100:
            logger.error(f"Rollout percentage must be between 0 and 100")
            return
        
        self.flags[flag_name]["rollout_percentage"] = percentage
        self._save_flags()
        logger.info(f"Set rollout percentage for '{flag_name}' to {percentage}%")
    
    def get_all_flags(self) -> Dict[str, Dict[str, Any]]:
        """Get all feature flags"""
        return self.flags.copy()
    
    def get_flag(self, flag_name: str) -> Optional[Dict[str, Any]]:
        """Get a specific feature flag"""
        return self.flags.get(flag_name)
    
    def _save_flags(self):
        """Save feature flags to configuration file"""
        try:
            config_path = Path(self.config_file)
            config_path.parent.mkdir(parents=True, exist_ok=True)
            
            with open(config_path, 'w') as f:
                json.dump(self.flags, f, indent=2)
            
            logger.info(f"Saved feature flags to {self.config_file}")
        except Exception as e:
            logger.error(f"Error saving feature flags: {e}")


# Global feature flag manager instance
feature_flags = FeatureFlagManager()


if __name__ == "__main__":
    # Test feature flag manager
    manager = FeatureFlagManager()
    
    # Check flags
    print("AI Vision Analysis:", manager.is_enabled("ai_vision_analysis"))
    print("Elasticsearch Search:", manager.is_enabled("elasticsearch_search"))
    
    # Enable a flag
    manager.enable_flag("elasticsearch_search", rollout_percentage=50)
    print("Elasticsearch Search (after enable):", manager.is_enabled("elasticsearch_search"))
    
    # Add user to whitelist
    manager.add_user_to_whitelist("new_scraping_pipeline", "user123")
    print("New Scraping Pipeline for user123:", manager.is_enabled("new_scraping_pipeline", "user123"))

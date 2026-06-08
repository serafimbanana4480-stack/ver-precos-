"""
Feature flags module for gradual rollouts and A/B testing
Based on Obsidian Vault documentation for Hub - Feature Flags
"""
from .manager import FeatureFlagManager
from .rollout import RolloutStrategy
from .ab_testing import ABTestManager
from .experimentation import ExperimentManager

__all__ = [
    'FeatureFlagManager',
    'RolloutStrategy',
    'ABTestManager',
    'ExperimentManager'
]

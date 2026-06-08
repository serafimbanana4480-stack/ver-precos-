"""
AutoDeal Multi-Agent System
Sistema de agentes inteligentes para desenvolvimento, monitorização e melhoria contínua.
"""
from .orchestrator import AgentOrchestrator, AgentTask, AgentResult
from .multi_ai_router import MultiAIRouter, AIProvider
from .continuous_improvement import ContinuousImprovementAgent
from .project_generator import ProjectGeneratorAgent

__all__ = [
    "AgentOrchestrator",
    "AgentTask",
    "AgentResult",
    "MultiAIRouter",
    "AIProvider",
    "ContinuousImprovementAgent",
    "ProjectGeneratorAgent",
]
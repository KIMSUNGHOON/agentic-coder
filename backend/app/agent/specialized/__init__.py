"""
Specialized Agents for DeepAgent Phase 1

This module provides specialized agent types for different tasks:
- ResearchAgent: Code exploration and analysis
- PlanningAgent: Enhanced planning with tool awareness
- TestingAgent: Test generation and execution
"""

from .base_specialized_agent import BaseSpecializedAgent, AgentCapabilities
from .research_agent import ResearchAgent
from .testing_agent import TestingAgent

__all__ = [
    "BaseSpecializedAgent",
    "AgentCapabilities",
    "ResearchAgent",
    "TestingAgent",
]

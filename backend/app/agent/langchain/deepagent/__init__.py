"""DeepAgents integration for advanced agent capabilities.

DeepAgents provides:
- Long-running task handling
- Planning and strategy execution
- File system access
- Sub-agent delegation
"""
from app.agent.langchain.deepagent.deep_agent import (
    DeepCodingAgent,
    DeepAgentManager,
    deep_agent_manager,
)

__all__ = [
    "DeepCodingAgent",
    "DeepAgentManager",
    "deep_agent_manager",
]

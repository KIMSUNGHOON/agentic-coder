"""Agent module with multiple framework support.

This module provides a unified interface for accessing agents and workflows
across different framework implementations:
- Microsoft Agent Framework (original)
- LangChain/LangGraph
- DeepAgents

Usage:
    # Using factory (recommended)
    from app.agent import get_agent_manager, get_workflow_manager

    agent_manager = get_agent_manager()
    workflow_manager = get_workflow_manager()

    # Or with specific framework
    agent_manager = get_agent_manager("langchain")

    # Direct access to specific frameworks
    from app.agent.microsoft import agent_manager as ms_agent_manager
    from app.agent.langchain import agent_manager as lc_agent_manager
"""
from app.agent.factory import (
    get_agent_manager,
    get_workflow_manager,
    get_framework_info,
    create_agent,
    create_workflow,
    FrameworkType,
)

# Re-export base interfaces
from app.agent.base.interface import (
    BaseAgent,
    BaseAgentManager,
    BaseWorkflow,
    BaseWorkflowManager,
)

# Backward compatibility: export default managers
# These will use the framework specified in settings
_default_agent_manager = None
_default_workflow_manager = None


def _get_default_agent_manager():
    """Lazy initialization of default agent manager."""
    global _default_agent_manager
    if _default_agent_manager is None:
        _default_agent_manager = get_agent_manager()
    return _default_agent_manager


def _get_default_workflow_manager():
    """Lazy initialization of default workflow manager."""
    global _default_workflow_manager
    if _default_workflow_manager is None:
        _default_workflow_manager = get_workflow_manager()
    return _default_workflow_manager


# For backward compatibility, provide direct access to managers
# Note: These are lazily initialized on first access
class _AgentManagerProxy:
    """Proxy for backward-compatible access to agent_manager."""

    def __getattr__(self, name):
        return getattr(_get_default_agent_manager(), name)


class _WorkflowManagerProxy:
    """Proxy for backward-compatible access to workflow_manager."""

    def __getattr__(self, name):
        return getattr(_get_default_workflow_manager(), name)


# Backward-compatible exports
agent_manager = _AgentManagerProxy()
workflow_manager = _WorkflowManagerProxy()


__all__ = [
    # Factory functions (recommended)
    "get_agent_manager",
    "get_workflow_manager",
    "get_framework_info",
    "create_agent",
    "create_workflow",
    "FrameworkType",
    # Base interfaces
    "BaseAgent",
    "BaseAgentManager",
    "BaseWorkflow",
    "BaseWorkflowManager",
    # Backward-compatible managers
    "agent_manager",
    "workflow_manager",
]

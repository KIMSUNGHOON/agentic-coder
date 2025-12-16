"""Factory for creating agent and workflow managers based on framework selection.

This module provides a unified interface for selecting between different
agent framework implementations:
- Microsoft Agent Framework
- LangChain/LangGraph
- DeepAgents (advanced LangChain)

Usage:
    from app.agent.factory import get_agent_manager, get_workflow_manager

    agent_manager = get_agent_manager()
    workflow_manager = get_workflow_manager()
"""
import logging
from typing import Literal, Optional
from app.core.config import settings
from app.agent.base.interface import BaseAgentManager, BaseWorkflowManager

logger = logging.getLogger(__name__)

# Framework type literal
FrameworkType = Literal["microsoft", "langchain", "deepagent"]


def get_agent_manager(
    framework: Optional[FrameworkType] = None
) -> BaseAgentManager:
    """Get an agent manager for the specified framework.

    Args:
        framework: Framework to use. If None, uses settings.agent_framework.
                   Options: "microsoft", "langchain", "deepagent"

    Returns:
        Agent manager instance implementing BaseAgentManager

    Raises:
        ValueError: If unknown framework is specified
    """
    fw = framework or getattr(settings, 'agent_framework', 'microsoft')

    if fw == "microsoft":
        from app.agent.microsoft.agent_manager import agent_manager
        logger.info("Using Microsoft Agent Framework")
        return agent_manager

    elif fw == "langchain":
        from app.agent.langchain.agent_manager import agent_manager
        logger.info("Using LangChain Agent Framework")
        return agent_manager

    elif fw == "deepagent":
        from app.agent.langchain.deepagent import deep_agent_manager
        logger.info("Using DeepAgents Framework")
        return deep_agent_manager

    else:
        raise ValueError(
            f"Unknown agent framework: {fw}. "
            f"Supported: microsoft, langchain, deepagent"
        )


def get_workflow_manager(
    framework: Optional[FrameworkType] = None
) -> BaseWorkflowManager:
    """Get a workflow manager for the specified framework.

    Args:
        framework: Framework to use. If None, uses settings.agent_framework.
                   Options: "microsoft", "langchain"

    Returns:
        Workflow manager instance implementing BaseWorkflowManager

    Raises:
        ValueError: If unknown framework is specified

    Note:
        DeepAgents doesn't have a separate workflow manager.
        When "deepagent" is specified, it falls back to LangGraph workflow.
    """
    fw = framework or getattr(settings, 'agent_framework', 'microsoft')

    if fw == "microsoft":
        from app.agent.microsoft.workflow_manager import workflow_manager
        logger.info("Using Microsoft Workflow Manager")
        return workflow_manager

    elif fw in ("langchain", "deepagent"):
        from app.agent.langchain.workflow_manager import workflow_manager
        logger.info("Using LangGraph Workflow Manager")
        return workflow_manager

    else:
        raise ValueError(
            f"Unknown workflow framework: {fw}. "
            f"Supported: microsoft, langchain, deepagent"
        )


def get_framework_info() -> dict:
    """Get information about available frameworks.

    Returns:
        Dictionary with framework information
    """
    info = {
        "current_framework": getattr(settings, 'agent_framework', 'microsoft'),
        "available_frameworks": {
            "microsoft": {
                "name": "Microsoft Agent Framework",
                "description": "Original agent framework using WorkflowBuilder and ChatAgent",
                "features": ["Workflow orchestration", "Multi-agent coordination"],
            },
            "langchain": {
                "name": "LangChain/LangGraph",
                "description": "LangChain ecosystem with LangGraph for stateful workflows",
                "features": [
                    "StateGraph workflows",
                    "Built-in persistence",
                    "Human-in-the-loop support",
                ],
            },
            "deepagent": {
                "name": "DeepAgents",
                "description": "Advanced agent built on LangGraph with planning and tools",
                "features": [
                    "Automatic task planning",
                    "File system access",
                    "Sub-agent delegation",
                    "Shell command execution",
                ],
            },
        },
    }

    # Check DeepAgents availability
    try:
        from app.agent.langchain.deepagent.deep_agent import DEEPAGENTS_AVAILABLE
        info["available_frameworks"]["deepagent"]["installed"] = DEEPAGENTS_AVAILABLE
    except ImportError:
        info["available_frameworks"]["deepagent"]["installed"] = False

    return info


# Convenience functions for direct access
def create_agent(session_id: str, framework: Optional[FrameworkType] = None):
    """Create or get an agent for the specified session.

    Args:
        session_id: Session identifier
        framework: Framework to use (optional)

    Returns:
        Agent instance
    """
    manager = get_agent_manager(framework)
    return manager.get_or_create_agent(session_id)


def create_workflow(session_id: str, framework: Optional[FrameworkType] = None):
    """Create or get a workflow for the specified session.

    Args:
        session_id: Session identifier
        framework: Framework to use (optional)

    Returns:
        Workflow instance
    """
    manager = get_workflow_manager(framework)
    return manager.get_or_create_workflow(session_id)

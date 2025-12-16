"""Factory for creating agent and workflow managers based on framework selection.

This module provides a unified interface for selecting between different
agent framework implementations:
- Microsoft Agent Framework
- LangChain/LangGraph
- DeepAgents (advanced LangChain)

Also provides access to:
- AgentSpawner for specialized agents (research, testing, etc.)
- ToolRegistry for tool management

Usage:
    from app.agent.factory import get_agent_manager, get_workflow_manager
    from app.agent.factory import get_spawner, spawn_agent

    agent_manager = get_agent_manager()
    workflow_manager = get_workflow_manager()

    # Spawn specialized agents
    research_agent = spawn_agent("research", "session123")
"""
import logging
from typing import Literal, Optional, List
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


# ==================== Specialized Agent Spawning ====================


def get_spawner():
    """Get the global agent spawner for specialized agents.

    Returns:
        AgentSpawner instance
    """
    from app.agent.registry import get_spawner as _get_spawner
    return _get_spawner()


def spawn_agent(
    agent_type: str,
    session_id: str,
    framework: Optional[FrameworkType] = None
):
    """Spawn a specialized agent.

    Args:
        agent_type: Type of agent (research, testing, etc.)
        session_id: Session identifier
        framework: Framework to use (optional, uses settings if None)

    Returns:
        Spawned agent instance

    Example:
        research_agent = spawn_agent("research", "session123")
        result = await research_agent.process("Find all Python files", {})
    """
    spawner = get_spawner()
    fw = framework
    if fw is None:
        fw = getattr(settings, 'agent_framework', 'microsoft')
    if fw == 'deepagent':
        fw = 'langchain'
    return spawner.spawn(agent_type, session_id, fw)


def list_agent_types(framework: Optional[FrameworkType] = None) -> List[str]:
    """List available specialized agent types.

    Args:
        framework: Framework to list agents for (optional)

    Returns:
        List of agent type names
    """
    from app.agent.registry import AgentRegistry
    registry = AgentRegistry()
    return registry.list_agent_types(framework)


def get_agent_type_info(agent_type: str, framework: Optional[FrameworkType] = None) -> dict:
    """Get information about a specialized agent type.

    Args:
        agent_type: Type of agent
        framework: Framework to use (optional)

    Returns:
        Dictionary with agent information
    """
    from app.agent.registry import AgentRegistry
    registry = AgentRegistry()
    return registry.get_agent_info(agent_type, framework)


# ==================== Tool System Access ====================


def get_tool_registry():
    """Get the global tool registry.

    Returns:
        ToolRegistry instance
    """
    from app.tools.registry import get_registry
    return get_registry()


def get_tool_executor(timeout: int = 30):
    """Get a tool executor instance.

    Args:
        timeout: Maximum execution time in seconds

    Returns:
        ToolExecutor instance
    """
    from app.tools.executor import ToolExecutor
    return ToolExecutor(timeout=timeout)


def list_tools(category: Optional[str] = None) -> List[str]:
    """List available tools.

    Args:
        category: Optional category filter (file, code, git, web, search)

    Returns:
        List of tool names
    """
    registry = get_tool_registry()
    if category:
        from app.tools.base import ToolCategory
        try:
            cat = ToolCategory(category)
            return registry.get_tool_names(cat)
        except ValueError:
            return []
    return registry.get_tool_names()


async def execute_tool(tool_name: str, params: dict, session_id: str = "default"):
    """Execute a tool directly.

    Args:
        tool_name: Name of the tool
        params: Tool parameters
        session_id: Session identifier for logging

    Returns:
        ToolResult with execution results
    """
    executor = get_tool_executor()
    return await executor.execute(tool_name, params, session_id)

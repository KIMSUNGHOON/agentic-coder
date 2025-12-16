"""LangChain/LangGraph agent framework implementation.

This module provides:
- LangChainAgent: Basic chat agent using LangChain
- LangGraphWorkflow: StateGraph-based coding workflow
- Tool Adapter: Bridge to native tool system
- Specialized Agents: Research, Testing agents with tool usage
"""
from app.agent.langchain.agent_manager import (
    LangChainAgent,
    LangChainAgentManager,
    agent_manager,
)
from app.agent.langchain.workflow_manager import (
    LangGraphWorkflow,
    LangGraphWorkflowManager,
    workflow_manager,
)
from app.agent.langchain.tool_adapter import (
    LangChainToolAdapter,
    LangChainToolRegistry,
    get_langchain_tools,
)

# Specialized agents (lazy import to avoid circular dependency)
def get_specialized_agents():
    """Get specialized agent classes."""
    from app.agent.langchain.specialized import (
        BaseLangChainAgent,
        LangChainAgentCapabilities,
        LangChainResearchAgent,
        LangChainTestingAgent,
    )
    return {
        "BaseLangChainAgent": BaseLangChainAgent,
        "LangChainAgentCapabilities": LangChainAgentCapabilities,
        "LangChainResearchAgent": LangChainResearchAgent,
        "LangChainTestingAgent": LangChainTestingAgent,
    }

__all__ = [
    # Agent Manager
    "LangChainAgent",
    "LangChainAgentManager",
    "agent_manager",
    # Workflow Manager
    "LangGraphWorkflow",
    "LangGraphWorkflowManager",
    "workflow_manager",
    # Tool Adapter
    "LangChainToolAdapter",
    "LangChainToolRegistry",
    "get_langchain_tools",
    # Specialized Agents accessor
    "get_specialized_agents",
]

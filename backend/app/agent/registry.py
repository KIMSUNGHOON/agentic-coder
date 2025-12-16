"""
Agent Registry and Spawner - Manage specialized agent lifecycle

Supports both Microsoft Agent Framework and LangChain agents.
"""

from typing import Dict, Type, Optional, List, Union, Any, Literal
import logging

from app.core.config import settings

# Microsoft Framework agents
from .specialized.base_specialized_agent import BaseSpecializedAgent
from .specialized.research_agent import ResearchAgent
from .specialized.testing_agent import TestingAgent

logger = logging.getLogger(__name__)

# Type alias for any agent
AnyAgent = Any  # Can be BaseSpecializedAgent or BaseLangChainAgent


class AgentRegistry:
    """
    Registry for all agent types.

    Maintains a mapping of agent type names to their classes.
    Supports both Microsoft and LangChain frameworks.
    """

    _instance = None

    def __new__(cls):
        if cls._instance is None:
            cls._instance = super().__new__(cls)
            cls._instance._initialized = False
        return cls._instance

    def __init__(self):
        if self._initialized:
            return

        self._microsoft_agents: Dict[str, Type[BaseSpecializedAgent]] = {}
        self._langchain_agents: Dict[str, Type] = {}
        self._register_default_agents()
        self._initialized = True

        total = len(self._microsoft_agents) + len(self._langchain_agents)
        logger.info(f"Agent Registry initialized with {total} agent types")

    def _register_default_agents(self):
        """Register all default agent types for both frameworks."""
        # Microsoft Framework agents
        self.register("research", ResearchAgent, framework="microsoft")
        self.register("testing", TestingAgent, framework="microsoft")

        # LangChain agents (lazy import to avoid circular dependency)
        try:
            from .langchain.specialized.research_agent import LangChainResearchAgent
            from .langchain.specialized.testing_agent import LangChainTestingAgent

            self.register("research", LangChainResearchAgent, framework="langchain")
            self.register("testing", LangChainTestingAgent, framework="langchain")
            logger.info("Registered LangChain specialized agents")
        except ImportError as e:
            logger.warning(f"Could not import LangChain agents: {e}")

    def register(
        self,
        agent_type: str,
        agent_class: Type,
        framework: Literal["microsoft", "langchain"] = "microsoft"
    ):
        """
        Register a new agent type.

        Args:
            agent_type: Type identifier
            agent_class: Agent class to register
            framework: Framework to register for ("microsoft" or "langchain")
        """
        if framework == "microsoft":
            if agent_type in self._microsoft_agents:
                logger.debug(f"Agent type '{agent_type}' already registered for Microsoft")
            self._microsoft_agents[agent_type] = agent_class
        else:
            if agent_type in self._langchain_agents:
                logger.debug(f"Agent type '{agent_type}' already registered for LangChain")
            self._langchain_agents[agent_type] = agent_class

        logger.debug(f"Registered agent type: {agent_type} ({framework})")

    def unregister(
        self,
        agent_type: str,
        framework: Optional[Literal["microsoft", "langchain"]] = None
    ) -> bool:
        """
        Unregister an agent type.

        Args:
            agent_type: Type to unregister
            framework: Framework to unregister from (None = both)

        Returns:
            True if unregistered, False if not found
        """
        removed = False

        if framework is None or framework == "microsoft":
            if agent_type in self._microsoft_agents:
                del self._microsoft_agents[agent_type]
                removed = True

        if framework is None or framework == "langchain":
            if agent_type in self._langchain_agents:
                del self._langchain_agents[agent_type]
                removed = True

        if removed:
            logger.debug(f"Unregistered agent type: {agent_type}")
        return removed

    def get_agent_class(
        self,
        agent_type: str,
        framework: Optional[Literal["microsoft", "langchain"]] = None
    ) -> Optional[Type]:
        """
        Get agent class by type.

        Args:
            agent_type: Type identifier
            framework: Framework to use (None = use settings.agent_framework)

        Returns:
            Agent class or None if not found
        """
        if framework is None:
            framework = getattr(settings, 'agent_framework', 'microsoft')
            # Map 'deepagent' to 'langchain'
            if framework == 'deepagent':
                framework = 'langchain'

        if framework == "langchain":
            return self._langchain_agents.get(agent_type)
        return self._microsoft_agents.get(agent_type)

    def list_agent_types(
        self,
        framework: Optional[Literal["microsoft", "langchain"]] = None
    ) -> List[str]:
        """
        List all registered agent types.

        Args:
            framework: Framework to list (None = all unique types)

        Returns:
            List of agent type names
        """
        if framework == "microsoft":
            return list(self._microsoft_agents.keys())
        elif framework == "langchain":
            return list(self._langchain_agents.keys())
        else:
            # Return unique types from both frameworks
            all_types = set(self._microsoft_agents.keys())
            all_types.update(self._langchain_agents.keys())
            return sorted(list(all_types))

    def get_agent_info(
        self,
        agent_type: str,
        framework: Optional[Literal["microsoft", "langchain"]] = None
    ) -> Optional[Dict]:
        """
        Get information about an agent type.

        Args:
            agent_type: Type identifier
            framework: Framework to use

        Returns:
            Agent info dictionary or None
        """
        agent_class = self.get_agent_class(agent_type, framework)
        if not agent_class:
            return None

        # Create a temporary instance to get info
        temp_instance = agent_class(session_id="temp")

        info = {
            "agent_type": agent_type,
            "framework": framework or settings.agent_framework,
        }

        # Handle different agent types
        if hasattr(temp_instance, 'model_name'):
            info["model_name"] = temp_instance.model_name
        if hasattr(temp_instance, 'capabilities'):
            caps = temp_instance.capabilities
            info["capabilities"] = {
                "can_use_tools": getattr(caps, 'can_use_tools', False),
                "allowed_tools": getattr(caps, 'allowed_tools', None),
                "can_spawn_agents": getattr(caps, 'can_spawn_agents', False),
                "max_iterations": getattr(caps, 'max_iterations', 5),
            }
            if hasattr(caps, 'model_type'):
                info["capabilities"]["model_type"] = caps.model_type
        if hasattr(temp_instance, 'tools'):
            info["tools"] = [t.name for t in temp_instance.tools]

        return info

    def get_all_info(self) -> Dict:
        """Get information about all registered agents."""
        return {
            "microsoft": {
                agent_type: self.get_agent_info(agent_type, "microsoft")
                for agent_type in self._microsoft_agents.keys()
            },
            "langchain": {
                agent_type: self.get_agent_info(agent_type, "langchain")
                for agent_type in self._langchain_agents.keys()
            }
        }


class AgentSpawner:
    """
    Factory for creating and managing agent instances.

    Manages the lifecycle of specialized agents across sessions.
    Supports both Microsoft and LangChain frameworks.
    """

    def __init__(self):
        self.registry = AgentRegistry()
        self._active_agents: Dict[str, AnyAgent] = {}

        logger.info("Agent Spawner initialized")

    def spawn(
        self,
        agent_type: str,
        session_id: str,
        framework: Optional[Literal["microsoft", "langchain"]] = None
    ) -> AnyAgent:
        """
        Spawn a new agent instance.

        Args:
            agent_type: Type of agent to spawn
            session_id: Session identifier
            framework: Framework to use (None = use settings)

        Returns:
            New agent instance

        Raises:
            ValueError: If agent type is unknown
        """
        if framework is None:
            framework = getattr(settings, 'agent_framework', 'microsoft')
            if framework == 'deepagent':
                framework = 'langchain'

        agent_class = self.registry.get_agent_class(agent_type, framework)
        if not agent_class:
            raise ValueError(f"Unknown agent type: {agent_type} for framework: {framework}")

        agent_id = f"{agent_type}_{session_id}_{framework}"

        # Check if already exists
        if agent_id in self._active_agents:
            logger.warning(f"Agent {agent_id} already exists, returning existing instance")
            return self._active_agents[agent_id]

        # Create new instance
        agent = agent_class(session_id=session_id)
        self._active_agents[agent_id] = agent

        logger.info(f"Spawned {agent_type} agent ({framework}) for session {session_id}")

        return agent

    def get_agent(self, agent_id: str) -> Optional[AnyAgent]:
        """
        Get an existing agent instance.

        Args:
            agent_id: Agent identifier (format: type_session_framework)

        Returns:
            Agent instance or None
        """
        return self._active_agents.get(agent_id)

    def get_by_session(self, session_id: str) -> List[AnyAgent]:
        """
        Get all agents for a session.

        Args:
            session_id: Session identifier

        Returns:
            List of agents for this session
        """
        return [
            agent for agent_id, agent in self._active_agents.items()
            if agent.session_id == session_id
        ]

    def terminate(self, agent_id: str) -> bool:
        """
        Terminate an agent.

        Args:
            agent_id: Agent identifier

        Returns:
            True if terminated, False if not found
        """
        if agent_id in self._active_agents:
            agent = self._active_agents[agent_id]
            if hasattr(agent, 'clear_history'):
                agent.clear_history()
            del self._active_agents[agent_id]
            logger.info(f"Terminated agent: {agent_id}")
            return True
        return False

    def terminate_session(self, session_id: str) -> int:
        """
        Terminate all agents for a session.

        Args:
            session_id: Session identifier

        Returns:
            Number of agents terminated
        """
        agents_to_remove = [
            agent_id for agent_id, agent in self._active_agents.items()
            if agent.session_id == session_id
        ]

        for agent_id in agents_to_remove:
            self.terminate(agent_id)

        return len(agents_to_remove)

    def list_active(self) -> List[str]:
        """
        List active agent IDs.

        Returns:
            List of agent IDs
        """
        return list(self._active_agents.keys())

    def get_statistics(self) -> Dict:
        """
        Get spawner statistics.

        Returns:
            Statistics dictionary
        """
        stats = {
            "total_active": len(self._active_agents),
            "by_type": {},
            "by_session": {},
            "by_framework": {"microsoft": 0, "langchain": 0}
        }

        for agent_id, agent in self._active_agents.items():
            # Count by type
            agent_type = agent.agent_type
            stats["by_type"][agent_type] = stats["by_type"].get(agent_type, 0) + 1

            # Count by session
            session_id = agent.session_id
            stats["by_session"][session_id] = stats["by_session"].get(session_id, 0) + 1

            # Count by framework
            if "langchain" in agent_id:
                stats["by_framework"]["langchain"] += 1
            else:
                stats["by_framework"]["microsoft"] += 1

        return stats


# Global spawner instance
_global_spawner = None


def get_spawner() -> AgentSpawner:
    """
    Get the global agent spawner instance.

    Returns:
        Global AgentSpawner instance
    """
    global _global_spawner
    if _global_spawner is None:
        _global_spawner = AgentSpawner()
    return _global_spawner

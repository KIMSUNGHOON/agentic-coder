"""
Agent Registry and Spawner - Manage specialized agent lifecycle
"""

from typing import Dict, Type, Optional, List
import logging

from .specialized.base_specialized_agent import BaseSpecializedAgent
from .specialized.research_agent import ResearchAgent
from .specialized.testing_agent import TestingAgent

logger = logging.getLogger(__name__)


class AgentRegistry:
    """
    Registry for all agent types.

    Maintains a mapping of agent type names to their classes.
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

        self._agent_types: Dict[str, Type[BaseSpecializedAgent]] = {}
        self._register_default_agents()
        self._initialized = True

        logger.info(f"Agent Registry initialized with {len(self._agent_types)} agent types")

    def _register_default_agents(self):
        """Register all default agent types"""
        self.register("research", ResearchAgent)
        self.register("testing", TestingAgent)
        # Future agents can be registered here:
        # self.register("planning", PlanningAgent)
        # self.register("review", ReviewAgent)
        # self.register("debug", DebugAgent)

    def register(self, agent_type: str, agent_class: Type[BaseSpecializedAgent]):
        """
        Register a new agent type.

        Args:
            agent_type: Type identifier
            agent_class: Agent class to register
        """
        if agent_type in self._agent_types:
            logger.warning(f"Agent type '{agent_type}' already registered, overwriting")

        self._agent_types[agent_type] = agent_class
        logger.debug(f"Registered agent type: {agent_type}")

    def unregister(self, agent_type: str) -> bool:
        """
        Unregister an agent type.

        Args:
            agent_type: Type to unregister

        Returns:
            True if unregistered, False if not found
        """
        if agent_type in self._agent_types:
            del self._agent_types[agent_type]
            logger.debug(f"Unregistered agent type: {agent_type}")
            return True
        return False

    def get_agent_class(self, agent_type: str) -> Optional[Type[BaseSpecializedAgent]]:
        """
        Get agent class by type.

        Args:
            agent_type: Type identifier

        Returns:
            Agent class or None if not found
        """
        return self._agent_types.get(agent_type)

    def list_agent_types(self) -> List[str]:
        """
        List all registered agent types.

        Returns:
            List of agent type names
        """
        return list(self._agent_types.keys())

    def get_agent_info(self, agent_type: str) -> Optional[Dict]:
        """
        Get information about an agent type.

        Args:
            agent_type: Type identifier

        Returns:
            Agent info dictionary or None
        """
        agent_class = self.get_agent_class(agent_type)
        if not agent_class:
            return None

        # Create a temporary instance to get info
        temp_instance = agent_class(session_id="temp")
        return {
            "agent_type": agent_type,
            "model_name": temp_instance.model_name,
            "capabilities": {
                "can_use_tools": temp_instance.capabilities.can_use_tools,
                "allowed_tools": temp_instance.capabilities.allowed_tools,
                "can_spawn_agents": temp_instance.capabilities.can_spawn_agents,
                "max_iterations": temp_instance.capabilities.max_iterations,
            }
        }


class AgentSpawner:
    """
    Factory for creating and managing agent instances.

    Manages the lifecycle of specialized agents across sessions.
    """

    def __init__(self):
        self.registry = AgentRegistry()
        self._active_agents: Dict[str, BaseSpecializedAgent] = {}

        logger.info("Agent Spawner initialized")

    def spawn(self, agent_type: str, session_id: str) -> BaseSpecializedAgent:
        """
        Spawn a new agent instance.

        Args:
            agent_type: Type of agent to spawn
            session_id: Session identifier

        Returns:
            New agent instance

        Raises:
            ValueError: If agent type is unknown
        """
        agent_class = self.registry.get_agent_class(agent_type)
        if not agent_class:
            raise ValueError(f"Unknown agent type: {agent_type}")

        agent_id = f"{agent_type}_{session_id}"

        # Check if already exists
        if agent_id in self._active_agents:
            logger.warning(f"Agent {agent_id} already exists, returning existing instance")
            return self._active_agents[agent_id]

        # Create new instance
        agent = agent_class(session_id=session_id)
        self._active_agents[agent_id] = agent

        logger.info(f"Spawned {agent_type} agent for session {session_id}")

        return agent

    def get_agent(self, agent_id: str) -> Optional[BaseSpecializedAgent]:
        """
        Get an existing agent instance.

        Args:
            agent_id: Agent identifier (format: type_session)

        Returns:
            Agent instance or None
        """
        return self._active_agents.get(agent_id)

    def get_by_session(self, session_id: str) -> List[BaseSpecializedAgent]:
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
            "by_session": {}
        }

        for agent_id, agent in self._active_agents.items():
            # Count by type
            agent_type = agent.agent_type
            stats["by_type"][agent_type] = stats["by_type"].get(agent_type, 0) + 1

            # Count by session
            session_id = agent.session_id
            stats["by_session"][session_id] = stats["by_session"].get(session_id, 0) + 1

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

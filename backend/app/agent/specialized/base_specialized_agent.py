"""
Base class for specialized agents with tool usage capabilities
"""

from typing import List, Dict, Any, Optional
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
import logging

logger = logging.getLogger(__name__)


@dataclass
class AgentCapabilities:
    """Defines what an agent can do"""
    can_use_tools: bool = True
    allowed_tools: Optional[List[str]] = None  # None = all tools allowed
    can_spawn_agents: bool = False
    max_iterations: int = 5
    requires_human_approval: bool = False


class BaseSpecializedAgent(ABC):
    """
    Base class for all specialized agents.

    All specialized agents must inherit from this class and implement:
    - get_system_prompt(): Define the agent's behavior
    - process(): Main task processing logic
    """

    def __init__(
        self,
        agent_type: str,
        model_name: str,
        capabilities: AgentCapabilities,
        session_id: str
    ):
        """
        Initialize specialized agent.

        Args:
            agent_type: Type identifier (research, testing, etc.)
            model_name: LLM model to use
            capabilities: Agent capabilities configuration
            session_id: Session identifier
        """
        self.agent_type = agent_type
        self.model_name = model_name
        self.capabilities = capabilities
        self.session_id = session_id
        self.history: List[Dict] = []
        self.tool_executor = None

        # Initialize tool executor if permitted
        if capabilities.can_use_tools:
            from app.tools.executor import ToolExecutor
            self.tool_executor = ToolExecutor()

        logger.info(f"Initialized {agent_type} agent for session {session_id}")

    @abstractmethod
    def get_system_prompt(self) -> str:
        """
        Return the system prompt for this agent.

        This defines the agent's role, responsibilities, and behavior.

        Returns:
            System prompt string
        """
        pass

    @abstractmethod
    async def process(self, task: str, context: Dict[str, Any]) -> Dict[str, Any]:
        """
        Process a task and return results.

        Args:
            task: Task description
            context: Additional context (files, data, etc.)

        Returns:
            Processing results
        """
        pass

    async def use_tool(self, tool_name: str, params: Dict) -> Any:
        """
        Execute a tool if permitted.

        Args:
            tool_name: Name of the tool to use
            params: Tool parameters

        Returns:
            Tool execution result

        Raises:
            PermissionError: If agent is not allowed to use tools
        """
        if not self.capabilities.can_use_tools:
            raise PermissionError(f"Agent {self.agent_type} cannot use tools")

        if self.capabilities.allowed_tools and tool_name not in self.capabilities.allowed_tools:
            raise PermissionError(
                f"Tool {tool_name} not allowed for {self.agent_type}. "
                f"Allowed: {self.capabilities.allowed_tools}"
            )

        logger.info(f"[{self.session_id}] {self.agent_type} using tool: {tool_name}")
        result = await self.tool_executor.execute(tool_name, params, self.session_id)
        return result

    def add_to_history(self, role: str, content: str):
        """Add a message to agent's history"""
        self.history.append({
            "role": role,
            "content": content
        })

    def get_history(self, limit: int = 10) -> List[Dict]:
        """Get recent history"""
        return self.history[-limit:]

    def clear_history(self):
        """Clear agent history"""
        self.history = []
        logger.debug(f"Cleared history for {self.agent_type} agent")

    def to_dict(self) -> Dict:
        """
        Serialize agent to dictionary.

        Returns:
            Agent state as dictionary
        """
        return {
            "agent_type": self.agent_type,
            "model_name": self.model_name,
            "session_id": self.session_id,
            "capabilities": {
                "can_use_tools": self.capabilities.can_use_tools,
                "allowed_tools": self.capabilities.allowed_tools,
                "can_spawn_agents": self.capabilities.can_spawn_agents,
                "max_iterations": self.capabilities.max_iterations,
            },
            "history_length": len(self.history)
        }

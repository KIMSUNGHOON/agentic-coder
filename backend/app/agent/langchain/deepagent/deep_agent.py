"""DeepAgents integration for advanced coding capabilities.

DeepAgents is built on top of LangChain and LangGraph, providing:
- Planning before execution
- Computer access (shell, filesystem)
- Sub-agent delegation for isolated task execution

This module provides a skeleton implementation that can be extended
when the deepagents package is available.
"""
import logging
from typing import List, Dict, Any, AsyncGenerator, Optional

from app.agent.base.interface import BaseAgent, BaseAgentManager

logger = logging.getLogger(__name__)

# Flag to check if deepagents is available
DEEPAGENTS_AVAILABLE = False

try:
    from deepagents import create_deep_agent
    from deepagents.middleware import (
        TodoListMiddleware,
        FilesystemMiddleware,
        SubAgentMiddleware,
    )
    DEEPAGENTS_AVAILABLE = True
    logger.info("DeepAgents package is available")
except ImportError:
    logger.warning(
        "DeepAgents package not installed. "
        "Install with: pip install deepagents"
    )


class DeepCodingAgent(BaseAgent):
    """Advanced coding agent using DeepAgents framework.

    DeepAgents provides enhanced capabilities over basic LangChain:
    - Automatic task planning via TodoListMiddleware
    - File system operations via FilesystemMiddleware
    - Sub-agent delegation for complex tasks

    If DeepAgents is not installed, this falls back to basic LangChain behavior.
    """

    def __init__(self):
        """Initialize DeepCodingAgent."""
        self.conversation_history: List[Dict[str, str]] = []
        self.agent = None

        if DEEPAGENTS_AVAILABLE:
            self._init_deep_agent()
        else:
            logger.warning(
                "DeepAgents not available. "
                "Agent will operate in limited mode."
            )

        logger.info("DeepCodingAgent initialized")

    def _init_deep_agent(self):
        """Initialize the DeepAgents agent with middleware."""
        try:
            # Create deep agent with coding-focused configuration
            self.agent = create_deep_agent(
                tools=[],  # Tools will be added based on requirements
                system_prompt="""You are an advanced coding assistant with the ability to:
1. Plan complex tasks before execution
2. Read and write files
3. Execute shell commands safely
4. Delegate sub-tasks to specialized agents

For each coding request:
1. First, create a detailed plan
2. Execute each step methodically
3. Verify the results
4. Report completion status

Always prioritize code quality and safety.""",
                # Enable built-in middleware
                middleware=[
                    TodoListMiddleware(),  # Automatic task tracking
                    FilesystemMiddleware(
                        allowed_paths=["./workspace"],
                        read_only=False
                    ),
                    SubAgentMiddleware(),  # Enable sub-agent delegation
                ],
            )
            logger.info("DeepAgents agent created with middleware")
        except Exception as e:
            logger.error(f"Failed to initialize DeepAgents: {e}")
            self.agent = None

    async def process_message(
        self,
        user_message: str,
        task_type: str = "coding",
        system_prompt: Optional[str] = None
    ) -> str:
        """Process a user message and return agent response.

        Args:
            user_message: User's message
            task_type: Type of task ('reasoning' or 'coding')
            system_prompt: Optional system prompt to use

        Returns:
            Agent's response
        """
        if not DEEPAGENTS_AVAILABLE or self.agent is None:
            return self._fallback_response(user_message)

        try:
            # Run the deep agent
            result = await self.agent.arun(user_message)

            # Update conversation history
            self.conversation_history.append({"role": "user", "content": user_message})
            self.conversation_history.append({"role": "assistant", "content": result})

            # Keep only last 10 messages
            if len(self.conversation_history) > 10:
                self.conversation_history = self.conversation_history[-10:]

            return result

        except Exception as e:
            logger.error(f"Error in DeepAgent processing: {e}")
            raise

    async def stream_message(
        self,
        user_message: str,
        task_type: str = "coding",
        system_prompt: Optional[str] = None
    ) -> AsyncGenerator[str, None]:
        """Process a user message and stream the response.

        Args:
            user_message: User's message
            task_type: Type of task ('reasoning' or 'coding')
            system_prompt: Optional system prompt to use

        Yields:
            Chunks of the agent's response
        """
        if not DEEPAGENTS_AVAILABLE or self.agent is None:
            yield self._fallback_response(user_message)
            return

        try:
            full_response = ""

            # Stream from deep agent
            async for chunk in self.agent.astream(user_message):
                if isinstance(chunk, dict) and "content" in chunk:
                    content = chunk["content"]
                elif isinstance(chunk, str):
                    content = chunk
                else:
                    continue

                full_response += content
                yield content

            # Update conversation history
            self.conversation_history.append({"role": "user", "content": user_message})
            self.conversation_history.append({"role": "assistant", "content": full_response})

            if len(self.conversation_history) > 10:
                self.conversation_history = self.conversation_history[-10:]

        except Exception as e:
            logger.error(f"Error streaming from DeepAgent: {e}")
            raise

    def _fallback_response(self, message: str) -> str:
        """Provide fallback response when DeepAgents is not available."""
        return (
            "DeepAgents is not currently available. "
            "Please install it with: pip install deepagents tavily-python\n\n"
            f"Your message: {message}"
        )

    def clear_history(self) -> None:
        """Clear conversation history."""
        self.conversation_history = []
        logger.info("DeepAgent conversation history cleared")

    def get_history(self) -> List[Dict[str, str]]:
        """Get conversation history.

        Returns:
            List of conversation messages
        """
        return self.conversation_history.copy()


class DeepAgentManager(BaseAgentManager):
    """Manager for DeepAgents sessions."""

    def __init__(self):
        """Initialize manager."""
        self.agents: Dict[str, DeepCodingAgent] = {}
        logger.info("DeepAgentManager initialized")

    def get_or_create_agent(self, session_id: str) -> DeepCodingAgent:
        """Get existing agent or create new one for session.

        Args:
            session_id: Session identifier

        Returns:
            DeepCodingAgent instance
        """
        if session_id not in self.agents:
            self.agents[session_id] = DeepCodingAgent()
            logger.info(f"Created new DeepAgent for session {session_id}")
        return self.agents[session_id]

    def delete_agent(self, session_id: str) -> None:
        """Delete agent for session.

        Args:
            session_id: Session identifier
        """
        if session_id in self.agents:
            del self.agents[session_id]
            logger.info(f"Deleted DeepAgent for session {session_id}")

    def get_active_sessions(self) -> List[str]:
        """Get list of active session IDs.

        Returns:
            List of session IDs
        """
        return list(self.agents.keys())


# Global deep agent manager instance
deep_agent_manager = DeepAgentManager()

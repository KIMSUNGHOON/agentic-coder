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
    from deepagents.middleware.subagents import SubAgentMiddleware
    from deepagents.middleware.filesystem import FilesystemMiddleware
    from deepagents.backends.filesystem import FilesystemBackend
    from langchain_openai import ChatOpenAI
    DEEPAGENTS_AVAILABLE = True
    logger.info("DeepAgents package is available (v0.3.0)")
except ImportError:
    logger.warning(
        "DeepAgents package not installed. "
        "Install with: pip install deepagents"
    )
    SubAgentMiddleware = None
    FilesystemMiddleware = None
    FilesystemBackend = None
    ChatOpenAI = None

# Import global middleware cache to prevent duplication errors
try:
    from app.agent.langchain.deepagent_workflow import _global_middleware_cache
except ImportError:
    # Fallback if deepagent_workflow not available
    _global_middleware_cache = {}


class DeepCodingAgent(BaseAgent):
    """Advanced coding agent using DeepAgents framework.

    DeepAgents (v0.3.0) provides enhanced capabilities over basic LangChain:
    - File system operations via FilesystemMiddleware
    - Sub-agent delegation for complex tasks via SubAgentMiddleware

    Note: TodoListMiddleware and SummarizationMiddleware are not available in v0.3.0

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
        """Initialize the DeepAgents agent with SINGLETON middleware.

        Note: DeepAgents 0.3.0 API differences:
        - TodoListMiddleware is not available
        - FilesystemMiddleware requires a backend parameter
        - SubAgentMiddleware requires default_model parameter

        IMPORTANT: Uses global singleton middleware to prevent duplication errors
        """
        try:
            # Create LLM for middleware
            # Using vLLM endpoint for efficiency
            llm = ChatOpenAI(
                base_url="http://localhost:8000/v1",  # vLLM endpoint
                model="deepseek-coder-v2",
                temperature=0.7,
                api_key="EMPTY"
            )

            # Build middleware list using SINGLETON pattern
            middleware_list = []

            # FilesystemMiddleware - use singleton
            if "filesystem" not in _global_middleware_cache:
                fs_backend = FilesystemBackend(root_dir="./workspace/.deepagents/shared")
                _global_middleware_cache["filesystem"] = FilesystemMiddleware(backend=fs_backend)
                logger.info("✅ Created SINGLETON FilesystemMiddleware for DeepCodingAgent")
            else:
                logger.info("♻️  Reusing FilesystemMiddleware singleton for DeepCodingAgent")
            middleware_list.append(_global_middleware_cache["filesystem"])

            # SubAgentMiddleware - use singleton
            if "subagent" not in _global_middleware_cache:
                _global_middleware_cache["subagent"] = SubAgentMiddleware(
                    default_model=llm,
                    default_tools=[]
                )
                logger.info("✅ Created SINGLETON SubAgentMiddleware for DeepCodingAgent")
            else:
                logger.info("♻️  Reusing SubAgentMiddleware singleton for DeepCodingAgent")
            middleware_list.append(_global_middleware_cache["subagent"])

            # Create deep agent with coding-focused configuration
            self.agent = create_deep_agent(
                model=llm,
                tools=[],
                system_prompt="""You are an advanced coding assistant with the ability to:
1. Read and write files
2. Execute shell commands safely
3. Delegate sub-tasks to specialized agents

For each coding request:
1. First, create a detailed plan
2. Execute each step methodically
3. Verify the results
4. Report completion status

Always prioritize code quality and safety.""",
                middleware=middleware_list,
            )
            logger.info("DeepAgents agent created with SINGLETON middleware (v0.3.0 compatible)")
        except Exception as e:
            logger.error(f"Failed to initialize DeepAgents: {e}")
            logger.exception("Full traceback:")
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

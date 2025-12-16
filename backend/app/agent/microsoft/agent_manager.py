"""Agent manager using Microsoft Agent Framework."""
import logging
from typing import List, Dict, Any, AsyncGenerator, Optional
from app.services.vllm_client import vllm_router
from app.agent.base.interface import BaseAgent, BaseAgentManager

logger = logging.getLogger(__name__)


class CodingAgent(BaseAgent):
    """Coding agent that uses vLLM models for code generation and reasoning."""

    def __init__(self):
        """Initialize coding agent."""
        self.conversation_history: List[Dict[str, str]] = []
        logger.info("CodingAgent (Microsoft) initialized")

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
        # Get appropriate client
        client = vllm_router.get_client(task_type)

        # Build messages
        messages = []
        if system_prompt:
            messages.append({"role": "system", "content": system_prompt})

        # Add conversation history
        messages.extend(self.conversation_history)

        # Add user message
        messages.append({"role": "user", "content": user_message})

        try:
            # Get response from vLLM
            response = await client.chat_completion(
                messages=messages,
                temperature=0.7,
                max_tokens=2048
            )

            assistant_message = response.choices[0].message.content

            # Update conversation history
            self.conversation_history.append({"role": "user", "content": user_message})
            self.conversation_history.append({"role": "assistant", "content": assistant_message})

            # Keep only last 10 messages to avoid context overflow
            if len(self.conversation_history) > 10:
                self.conversation_history = self.conversation_history[-10:]

            return assistant_message

        except Exception as e:
            logger.error(f"Error processing message: {e}")
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
        # Get appropriate client
        client = vllm_router.get_client(task_type)

        # Build messages
        messages = []
        if system_prompt:
            messages.append({"role": "system", "content": system_prompt})

        # Add conversation history
        messages.extend(self.conversation_history)

        # Add user message
        messages.append({"role": "user", "content": user_message})

        try:
            full_response = ""

            # Stream response from vLLM
            async for chunk in client.stream_chat_completion(
                messages=messages,
                temperature=0.7,
                max_tokens=2048
            ):
                full_response += chunk
                yield chunk

            # Update conversation history
            self.conversation_history.append({"role": "user", "content": user_message})
            self.conversation_history.append({"role": "assistant", "content": full_response})

            # Keep only last 10 messages
            if len(self.conversation_history) > 10:
                self.conversation_history = self.conversation_history[-10:]

        except Exception as e:
            logger.error(f"Error streaming message: {e}")
            raise

    def clear_history(self) -> None:
        """Clear conversation history."""
        self.conversation_history = []
        logger.info("Conversation history cleared")

    def get_history(self) -> List[Dict[str, str]]:
        """Get conversation history.

        Returns:
            List of conversation messages
        """
        return self.conversation_history.copy()


class AgentManager(BaseAgentManager):
    """Manager for multiple agent sessions."""

    def __init__(self):
        """Initialize agent manager."""
        self.agents: Dict[str, CodingAgent] = {}
        logger.info("AgentManager (Microsoft) initialized")

    def get_or_create_agent(self, session_id: str) -> CodingAgent:
        """Get existing agent or create new one for session.

        Args:
            session_id: Session identifier

        Returns:
            CodingAgent instance
        """
        if session_id not in self.agents:
            self.agents[session_id] = CodingAgent()
            logger.info(f"Created new agent for session {session_id}")
        return self.agents[session_id]

    def delete_agent(self, session_id: str) -> None:
        """Delete agent for session.

        Args:
            session_id: Session identifier
        """
        if session_id in self.agents:
            del self.agents[session_id]
            logger.info(f"Deleted agent for session {session_id}")

    def get_active_sessions(self) -> List[str]:
        """Get list of active session IDs.

        Returns:
            List of session IDs
        """
        return list(self.agents.keys())


# Global agent manager instance
agent_manager = AgentManager()

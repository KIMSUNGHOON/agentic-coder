"""Agent manager using LangChain framework."""
import logging
from typing import List, Dict, Any, AsyncGenerator, Optional
from langchain_openai import ChatOpenAI
from langchain_core.messages import HumanMessage, AIMessage, SystemMessage
from langchain_core.prompts import ChatPromptTemplate, MessagesPlaceholder
from app.core.config import settings
from app.agent.base.interface import BaseAgent, BaseAgentManager

logger = logging.getLogger(__name__)


class LangChainAgent(BaseAgent):
    """Coding agent that uses LangChain with vLLM backend."""

    def __init__(self):
        """Initialize LangChain coding agent."""
        self.conversation_history: List[Dict[str, str]] = []

        # Initialize LLM clients for reasoning and coding
        # LangChain's ChatOpenAI works with OpenAI-compatible APIs (vLLM)
        self.reasoning_llm = ChatOpenAI(
            base_url=settings.vllm_reasoning_endpoint,
            model=settings.reasoning_model,
            temperature=0.7,
            max_tokens=2048,
            api_key="not-needed",  # vLLM doesn't require API key
        )

        self.coding_llm = ChatOpenAI(
            base_url=settings.vllm_coding_endpoint,
            model=settings.coding_model,
            temperature=0.7,
            max_tokens=2048,
            api_key="not-needed",
        )

        logger.info("LangChainAgent initialized")

    def _get_llm(self, task_type: str) -> ChatOpenAI:
        """Get appropriate LLM based on task type."""
        if task_type == "reasoning":
            return self.reasoning_llm
        return self.coding_llm

    def _build_messages(
        self,
        user_message: str,
        system_prompt: Optional[str] = None
    ) -> List:
        """Build message list for LangChain."""
        messages = []

        if system_prompt:
            messages.append(SystemMessage(content=system_prompt))

        # Add conversation history
        for msg in self.conversation_history:
            if msg["role"] == "user":
                messages.append(HumanMessage(content=msg["content"]))
            elif msg["role"] == "assistant":
                messages.append(AIMessage(content=msg["content"]))

        # Add current user message
        messages.append(HumanMessage(content=user_message))

        return messages

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
        llm = self._get_llm(task_type)
        messages = self._build_messages(user_message, system_prompt)

        try:
            # Get response from LangChain
            response = await llm.ainvoke(messages)
            assistant_message = response.content

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
        llm = self._get_llm(task_type)
        messages = self._build_messages(user_message, system_prompt)

        try:
            full_response = ""

            # Stream response from LangChain
            async for chunk in llm.astream(messages):
                if chunk.content:
                    full_response += chunk.content
                    yield chunk.content

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


class LangChainAgentManager(BaseAgentManager):
    """Manager for multiple LangChain agent sessions."""

    def __init__(self):
        """Initialize agent manager."""
        self.agents: Dict[str, LangChainAgent] = {}
        logger.info("LangChainAgentManager initialized")

    def get_or_create_agent(self, session_id: str) -> LangChainAgent:
        """Get existing agent or create new one for session.

        Args:
            session_id: Session identifier

        Returns:
            LangChainAgent instance
        """
        if session_id not in self.agents:
            self.agents[session_id] = LangChainAgent()
            logger.info(f"Created new LangChain agent for session {session_id}")
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
agent_manager = LangChainAgentManager()

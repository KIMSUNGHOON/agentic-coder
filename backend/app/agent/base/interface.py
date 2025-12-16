"""Abstract base interfaces for agent frameworks.

This module defines the common interfaces that all agent framework
implementations (Microsoft, LangChain, etc.) must follow.
"""
from abc import ABC, abstractmethod
from typing import List, Dict, Any, AsyncGenerator, Optional


class BaseAgent(ABC):
    """Abstract base class for coding agents."""

    @abstractmethod
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
        pass

    @abstractmethod
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
        pass

    @abstractmethod
    def clear_history(self) -> None:
        """Clear conversation history."""
        pass

    @abstractmethod
    def get_history(self) -> List[Dict[str, str]]:
        """Get conversation history.

        Returns:
            List of conversation messages
        """
        pass


class BaseAgentManager(ABC):
    """Abstract base class for managing agent sessions."""

    @abstractmethod
    def get_or_create_agent(self, session_id: str) -> BaseAgent:
        """Get existing agent or create new one for session.

        Args:
            session_id: Session identifier

        Returns:
            Agent instance
        """
        pass

    @abstractmethod
    def delete_agent(self, session_id: str) -> None:
        """Delete agent for session.

        Args:
            session_id: Session identifier
        """
        pass

    @abstractmethod
    def get_active_sessions(self) -> List[str]:
        """Get list of active session IDs.

        Returns:
            List of session IDs
        """
        pass


class BaseWorkflow(ABC):
    """Abstract base class for coding workflows."""

    @abstractmethod
    async def execute(
        self,
        user_request: str,
        context: Optional[Any] = None
    ) -> str:
        """Execute the coding workflow.

        Args:
            user_request: User's coding request
            context: Optional run context

        Returns:
            Final result from the workflow
        """
        pass

    @abstractmethod
    async def execute_stream(
        self,
        user_request: str,
        context: Optional[Any] = None
    ) -> AsyncGenerator[Dict[str, Any], None]:
        """Execute the workflow with streaming updates.

        Args:
            user_request: User's coding request
            context: Optional run context

        Yields:
            Updates with workflow progress
        """
        pass


class BaseWorkflowManager(ABC):
    """Abstract base class for managing workflow sessions."""

    @abstractmethod
    def get_or_create_workflow(self, session_id: str) -> BaseWorkflow:
        """Get existing workflow or create new one for session.

        Args:
            session_id: Session identifier

        Returns:
            Workflow instance
        """
        pass

    @abstractmethod
    def delete_workflow(self, session_id: str) -> None:
        """Delete workflow for session.

        Args:
            session_id: Session identifier
        """
        pass

    @abstractmethod
    def get_active_sessions(self) -> List[str]:
        """Get list of active session IDs.

        Returns:
            List of session IDs
        """
        pass

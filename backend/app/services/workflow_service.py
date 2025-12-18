"""
Workflow Service Layer

Handles workflow creation, caching, and execution business logic.
Separates business logic from HTTP routing concerns.
"""
import logging
import os
import re
from datetime import datetime
from typing import Dict, Any, Optional, List
from pathlib import Path

from app.core.config import settings
from app.core.session_store import SessionStore, FrameworkType
from app.api.models import ChatRequest, ChatMessage, ArtifactContext

logger = logging.getLogger(__name__)


class WorkflowService:
    """Service for managing workflows across different frameworks."""

    def __init__(self, session_store: SessionStore):
        """
        Initialize workflow service.

        Args:
            session_store: Session storage for framework and workspace tracking
        """
        self.session_store = session_store
        # Cache for DeepAgent workflows (to prevent middleware duplication)
        self._deepagent_workflows: Dict[str, Any] = {}

    async def suggest_project_name(self, user_message: str) -> str:
        """
        Use LLM to suggest a project name based on user's prompt.

        Args:
            user_message: User's request/prompt

        Returns:
            Suggested project name (lowercase with underscores)
        """
        try:
            from langchain_openai import ChatOpenAI
            from langchain_core.messages import HumanMessage, SystemMessage

            # Use fast model for project name suggestion
            llm = ChatOpenAI(
                base_url=settings.vllm_coding_endpoint,
                model=settings.coding_model,
                temperature=0.3,
                api_key="EMPTY",
                max_tokens=50
            )

            messages = [
                SystemMessage(content="""You are a project naming assistant. Given a user's request, suggest a concise, descriptive project name.

Rules:
- Use lowercase with underscores (e.g., todo_app, blog_system, user_auth)
- Keep it short (2-4 words max)
- Make it descriptive of the main feature/purpose
- Return ONLY the project name, nothing else

Examples:
"Create a todo list app" -> todo_app
"Build a blog system with authentication" -> blog_system
"Make a REST API for users" -> user_api
"Implement user authentication" -> user_auth
"Create a chat application" -> chat_app"""),
                HumanMessage(content=f"Suggest a project name for: {user_message[:200]}")
            ]

            response = await llm.ainvoke(messages)
            project_name = response.content.strip().lower()

            # Clean up the project name
            project_name = re.sub(r'[^a-z0-9_]', '_', project_name)
            project_name = re.sub(r'_+', '_', project_name)
            project_name = project_name.strip('_')

            # Fallback if empty or too long
            if not project_name or len(project_name) > 50:
                project_name = f"project_{datetime.now().strftime('%Y%m%d_%H%M%S')}"

            logger.info(f"Suggested project name: {project_name}")
            return project_name
        except Exception as e:
            logger.warning(f"Failed to suggest project name: {e}, using timestamp")
            return f"project_{datetime.now().strftime('%Y%m%d_%H%M%S')}"

    def _is_project_directory(self, path: str) -> bool:
        """
        Check if path is already a project directory (direct child of workspace).

        Args:
            path: Path to check

        Returns:
            True if path is a project directory
        """
        if not os.path.exists(path):
            return False
        basename = os.path.basename(path)
        parent = os.path.dirname(path)
        parent_basename = os.path.basename(parent)
        # It's a project if parent is named "workspace" and basename is not "workspace"
        return parent_basename == "workspace" and basename != "workspace"

    async def get_or_create_workspace(
        self,
        session_id: str,
        user_message: str,
        base_workspace: Optional[str] = None
    ) -> str:
        """
        Get existing workspace or create a new one for the session.

        Args:
            session_id: Session identifier
            user_message: User's message (for project name suggestion)
            base_workspace: Optional base workspace path

        Returns:
            Workspace path for the session
        """
        # Check if workspace already exists for this session
        existing_workspace = await self.session_store.get_workspace(session_id, default=None)
        if existing_workspace:
            logger.info(f"Reusing existing workspace for session {session_id}: {existing_workspace}")
            return existing_workspace

        # Create new workspace for first request in this session
        base_workspace = base_workspace or "/home/user/workspace"

        # Check if base_workspace is already a project directory
        if self._is_project_directory(base_workspace):
            workspace = base_workspace
            logger.info(f"Using existing project directory: {workspace}")
        else:
            # Need to create a new project directory
            if not base_workspace.endswith("/workspace"):
                workspace_root = (
                    base_workspace if os.path.basename(base_workspace) == "workspace"
                    else base_workspace
                )
            else:
                workspace_root = base_workspace

            # Let LLM suggest a project name based on the user's request
            project_name = await self.suggest_project_name(user_message)

            # Check if project already exists, add suffix if needed
            candidate_workspace = os.path.join(workspace_root, project_name)
            counter = 1
            while os.path.exists(candidate_workspace):
                candidate_workspace = os.path.join(workspace_root, f"{project_name}_{counter}")
                counter += 1

            workspace = candidate_workspace
            logger.info(f"Created new project workspace '{os.path.basename(workspace)}' in {workspace_root}")

        # Store workspace for this session
        await self.session_store.set_workspace(session_id, workspace)

        # Ensure project workspace exists
        if not os.path.exists(workspace):
            os.makedirs(workspace, exist_ok=True)
            logger.info(f"Created workspace directory: {workspace}")

        return workspace

    async def get_workflow(
        self,
        session_id: str,
        workspace: str,
        workflow_manager: Any = None
    ) -> Any:
        """
        Get or create workflow for the session based on selected framework.

        Args:
            session_id: Session identifier
            workspace: Workspace path
            workflow_manager: Standard workflow manager (if using standard framework)

        Returns:
            Workflow instance (either DeepAgent or Standard)

        Raises:
            Exception: If DeepAgents not available when requested
        """
        # Check which framework to use for this session
        selected_framework = await self.session_store.get_framework(session_id)

        # Use Standard workflow with optional DeepAgents middleware
        # This maintains Standard's proven scenario while enabling DeepAgents features
        enable_deepagents = (selected_framework == "deepagents")

        if enable_deepagents:
            logger.info(
                f"Session {session_id} using Standard workflow WITH DeepAgents middleware"
            )
        else:
            logger.info(
                f"Session {session_id} using Standard workflow WITHOUT DeepAgents"
            )

        return self._get_standard_workflow(session_id, workflow_manager, enable_deepagents)

    async def _get_deepagent_workflow(self, session_id: str, workspace: str) -> Any:
        """
        Get or create DeepAgent workflow.

        Args:
            session_id: Session identifier
            workspace: Workspace path

        Returns:
            DeepAgent workflow instance

        Raises:
            Exception: If DeepAgents not available
        """
        from app.agent.langchain.deepagent_workflow import (
            DeepAgentWorkflowManager,
            DEEPAGENTS_AVAILABLE
        )
        import time

        if not DEEPAGENTS_AVAILABLE:
            raise Exception(
                "DeepAgents framework not available. "
                "Install with: pip install deepagents tavily-python"
            )

        # Get or create DeepAgent workflow (cached to prevent middleware duplication)
        if session_id not in self._deepagent_workflows:
            try:
                # Use unique agent_id to prevent FilesystemMiddleware path conflicts
                # This allows:
                # 1. Multiple sessions to use the same workspace
                # 2. Backend restart without middleware conflicts
                # 3. FilesystemMiddleware to work properly
                unique_agent_id = f"{session_id}_{int(time.time() * 1000)}"

                logger.info(
                    f"Creating new DeepAgents workflow for session {session_id} "
                    f"(agent_id: {unique_agent_id}) with workspace {workspace}"
                )
                self._deepagent_workflows[session_id] = DeepAgentWorkflowManager(
                    agent_id=unique_agent_id,
                    model_name="gpt-4o",
                    temperature=0.7,
                    enable_subagents=False,     # DISABLED: Causes duplication error
                    enable_filesystem=False,    # DISABLED: Not needed (we save files directly)
                    enable_parallel=True,
                    max_parallel_agents=25,
                    workspace=workspace
                )
                logger.info(f"✅ Successfully created DeepAgents workflow for session {session_id}")
            except Exception as e:
                # If creation fails, ensure it's not in cache so next attempt can retry cleanly
                self._deepagent_workflows.pop(session_id, None)
                logger.error(f"❌ Failed to create DeepAgents workflow for session {session_id}: {e}")
                raise Exception(f"Failed to initialize DeepAgents workflow: {str(e)}")
        else:
            logger.info(f"♻️  Reusing cached DeepAgents workflow for session {session_id}")

        return self._deepagent_workflows[session_id]

    def _get_standard_workflow(self, session_id: str, workflow_manager: Any, enable_deepagents: bool = False) -> Any:
        """
        Get or create standard workflow.

        Args:
            session_id: Session identifier
            workflow_manager: Standard workflow manager instance
            enable_deepagents: Whether to enable DeepAgents middleware

        Returns:
            Standard workflow instance
        """
        workflow = workflow_manager.get_or_create_workflow(session_id, enable_deepagents=enable_deepagents)
        if enable_deepagents:
            logger.info(f"Using Standard workflow WITH DeepAgents middleware for session {session_id}")
        else:
            logger.info(f"Using Standard workflow for session {session_id}")
        return workflow

    def build_context_string(
        self,
        messages: Optional[List[ChatMessage]] = None,
        artifacts: Optional[List[ArtifactContext]] = None
    ) -> str:
        """
        Build context string from previous messages and artifacts.

        Args:
            messages: Previous chat messages
            artifacts: Existing code artifacts

        Returns:
            Formatted context string
        """
        context_str = ""

        # Add previous messages as context
        if messages:
            context_str += "\n<previous_conversation>\n"
            for msg in messages[-5:]:  # Last 5 messages
                context_str += f"{msg.role.upper()}: {msg.content}\n"
            context_str += "</previous_conversation>\n"

        # Add existing artifacts as context
        if artifacts:
            context_str += "\n<existing_code>\n"
            for artifact in artifacts:
                context_str += f"```{artifact.language} {artifact.filename}\n{artifact.content}\n```\n\n"
            context_str += "</existing_code>\n"

        return context_str

    async def clear_workflow_cache(self, session_id: str) -> None:
        """
        Clear cached workflow for a session.

        Args:
            session_id: Session identifier to clear
        """
        if session_id in self._deepagent_workflows:
            del self._deepagent_workflows[session_id]
            logger.info(f"Cleared cached DeepAgent workflow for session {session_id}")

    async def clear_all_caches(self) -> int:
        """
        Clear all cached workflows.

        Returns:
            Number of workflows cleared
        """
        count = len(self._deepagent_workflows)
        self._deepagent_workflows.clear()
        logger.info(f"Cleared {count} cached DeepAgent workflows")
        return count

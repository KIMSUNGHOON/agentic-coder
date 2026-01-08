"""Session Manager for Agentic Coder CLI

Handles:
- Session ID generation and management
- Conversation history persistence
- Workspace management
- Integration with DynamicWorkflowManager
- Session save/resume functionality
"""

import json
import asyncio
from pathlib import Path
from datetime import datetime
from typing import List, Dict, Any, Optional, AsyncIterator


class SessionManager:
    """Manages CLI sessions with persistence and workflow integration"""

    def __init__(
        self,
        workspace: str = None,
        session_id: Optional[str] = None,
        model: str = None,
        auto_save: bool = True
    ):
        """Initialize session manager

        Args:
            workspace: Working directory for code generation (default: from .env DEFAULT_WORKSPACE or ".")
            session_id: Optional session ID to resume
            model: LLM model to use (default: from .env LLM_MODEL or deepseek-ai/DeepSeek-R1)
            auto_save: Whether to auto-save after each interaction
        """
        import os

        # Get workspace from .env if not provided
        if workspace is None:
            workspace = os.getenv("DEFAULT_WORKSPACE", ".")

        # Get model from .env if not provided
        if model is None:
            model = os.getenv("LLM_MODEL", "deepseek-ai/DeepSeek-R1")

        self.workspace = Path(workspace).resolve()
        self.model = model
        self.auto_save = auto_save

        # Session directory
        self.session_dir = self.workspace / ".agentic-coder" / "sessions"
        self.session_dir.mkdir(parents=True, exist_ok=True)

        # Initialize or resume session
        if session_id:
            self.session_id = session_id
            self._load_session()
        else:
            self.session_id = self._generate_session_id()
            self.conversation_history = []
            self.metadata = {
                "created_at": datetime.now().isoformat(),
                "model": model,
                "workspace": str(self.workspace)
            }

        # Initialize workflow manager (lazy load to avoid import errors)
        self.workflow_mgr = None

    def _generate_session_id(self) -> str:
        """Generate unique session ID"""
        timestamp = datetime.now().strftime("%Y%m%d-%H%M%S")
        return f"session-{timestamp}"

    def _get_session_file(self) -> Path:
        """Get session file path"""
        return self.session_dir / f"{self.session_id}.json"

    def _load_session(self):
        """Load session from file"""
        session_file = self._get_session_file()

        if not session_file.exists():
            raise FileNotFoundError(
                f"Session '{self.session_id}' not found at {session_file}"
            )

        with open(session_file, 'r', encoding='utf-8') as f:
            data = json.load(f)

        self.conversation_history = data.get("conversation_history", [])
        self.metadata = data.get("metadata", {})

        # Update workspace if different
        saved_workspace = self.metadata.get("workspace")
        if saved_workspace and saved_workspace != str(self.workspace):
            print(f"⚠️  Session workspace: {saved_workspace}")
            print(f"   Current workspace: {self.workspace}")

    def save_session(self):
        """Save session to file"""
        if not self.auto_save:
            return

        session_file = self._get_session_file()

        # Update metadata
        self.metadata["updated_at"] = datetime.now().isoformat()
        self.metadata["message_count"] = len(self.conversation_history)

        data = {
            "session_id": self.session_id,
            "metadata": self.metadata,
            "conversation_history": self.conversation_history
        }

        with open(session_file, 'w', encoding='utf-8') as f:
            json.dump(data, f, indent=2, ensure_ascii=False)

    def add_message(self, role: str, content: str):
        """Add message to conversation history

        Args:
            role: 'user' or 'assistant'
            content: Message content
        """
        self.conversation_history.append({
            "role": role,
            "content": content,
            "timestamp": datetime.now().isoformat()
        })

        if self.auto_save:
            self.save_session()

    async def execute_streaming_workflow(
        self,
        user_request: str
    ) -> AsyncIterator[Dict[str, Any]]:
        """Execute workflow with streaming updates

        Args:
            user_request: User's request

        Yields:
            Stream updates from workflow execution
        """
        # Lazy import to avoid circular dependencies
        if self.workflow_mgr is None:
            from app.agent.langgraph.dynamic_workflow import DynamicWorkflowManager
            self.workflow_mgr = DynamicWorkflowManager()

        # Add user message to history
        self.add_message("user", user_request)

        # Execute workflow
        final_response = None
        async for update in self.workflow_mgr.execute_streaming_workflow(
            user_request=user_request,
            workspace_dir=str(self.workspace),
            conversation_history=self.conversation_history
        ):
            # Store final response
            if update.get("type") == "final_response":
                final_response = update.get("content", "")

            yield update

        # Add assistant response to history
        if final_response:
            self.add_message("assistant", final_response)

    def get_history_summary(self) -> Dict[str, Any]:
        """Get summary of conversation history

        Returns:
            Dictionary with history statistics
        """
        user_messages = [m for m in self.conversation_history if m.get("role") == "user"]
        assistant_messages = [m for m in self.conversation_history if m.get("role") == "assistant"]

        return {
            "session_id": self.session_id,
            "total_messages": len(self.conversation_history),
            "user_messages": len(user_messages),
            "assistant_messages": len(assistant_messages),
            "created_at": self.metadata.get("created_at"),
            "updated_at": self.metadata.get("updated_at"),
            "workspace": str(self.workspace),
            "model": self.model
        }

    def get_context_info(self) -> Dict[str, Any]:
        """Get current context information using ContextManager

        Returns:
            Dictionary with extracted context
        """
        from app.utils.context_manager import ContextManager

        context_mgr = ContextManager()
        key_info = context_mgr.extract_key_info(self.conversation_history)

        return {
            "files_mentioned": key_info.get("files_mentioned", []),
            "errors_encountered": key_info.get("errors_encountered", []),
            "decisions_made": key_info.get("decisions_made", []),
            "user_preferences": key_info.get("user_preferences", [])
        }

    def list_sessions(self) -> List[Dict[str, str]]:
        """List all available sessions

        Returns:
            List of session info dictionaries
        """
        sessions = []

        for session_file in self.session_dir.glob("session-*.json"):
            try:
                with open(session_file, 'r', encoding='utf-8') as f:
                    data = json.load(f)

                metadata = data.get("metadata", {})
                sessions.append({
                    "session_id": data.get("session_id", session_file.stem),
                    "created_at": metadata.get("created_at", "Unknown"),
                    "updated_at": metadata.get("updated_at", "Unknown"),
                    "message_count": len(data.get("conversation_history", [])),
                    "workspace": metadata.get("workspace", "Unknown")
                })
            except Exception:
                continue

        # Sort by updated_at (most recent first)
        sessions.sort(key=lambda s: s.get("updated_at", ""), reverse=True)

        return sessions

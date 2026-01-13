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

        # Get base workspace from .env if not provided
        if workspace is None:
            workspace = os.getenv("DEFAULT_WORKSPACE", ".")

        # Get model from .env if not provided
        if model is None:
            model = os.getenv("LLM_MODEL", "deepseek-ai/DeepSeek-R1")

        self.base_workspace = Path(workspace).resolve()
        self.model = model
        self.auto_save = auto_save

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
                "base_workspace": str(self.base_workspace)
            }

        # Actual workspace: base_workspace/session_id
        self.workspace = self.base_workspace / self.session_id
        self.workspace.mkdir(parents=True, exist_ok=True)

        # Session metadata directory (separate from workspace)
        self.session_dir = self.base_workspace / ".agentic-coder" / "sessions"
        self.session_dir.mkdir(parents=True, exist_ok=True)

        # Initialize workflow manager (lazy load to avoid import errors)
        self.workflow_mgr = None

        # Phase 3: Statistics tracking
        self.statistics = self.metadata.get("statistics", {
            "tool_usage": {},          # {tool_name: count}
            "files_created": [],       # List of created file paths
            "files_modified": [],      # List of modified file paths
            "total_iterations": 0,     # Total workflow iterations
            "errors_count": 0,         # Number of errors encountered
            "workspace_snapshots": []  # Periodic workspace size snapshots
        })

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

        # Update base workspace if different
        saved_base = self.metadata.get("base_workspace", self.metadata.get("workspace"))
        if saved_base and saved_base != str(self.base_workspace):
            print(f"⚠️  Session base workspace: {saved_base}")
            print(f"   Current base workspace: {self.base_workspace}")

    def save_session(self):
        """Save session to file"""
        if not self.auto_save:
            return

        session_file = self._get_session_file()

        # Update metadata
        self.metadata["updated_at"] = datetime.now().isoformat()
        self.metadata["message_count"] = len(self.conversation_history)
        # Phase 3: Save statistics
        self.metadata["statistics"] = self.statistics

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

    async def execute_tool_use_workflow(
        self,
        user_request: str,
        max_iterations: int = 15
    ) -> AsyncIterator[Dict[str, Any]]:
        """Execute workflow using Tool Use pattern (NEW - Dynamic LLM-driven)

        Instead of hardcoded workflow types (QUICK_QA, CODE_GENERATION),
        the LLM freely decides which concrete tools to call.

        This is the Claude Code / ChatGPT approach - maximum flexibility.

        Args:
            user_request: User's request
            max_iterations: Maximum tool call iterations (prevent infinite loops)

        Yields:
            Stream updates from tool execution
        """
        from core.supervisor import supervisor

        # Add user message to history
        self.add_message("user", user_request)

        # Build context
        context = {
            "conversation_history": self.conversation_history,
            "workspace": str(self.workspace),
            "session_id": self.session_id,
            "model": self.model
        }

        # Execute with Tool Use pattern
        final_response = None
        async for update in supervisor.execute_with_tools(
            user_request=user_request,
            context=context,
            max_iterations=max_iterations
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

    async def cleanup_temporary_files(self) -> int:
        """Remove temporary files from workspace

        Removes files matching temporary patterns:
        - code_*.txt (code_1.txt, code_2.txt, etc.)
        - temp_*.* (temp_script.py, temp_test.js, temp_data.txt)
        - tmp_* (tmp_anything)
        - test_*.txt (test_1.txt, test_2.txt)

        Returns:
            Number of files removed
        """
        import logging
        logger = logging.getLogger(__name__)

        temp_patterns = [
            "code_*.txt",
            "temp_*.*",
            "tmp_*",
            "test_*.txt"
        ]

        removed_count = 0
        removed_files = []

        for pattern in temp_patterns:
            for file_path in self.workspace.glob(pattern):
                try:
                    file_path.unlink()
                    removed_files.append(file_path.name)
                    removed_count += 1
                    logger.info(f"🗑️  Cleaned up temporary file: {file_path.name}")
                except Exception as e:
                    logger.warning(f"Failed to remove {file_path}: {e}")

        if removed_count > 0:
            logger.info(f"✅ Cleaned up {removed_count} temporary files: {', '.join(removed_files)}")
        else:
            logger.debug("No temporary files found to clean up")

        return removed_count

    async def close(self) -> Dict[str, Any]:
        """Close session with cleanup and save

        Returns:
            Session summary report
        """
        import logging
        logger = logging.getLogger(__name__)

        # 1. Cleanup temporary files
        removed = await self.cleanup_temporary_files()

        # 2. Generate report
        summary = self.get_history_summary()
        summary["cleanup"] = {
            "removed_files": removed,
            "message": f"Cleaned up {removed} temporary files" if removed > 0 else "No temporary files found"
        }

        # 3. Save session
        if self.auto_save:
            self.save_session()
            logger.info(f"💾 Session {self.session_id} saved")

        # 4. Log summary
        logger.info(f"📊 Session {self.session_id} closed:")
        logger.info(f"   - Interactions: {summary['total_messages']}")
        logger.info(f"   - Workspace: {summary['workspace']}")
        if removed > 0:
            logger.info(f"   - Cleaned up: {removed} files")

        return summary

    def get_workspace_usage(self) -> Dict[str, Any]:
        """Calculate workspace disk usage

        Returns:
            Dict with workspace statistics:
            - total_size_bytes: Total size in bytes
            - total_size_mb: Total size in MB
            - file_count: Number of files
            - largest_files: Top 5 largest files
        """
        import os

        total_size = 0
        file_count = 0
        file_sizes = []  # [(path, size), ...]

        try:
            for root, dirs, files in os.walk(self.workspace):
                for file in files:
                    file_path = os.path.join(root, file)
                    try:
                        size = os.path.getsize(file_path)
                        total_size += size
                        file_count += 1
                        # Store relative path and size
                        rel_path = os.path.relpath(file_path, self.workspace)
                        file_sizes.append((rel_path, size))
                    except (OSError, FileNotFoundError):
                        continue

            # Sort by size and get top 5
            file_sizes.sort(key=lambda x: x[1], reverse=True)
            largest_files = [
                {"path": path, "size_bytes": size, "size_mb": round(size / (1024 * 1024), 2)}
                for path, size in file_sizes[:5]
            ]

            return {
                "total_size_bytes": total_size,
                "total_size_mb": round(total_size / (1024 * 1024), 2),
                "file_count": file_count,
                "largest_files": largest_files,
                "workspace_path": str(self.workspace)
            }
        except Exception as e:
            return {
                "error": str(e),
                "workspace_path": str(self.workspace)
            }

    def record_tool_usage(self, tool_name: str, success: bool = True):
        """Record tool usage statistics

        Args:
            tool_name: Name of the tool used
            success: Whether the tool execution was successful
        """
        # Increment tool usage count
        if tool_name not in self.statistics["tool_usage"]:
            self.statistics["tool_usage"][tool_name] = {"success": 0, "failure": 0}

        if success:
            self.statistics["tool_usage"][tool_name]["success"] += 1
        else:
            self.statistics["tool_usage"][tool_name]["failure"] += 1
            self.statistics["errors_count"] += 1

    def record_file_operation(self, operation: str, file_path: str):
        """Record file creation or modification

        Args:
            operation: "created" or "modified"
            file_path: Path to the file
        """
        if operation == "created" and file_path not in self.statistics["files_created"]:
            self.statistics["files_created"].append(file_path)
        elif operation == "modified" and file_path not in self.statistics["files_modified"]:
            self.statistics["files_modified"].append(file_path)

    def record_iteration(self):
        """Record a workflow iteration"""
        self.statistics["total_iterations"] += 1

    def snapshot_workspace(self):
        """Take a snapshot of current workspace size"""
        usage = self.get_workspace_usage()
        snapshot = {
            "timestamp": datetime.now().isoformat(),
            "size_mb": usage.get("total_size_mb", 0),
            "file_count": usage.get("file_count", 0)
        }
        self.statistics["workspace_snapshots"].append(snapshot)

        # Keep only last 10 snapshots
        if len(self.statistics["workspace_snapshots"]) > 10:
            self.statistics["workspace_snapshots"] = self.statistics["workspace_snapshots"][-10:]

    def get_statistics_summary(self) -> Dict[str, Any]:
        """Get comprehensive statistics summary

        Returns:
            Dictionary with all statistics
        """
        # Calculate top tools
        tool_usage = self.statistics.get("tool_usage", {})
        top_tools = sorted(
            [
                {
                    "tool": name,
                    "success": counts.get("success", 0),
                    "failure": counts.get("failure", 0),
                    "total": counts.get("success", 0) + counts.get("failure", 0)
                }
                for name, counts in tool_usage.items()
            ],
            key=lambda x: x["total"],
            reverse=True
        )[:10]

        # Get workspace usage
        workspace_usage = self.get_workspace_usage()

        # Calculate session duration
        created_at = datetime.fromisoformat(self.metadata.get("created_at", datetime.now().isoformat()))
        duration_seconds = (datetime.now() - created_at).total_seconds()

        return {
            "session_id": self.session_id,
            "duration_seconds": int(duration_seconds),
            "duration_formatted": self._format_duration(duration_seconds),
            "total_messages": len(self.conversation_history),
            "total_iterations": self.statistics.get("total_iterations", 0),
            "errors_count": self.statistics.get("errors_count", 0),
            "top_tools": top_tools,
            "files_created_count": len(self.statistics.get("files_created", [])),
            "files_modified_count": len(self.statistics.get("files_modified", [])),
            "workspace_usage": workspace_usage,
            "workspace_snapshots": self.statistics.get("workspace_snapshots", [])
        }

    def _format_duration(self, seconds: float) -> str:
        """Format duration in human-readable format"""
        hours = int(seconds // 3600)
        minutes = int((seconds % 3600) // 60)
        secs = int(seconds % 60)

        if hours > 0:
            return f"{hours}h {minutes}m {secs}s"
        elif minutes > 0:
            return f"{minutes}m {secs}s"
        else:
            return f"{secs}s"

    @staticmethod
    def cleanup_old_sessions(
        base_workspace: str = None,
        max_age_days: int = 30,
        max_size_mb: int = 1000,
        dry_run: bool = False
    ) -> Dict[str, Any]:
        """Clean up old or large sessions

        Args:
            base_workspace: Base workspace directory
            max_age_days: Maximum age in days (default: 30)
            max_size_mb: Maximum total workspace size in MB (default: 1000)
            dry_run: If True, only report what would be deleted

        Returns:
            Dict with cleanup statistics
        """
        import os
        import shutil
        from datetime import timedelta

        if base_workspace is None:
            base_workspace = os.getenv("DEFAULT_WORKSPACE", ".")

        base_path = Path(base_workspace).resolve()
        session_dir = base_path / ".agentic-coder" / "sessions"

        if not session_dir.exists():
            return {"error": "Session directory not found"}

        # Collect session information
        sessions_info = []
        total_size = 0

        for session_file in session_dir.glob("session-*.json"):
            try:
                with open(session_file, 'r', encoding='utf-8') as f:
                    data = json.load(f)

                metadata = data.get("metadata", {})
                session_id = data.get("session_id", session_file.stem)
                workspace_path = base_path / session_id

                # Get workspace size
                workspace_size = 0
                if workspace_path.exists():
                    for root, dirs, files in os.walk(workspace_path):
                        for file in files:
                            try:
                                workspace_size += os.path.getsize(os.path.join(root, file))
                            except (OSError, FileNotFoundError):
                                pass

                # Get session age
                created_at_str = metadata.get("created_at", datetime.now().isoformat())
                created_at = datetime.fromisoformat(created_at_str)
                age_days = (datetime.now() - created_at).days

                sessions_info.append({
                    "session_id": session_id,
                    "session_file": session_file,
                    "workspace_path": workspace_path,
                    "age_days": age_days,
                    "size_mb": round(workspace_size / (1024 * 1024), 2),
                    "size_bytes": workspace_size,
                    "created_at": created_at_str,
                    "updated_at": metadata.get("updated_at", created_at_str)
                })

                total_size += workspace_size

            except Exception:
                continue

        # Determine sessions to delete
        sessions_to_delete = []

        # Delete sessions older than max_age_days
        for session in sessions_info:
            if session["age_days"] > max_age_days:
                sessions_to_delete.append({
                    "session": session,
                    "reason": f"Age {session['age_days']} days > {max_age_days} days"
                })

        # If total size exceeds limit, delete oldest sessions
        total_size_mb = round(total_size / (1024 * 1024), 2)
        if total_size_mb > max_size_mb:
            # Sort by age (oldest first)
            remaining_sessions = [s for s in sessions_info
                                if s not in [d["session"] for d in sessions_to_delete]]
            remaining_sessions.sort(key=lambda x: x["age_days"], reverse=True)

            current_size_mb = total_size_mb
            for session in remaining_sessions:
                if current_size_mb <= max_size_mb:
                    break
                sessions_to_delete.append({
                    "session": session,
                    "reason": f"Total size {current_size_mb:.2f}MB > {max_size_mb}MB"
                })
                current_size_mb -= session["size_mb"]

        # Perform deletion
        deleted_count = 0
        deleted_size_mb = 0
        errors = []

        if not dry_run:
            for item in sessions_to_delete:
                session = item["session"]
                try:
                    # Delete workspace directory
                    if session["workspace_path"].exists():
                        shutil.rmtree(session["workspace_path"])

                    # Delete session file
                    if session["session_file"].exists():
                        session["session_file"].unlink()

                    deleted_count += 1
                    deleted_size_mb += session["size_mb"]

                except Exception as e:
                    errors.append({
                        "session_id": session["session_id"],
                        "error": str(e)
                    })

        return {
            "total_sessions": len(sessions_info),
            "total_size_mb": total_size_mb,
            "sessions_to_delete": len(sessions_to_delete),
            "deleted_count": deleted_count if not dry_run else 0,
            "deleted_size_mb": round(deleted_size_mb, 2) if not dry_run else 0,
            "dry_run": dry_run,
            "details": [
                {
                    "session_id": item["session"]["session_id"],
                    "age_days": item["session"]["age_days"],
                    "size_mb": item["session"]["size_mb"],
                    "reason": item["reason"]
                }
                for item in sessions_to_delete
            ],
            "errors": errors
        }

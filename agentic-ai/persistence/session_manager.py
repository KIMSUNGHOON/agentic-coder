"""Session Manager for Agentic 2.0

Thread and session management:
- Session creation and tracking
- Thread ID management
- Session metadata
- Active session monitoring
"""

import logging
import uuid
from typing import Dict, Any, List, Optional
from dataclasses import dataclass, field
from datetime import datetime

logger = logging.getLogger(__name__)


@dataclass
class Session:
    """Session information

    A session represents a conversation or workflow execution.
    Each session has a unique thread_id for checkpointing.
    """

    session_id: str
    thread_id: str
    task_description: str
    task_type: str
    workspace: str
    created_at: datetime = field(default_factory=datetime.now)
    updated_at: datetime = field(default_factory=datetime.now)
    status: str = "active"  # active, completed, failed, cancelled
    metadata: Dict[str, Any] = field(default_factory=dict)
    checkpoint_count: int = 0
    last_checkpoint: Optional[datetime] = None

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary"""
        return {
            "session_id": self.session_id,
            "thread_id": self.thread_id,
            "task_description": self.task_description,
            "task_type": self.task_type,
            "workspace": self.workspace,
            "created_at": self.created_at.isoformat(),
            "updated_at": self.updated_at.isoformat(),
            "status": self.status,
            "metadata": self.metadata,
            "checkpoint_count": self.checkpoint_count,
            "last_checkpoint": self.last_checkpoint.isoformat() if self.last_checkpoint else None,
        }


class SessionManager:
    """Manages sessions and thread IDs

    Features:
    - Session creation and tracking
    - Thread ID generation
    - Session status management
    - Active session monitoring
    - Session history

    Example:
        >>> manager = SessionManager()
        >>> session = manager.create_session(
        ...     task_description="Build a web app",
        ...     task_type="coding",
        ...     workspace="/workspace"
        ... )
        >>> print(session.thread_id)  # Use with checkpointer
        >>> manager.complete_session(session.session_id)
    """

    def __init__(self):
        """Initialize session manager"""
        self.sessions: Dict[str, Session] = {}
        self.active_sessions: List[str] = []

        logger.info("📝 SessionManager initialized")

    def create_session(
        self,
        task_description: str,
        task_type: str,
        workspace: str,
        metadata: Optional[Dict[str, Any]] = None,
    ) -> Session:
        """Create a new session

        Args:
            task_description: Description of the task
            task_type: Type of task (coding, research, data, general)
            workspace: Working directory
            metadata: Optional metadata

        Returns:
            Session object with unique session_id and thread_id
        """
        session_id = self._generate_session_id()
        thread_id = self._generate_thread_id()

        session = Session(
            session_id=session_id,
            thread_id=thread_id,
            task_description=task_description,
            task_type=task_type,
            workspace=workspace,
            metadata=metadata or {},
        )

        self.sessions[session_id] = session
        self.active_sessions.append(session_id)

        logger.info(f"📝 Session created: {session_id[:8]} (thread: {thread_id[:8]})")

        return session

    def get_session(self, session_id: str) -> Optional[Session]:
        """Get session by ID

        Args:
            session_id: Session ID

        Returns:
            Session object or None
        """
        return self.sessions.get(session_id)

    def get_session_by_thread(self, thread_id: str) -> Optional[Session]:
        """Get session by thread ID

        Args:
            thread_id: Thread ID

        Returns:
            Session object or None
        """
        for session in self.sessions.values():
            if session.thread_id == thread_id:
                return session
        return None

    def update_session(
        self,
        session_id: str,
        **kwargs
    ) -> bool:
        """Update session fields

        Args:
            session_id: Session ID
            **kwargs: Fields to update

        Returns:
            True if updated, False if session not found
        """
        session = self.sessions.get(session_id)
        if not session:
            logger.warning(f"Session not found: {session_id}")
            return False

        # Update fields
        for key, value in kwargs.items():
            if hasattr(session, key):
                setattr(session, key, value)

        session.updated_at = datetime.now()

        logger.debug(f"📝 Session updated: {session_id[:8]}")
        return True

    def record_checkpoint(self, session_id: str):
        """Record a checkpoint for session

        Args:
            session_id: Session ID
        """
        session = self.sessions.get(session_id)
        if session:
            session.checkpoint_count += 1
            session.last_checkpoint = datetime.now()
            session.updated_at = datetime.now()

            logger.debug(f"💾 Checkpoint recorded: {session_id[:8]} (#{session.checkpoint_count})")

    def complete_session(self, session_id: str):
        """Mark session as completed

        Args:
            session_id: Session ID
        """
        if self.update_session(session_id, status="completed"):
            if session_id in self.active_sessions:
                self.active_sessions.remove(session_id)
            logger.info(f"✅ Session completed: {session_id[:8]}")

    def fail_session(self, session_id: str, error: str):
        """Mark session as failed

        Args:
            session_id: Session ID
            error: Error message
        """
        if self.update_session(session_id, status="failed", metadata={"error": error}):
            if session_id in self.active_sessions:
                self.active_sessions.remove(session_id)
            logger.error(f"❌ Session failed: {session_id[:8]}: {error}")

    def cancel_session(self, session_id: str):
        """Cancel session

        Args:
            session_id: Session ID
        """
        if self.update_session(session_id, status="cancelled"):
            if session_id in self.active_sessions:
                self.active_sessions.remove(session_id)
            logger.info(f"🚫 Session cancelled: {session_id[:8]}")

    def list_active_sessions(self) -> List[Session]:
        """List all active sessions

        Returns:
            List of active Session objects
        """
        return [
            self.sessions[sid] for sid in self.active_sessions
            if sid in self.sessions
        ]

    def list_all_sessions(self) -> List[Session]:
        """List all sessions

        Returns:
            List of all Session objects
        """
        return list(self.sessions.values())

    def get_stats(self) -> Dict[str, Any]:
        """Get session statistics

        Returns:
            Dict with statistics
        """
        total = len(self.sessions)
        active = len(self.active_sessions)
        completed = sum(1 for s in self.sessions.values() if s.status == "completed")
        failed = sum(1 for s in self.sessions.values() if s.status == "failed")
        cancelled = sum(1 for s in self.sessions.values() if s.status == "cancelled")

        return {
            "total_sessions": total,
            "active_sessions": active,
            "completed_sessions": completed,
            "failed_sessions": failed,
            "cancelled_sessions": cancelled,
        }

    def cleanup_old_sessions(self, max_age_days: int = 7):
        """Clean up old completed/failed sessions

        Args:
            max_age_days: Maximum age in days to keep
        """
        now = datetime.now()
        to_remove = []

        for session_id, session in self.sessions.items():
            if session.status in ["completed", "failed", "cancelled"]:
                age_days = (now - session.updated_at).days
                if age_days > max_age_days:
                    to_remove.append(session_id)

        for session_id in to_remove:
            del self.sessions[session_id]
            if session_id in self.active_sessions:
                self.active_sessions.remove(session_id)

        if to_remove:
            logger.info(f"🧹 Cleaned up {len(to_remove)} old sessions")

    def _generate_session_id(self) -> str:
        """Generate unique session ID"""
        return f"session_{uuid.uuid4().hex[:16]}"

    def _generate_thread_id(self) -> str:
        """Generate unique thread ID for checkpointing"""
        return f"thread_{uuid.uuid4().hex[:16]}"

"""Thread-safe session storage with database persistence for multi-user support"""

import asyncio
from typing import Dict, Optional, Literal, Callable
from collections import defaultdict
import logging

from app.core.config import settings

logger = logging.getLogger(__name__)

FrameworkType = Literal["standard", "deepagents"]


class SessionStore:
    """
    Thread-safe session storage with database persistence.

    Manages session-specific state including:
    - Framework selection (standard vs deepagents)
    - Workspace paths
    - Any other session-scoped configuration

    Thread Safety:
    - Uses asyncio.Lock per session for fine-grained locking
    - Prevents race conditions in concurrent requests
    - Allows parallel access to different sessions

    Persistence:
    - In-memory cache for fast access
    - Database persistence for multi-user support
    - Auto-restore from database on cache miss
    """

    def __init__(self, db_session_factory: Optional[Callable] = None):
        """Initialize session store.

        Args:
            db_session_factory: Optional factory function to create database sessions.
                               If provided, enables database persistence.
        """
        self._frameworks: Dict[str, FrameworkType] = {}
        self._workspaces: Dict[str, str] = {}
        self._locks: Dict[str, asyncio.Lock] = defaultdict(asyncio.Lock)
        self._global_lock = asyncio.Lock()  # For lock management
        self._db_session_factory = db_session_factory

    def set_db_session_factory(self, factory: Callable) -> None:
        """Set database session factory for persistence.

        Args:
            factory: Function that returns a database session context manager.
        """
        self._db_session_factory = factory
        logger.info("SessionStore: Database persistence enabled")

    def _persist_to_db(self, session_id: str, workspace: Optional[str] = None, framework: Optional[str] = None) -> None:
        """Persist session config to database (synchronous, called within async lock)."""
        if not self._db_session_factory:
            return

        try:
            # Import here to avoid circular imports
            from backend.app.db.repository import ConversationRepository

            with self._db_session_factory() as db:
                repo = ConversationRepository(db)
                repo.update_session_config(
                    session_id=session_id,
                    workspace_path=workspace,
                    framework=framework
                )
                logger.debug(f"Session {session_id}: persisted to database")
        except Exception as e:
            logger.warning(f"Failed to persist session {session_id} to database: {e}")

    def _load_from_db(self, session_id: str) -> Optional[Dict[str, str]]:
        """Load session config from database (synchronous)."""
        if not self._db_session_factory:
            return None

        try:
            from backend.app.db.repository import ConversationRepository

            with self._db_session_factory() as db:
                repo = ConversationRepository(db)
                config = repo.get_session_config(session_id)
                if config:
                    logger.debug(f"Session {session_id}: restored from database")
                return config
        except Exception as e:
            logger.warning(f"Failed to load session {session_id} from database: {e}")
            return None

    async def get_framework(self, session_id: str) -> FrameworkType:
        """
        Get framework for session.

        Args:
            session_id: Session identifier

        Returns:
            Framework type ("standard" or "deepagents")
        """
        async with self._locks[session_id]:
            # Check in-memory cache first
            if session_id in self._frameworks:
                return self._frameworks[session_id]

            # Try to restore from database
            config = self._load_from_db(session_id)
            if config and config.get("framework"):
                self._frameworks[session_id] = config["framework"]
                return config["framework"]

            return "standard"

    async def set_framework(
        self,
        session_id: str,
        framework: FrameworkType
    ) -> None:
        """
        Set framework for session.

        Args:
            session_id: Session identifier
            framework: Framework type to use

        Raises:
            ValueError: If framework is invalid
        """
        if framework not in ("standard", "deepagents"):
            raise ValueError(f"Invalid framework: {framework}")

        async with self._locks[session_id]:
            self._frameworks[session_id] = framework
            self._persist_to_db(session_id, framework=framework)
            logger.info(f"Session {session_id}: framework set to {framework}")

    async def get_workspace(
        self,
        session_id: str,
        default: str = None
    ) -> str:
        """
        Get workspace path for session.

        Args:
            session_id: Session identifier
            default: Default workspace if not set

        Returns:
            Workspace path
        """
        async with self._locks[session_id]:
            # Check in-memory cache first
            if session_id in self._workspaces:
                return self._workspaces[session_id]

            # Try to restore from database
            config = self._load_from_db(session_id)
            if config and config.get("workspace_path"):
                self._workspaces[session_id] = config["workspace_path"]
                return config["workspace_path"]

            return default or settings.default_workspace

    async def set_workspace(self, session_id: str, workspace: str) -> None:
        """
        Set workspace path for session.

        Args:
            session_id: Session identifier
            workspace: Workspace path (should be validated before calling)
        """
        async with self._locks[session_id]:
            self._workspaces[session_id] = workspace
            self._persist_to_db(session_id, workspace=workspace)
            logger.info(f"Session {session_id}: workspace set to {workspace}")

    async def delete_session(self, session_id: str) -> None:
        """
        Delete all data for a session.

        Args:
            session_id: Session identifier
        """
        async with self._global_lock:
            # Remove session data from cache
            self._frameworks.pop(session_id, None)
            self._workspaces.pop(session_id, None)

            # Remove the lock itself
            if session_id in self._locks:
                del self._locks[session_id]

            logger.info(f"Session {session_id}: deleted from cache")

    async def get_session_info(self, session_id: str) -> Dict[str, any]:
        """
        Get all information for a session.

        Args:
            session_id: Session identifier

        Returns:
            Dictionary with session information
        """
        async with self._locks[session_id]:
            # Try to restore from database if not in cache
            config = None
            if session_id not in self._frameworks and session_id not in self._workspaces:
                config = self._load_from_db(session_id)
                if config:
                    if config.get("framework"):
                        self._frameworks[session_id] = config["framework"]
                    if config.get("workspace_path"):
                        self._workspaces[session_id] = config["workspace_path"]

            return {
                "session_id": session_id,
                "framework": self._frameworks.get(session_id, "standard"),
                "workspace": self._workspaces.get(session_id, settings.default_workspace),
                "exists": session_id in self._frameworks or session_id in self._workspaces,
                "persisted": config is not None
            }

    async def list_sessions(self) -> list[str]:
        """
        List all active session IDs (from in-memory cache).

        Returns:
            List of session IDs
        """
        async with self._global_lock:
            # Combine keys from both dicts
            return list(set(self._frameworks.keys()) | set(self._workspaces.keys()))

    def __len__(self) -> int:
        """Return number of active sessions in cache."""
        return len(set(self._frameworks.keys()) | set(self._workspaces.keys()))


# Global singleton instance
_session_store: Optional[SessionStore] = None


def get_session_store() -> SessionStore:
    """
    Get global SessionStore instance (singleton pattern).

    Returns:
        SessionStore instance
    """
    global _session_store
    if _session_store is None:
        _session_store = SessionStore()
    return _session_store


def init_session_store_with_db(db_session_factory: Callable) -> SessionStore:
    """
    Initialize SessionStore with database persistence.

    Call this during application startup to enable session persistence.

    Args:
        db_session_factory: Factory function that returns database session context manager.

    Returns:
        Configured SessionStore instance
    """
    store = get_session_store()
    store.set_db_session_factory(db_session_factory)
    return store

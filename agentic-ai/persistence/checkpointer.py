"""Checkpointer Module for Agentic 2.0

LangGraph Checkpointer integration:
- SQLite checkpointer (default)
- PostgreSQL checkpointer (optional)
- Checkpoint management
- State persistence
"""

import logging
from typing import Optional, Dict, Any
from pathlib import Path

from langgraph.checkpoint.sqlite.aio import AsyncSqliteSaver

# PostgreSQL support is optional
try:
    from langgraph.checkpoint.postgres.aio import AsyncPostgresSaver
    HAS_POSTGRES = True
except ImportError:
    AsyncPostgresSaver = None
    HAS_POSTGRES = False

logger = logging.getLogger(__name__)


class CheckpointerManager:
    """Manages LangGraph checkpointers

    Features:
    - SQLite or PostgreSQL backend
    - Automatic initialization
    - Connection management
    - Checkpoint cleanup

    Example:
        >>> manager = CheckpointerManager(db_path="./checkpoints.db")
        >>> checkpointer = await manager.get_checkpointer()
        >>> # Use with LangGraph
        >>> graph = workflow.compile(checkpointer=checkpointer)
    """

    def __init__(
        self,
        db_path: str = "./data/checkpoints.db",
        db_type: str = "sqlite",
        postgres_uri: Optional[str] = None,
    ):
        """Initialize checkpointer manager

        Args:
            db_path: Path to SQLite database (default: ./data/checkpoints.db)
            db_type: Database type: "sqlite" or "postgres" (default: sqlite)
            postgres_uri: PostgreSQL connection URI (required if db_type="postgres")
        """
        self.db_path = db_path
        self.db_type = db_type
        self.postgres_uri = postgres_uri
        self._checkpointer: Optional[Any] = None

        logger.info(f"💾 CheckpointerManager initialized: {db_type} at {db_path if db_type == 'sqlite' else 'postgres'}")

    async def get_checkpointer(self) -> Any:
        """Get or create checkpointer instance

        Returns:
            LangGraph checkpointer (AsyncSqliteSaver or AsyncPostgresSaver)
        """
        if self._checkpointer is not None:
            return self._checkpointer

        if self.db_type == "sqlite":
            self._checkpointer = await self._create_sqlite_checkpointer()
        elif self.db_type == "postgres":
            self._checkpointer = await self._create_postgres_checkpointer()
        else:
            raise ValueError(f"Unknown db_type: {self.db_type}")

        logger.info(f"✅ Checkpointer created: {self.db_type}")
        return self._checkpointer

    async def _create_sqlite_checkpointer(self) -> AsyncSqliteSaver:
        """Create SQLite checkpointer"""
        # Ensure directory exists
        db_path = Path(self.db_path)
        db_path.parent.mkdir(parents=True, exist_ok=True)

        # Create checkpointer using async context manager
        async with AsyncSqliteSaver.from_conn_string(str(db_path)) as checkpointer:
            # Setup is called automatically
            pass

        # For persistence, we need to create a new instance that will be kept alive
        # The context manager pattern in LangGraph is for cleanup, but for long-running use
        # we can use a simpler approach
        checkpointer = AsyncSqliteSaver.from_conn_string(str(db_path))

        logger.info(f"💾 SQLite checkpointer created: {self.db_path}")
        return checkpointer

    async def _create_postgres_checkpointer(self) -> AsyncPostgresSaver:
        """Create PostgreSQL checkpointer"""
        if not HAS_POSTGRES:
            raise ImportError(
                "PostgreSQL support not available. "
                "Install with: pip install langgraph-checkpoint-postgres"
            )

        if not self.postgres_uri:
            raise ValueError("postgres_uri is required for PostgreSQL checkpointer")

        # Create checkpointer using async context manager
        async with AsyncPostgresSaver.from_conn_string(self.postgres_uri) as checkpointer:
            # Setup is called automatically
            pass

        # For persistence, create a new instance
        checkpointer = AsyncPostgresSaver.from_conn_string(self.postgres_uri)

        logger.info(f"💾 PostgreSQL checkpointer created")
        return checkpointer

    async def cleanup_old_checkpoints(self, max_age_days: int = 7):
        """Clean up old checkpoints

        Args:
            max_age_days: Maximum age of checkpoints to keep (default: 7 days)
        """
        # This is a placeholder - LangGraph doesn't provide built-in cleanup yet
        # In production, you'd implement custom SQL to delete old checkpoints
        logger.info(f"🧹 Checkpoint cleanup: max_age={max_age_days} days")
        # TODO: Implement cleanup logic

    async def close(self):
        """Close checkpointer connections"""
        if self._checkpointer:
            # LangGraph checkpointers auto-close connections
            self._checkpointer = None
            logger.info("💾 Checkpointer closed")

    def get_stats(self) -> Dict[str, Any]:
        """Get checkpointer statistics"""
        return {
            "db_type": self.db_type,
            "db_path": self.db_path if self.db_type == "sqlite" else None,
            "initialized": self._checkpointer is not None,
        }


# Factory functions for convenience

async def create_sqlite_checkpointer(
    db_path: str = "./data/checkpoints.db"
) -> AsyncSqliteSaver:
    """Create SQLite checkpointer (convenience function)

    Args:
        db_path: Path to SQLite database

    Returns:
        AsyncSqliteSaver instance
    """
    manager = CheckpointerManager(db_path=db_path, db_type="sqlite")
    return await manager.get_checkpointer()


async def create_postgres_checkpointer(
    postgres_uri: str
) -> AsyncPostgresSaver:
    """Create PostgreSQL checkpointer (convenience function)

    Args:
        postgres_uri: PostgreSQL connection URI

    Returns:
        AsyncPostgresSaver instance
    """
    manager = CheckpointerManager(
        db_type="postgres",
        postgres_uri=postgres_uri
    )
    return await manager.get_checkpointer()

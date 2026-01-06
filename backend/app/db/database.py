"""Database configuration and session management."""
import os
from sqlalchemy import create_engine, event, text
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

# Database path - store in data directory
DATA_DIR = os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(__file__))), "data")
os.makedirs(DATA_DIR, exist_ok=True)

DATABASE_URL = f"sqlite:///{os.path.join(DATA_DIR, 'conversations.db')}"

# Create engine with optimized pooling settings for SQLite
engine = create_engine(
    DATABASE_URL,
    connect_args={
        "check_same_thread": False,  # Required for SQLite with async
        "timeout": 30  # Wait up to 30 seconds for lock
    },
    poolclass=StaticPool,  # StaticPool for SQLite - maintains single connection
    pool_pre_ping=True,  # Verify connections before using
    echo=False  # Set to True for SQL debugging
)

# Enable Write-Ahead Logging for better concurrent performance
@event.listens_for(engine, "connect")
def set_sqlite_pragma(dbapi_conn, connection_record):
    """Set SQLite pragmas for better performance and concurrency."""
    cursor = dbapi_conn.cursor()
    # Enable WAL mode for better concurrent read/write performance
    cursor.execute("PRAGMA journal_mode=WAL")
    # Increase cache size to 10MB (default is usually 2MB)
    cursor.execute("PRAGMA cache_size=-10000")
    # Enable foreign key constraints
    cursor.execute("PRAGMA foreign_keys=ON")
    cursor.close()

SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

Base = declarative_base()


def get_db():
    """Get database session (generator for FastAPI dependency injection)."""
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


from contextlib import contextmanager

@contextmanager
def get_db_context():
    """Get database session as a context manager.

    Use this for non-FastAPI code that needs database access.
    Example:
        with get_db_context() as db:
            repo = ConversationRepository(db)
            ...
    """
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


def _run_migrations():
    """Run database migrations for schema changes.

    SQLite doesn't support ALTER TABLE ADD COLUMN IF NOT EXISTS,
    so we check and add missing columns manually.
    """
    import logging
    logger = logging.getLogger(__name__)

    with engine.connect() as conn:
        # Check if conversations table exists
        result = conn.execute(
            text("SELECT name FROM sqlite_master WHERE type='table' AND name='conversations'")
        )
        if not result.fetchone():
            return  # Table doesn't exist yet, will be created by create_all

        # Get existing columns
        result = conn.execute(text("PRAGMA table_info(conversations)"))
        existing_columns = {row[1] for row in result.fetchall()}

        # Add missing columns
        migrations = [
            ("workspace_path", "VARCHAR(500)"),
            ("framework", "VARCHAR(20) DEFAULT 'standard'"),
        ]

        for column_name, column_type in migrations:
            if column_name not in existing_columns:
                try:
                    conn.execute(text(f"ALTER TABLE conversations ADD COLUMN {column_name} {column_type}"))
                    conn.commit()
                    logger.info(f"Migration: Added column '{column_name}' to conversations table")
                except Exception as e:
                    logger.warning(f"Migration: Could not add column '{column_name}': {e}")


def init_db():
    """Initialize database tables and run migrations."""
    from . import models  # Import models to register them

    # Run migrations first (for existing databases)
    _run_migrations()

    # Create all tables (for new databases)
    Base.metadata.create_all(bind=engine)

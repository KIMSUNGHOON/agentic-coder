"""
Database Migration Script - Add task_type Column

This script adds the task_type column to the conversations table.
Supports mode separation between general questions and code generation.

Usage:
    python -m app.db.migrations.add_task_type
"""

import sys
from pathlib import Path

# Add parent directory to path
sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from sqlalchemy import text, inspect
from app.db.database import engine


def column_exists(inspector, table_name: str, column_name: str) -> bool:
    """Check if a column exists on a table."""
    columns = inspector.get_columns(table_name)
    return any(col['name'] == column_name for col in columns)


def add_task_type_column():
    """Add task_type column to conversations table."""
    print("=" * 60)
    print("DATABASE MIGRATION: Add task_type Column")
    print("=" * 60)

    inspector = inspect(engine)

    with engine.connect() as conn:
        # Check if column already exists
        if column_exists(inspector, "conversations", "task_type"):
            print("  task_type column already exists, skipping")
            return

        # Add task_type column with default value 'auto'
        try:
            conn.execute(text(
                "ALTER TABLE conversations ADD COLUMN task_type VARCHAR(30) DEFAULT 'auto'"
            ))
            conn.commit()
            print("  Added task_type column to conversations table")
        except Exception as e:
            print(f"  Failed to add task_type column: {e}")
            return

    print("\n" + "=" * 60)
    print("MIGRATION COMPLETE")
    print("=" * 60)


def verify_migration():
    """Verify the migration was successful."""
    print("\nVerifying migration...")

    inspector = inspect(engine)

    if column_exists(inspector, "conversations", "task_type"):
        print("  task_type column exists")
        return True
    else:
        print("  task_type column MISSING!")
        return False


if __name__ == "__main__":
    add_task_type_column()
    verify_migration()

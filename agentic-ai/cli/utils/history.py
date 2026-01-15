"""Command History Manager

Manages command history with local-only storage.
"""

import json
from pathlib import Path
from datetime import datetime
from typing import List, Optional


class CommandHistory:
    """Command history manager

    Features:
    - Persistent history (local file only)
    - Search and filter
    - Maximum size limit
    - Timestamp tracking
    """

    def __init__(
        self,
        history_file: str = "./data/cli_history.jsonl",
        max_entries: int = 1000
    ):
        """Initialize command history

        Args:
            history_file: Path to history file (local only)
            max_entries: Maximum history entries
        """
        self.history_file = Path(history_file)
        self.max_entries = max_entries
        self.commands: List[dict] = []

    def add(self, command: str) -> None:
        """Add command to history

        Args:
            command: Command string
        """
        entry = {
            "command": command,
            "timestamp": datetime.now().isoformat(),
        }

        self.commands.append(entry)

        # Trim if exceeds max
        if len(self.commands) > self.max_entries:
            self.commands = self.commands[-self.max_entries:]

        # Auto-save (local only)
        self.save()

    def get_recent(self, n: int = 10) -> List[str]:
        """Get recent commands

        Args:
            n: Number of recent commands

        Returns:
            List of recent commands
        """
        return [
            entry["command"]
            for entry in self.commands[-n:]
        ]

    def search(self, query: str) -> List[str]:
        """Search history

        Args:
            query: Search query

        Returns:
            Matching commands
        """
        return [
            entry["command"]
            for entry in self.commands
            if query.lower() in entry["command"].lower()
        ]

    def clear(self) -> None:
        """Clear history"""
        self.commands = []
        self.save()

    def load(self) -> None:
        """Load history from file (local only)"""
        try:
            self.history_file.parent.mkdir(parents=True, exist_ok=True)

            if self.history_file.exists():
                with open(self.history_file, "r") as f:
                    self.commands = [
                        json.loads(line)
                        for line in f
                        if line.strip()
                    ]

                # Trim if exceeds max
                if len(self.commands) > self.max_entries:
                    self.commands = self.commands[-self.max_entries:]

        except Exception as e:
            # If loading fails, start fresh
            print(f"Warning: Could not load history: {e}")
            self.commands = []

    def save(self) -> None:
        """Save history to file (local only)"""
        try:
            self.history_file.parent.mkdir(parents=True, exist_ok=True)

            with open(self.history_file, "w") as f:
                for entry in self.commands:
                    f.write(json.dumps(entry) + "\n")

        except Exception as e:
            print(f"Warning: Could not save history: {e}")

    def get_stats(self) -> dict:
        """Get history statistics

        Returns:
            Dictionary with stats
        """
        if not self.commands:
            return {
                "total": 0,
                "first": None,
                "last": None,
            }

        return {
            "total": len(self.commands),
            "first": self.commands[0]["timestamp"],
            "last": self.commands[-1]["timestamp"],
        }

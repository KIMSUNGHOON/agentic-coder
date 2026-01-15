"""Status Bar Component

Shows system status and health.
"""

from textual.widgets import Static
from rich.text import Text


class StatusBar(Static):
    """System status bar

    Shows:
    - Current status (Ready, Processing, Error)
    - System health (Healthy, Degraded, Unhealthy)
    - Session info
    - Local-only indicator
    """

    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self.status = "Initializing"
        self.health = "unknown"
        self.session_id = None
        self.update_display()

    def update_display(self) -> None:
        """Update the status bar display"""
        text = Text()

        # Status indicator
        if self.status == "Ready":
            text.append("● ", style="bold green")
            text.append("Ready", style="green")
        elif self.status == "Processing...":
            text.append("● ", style="bold yellow")
            text.append("Processing", style="yellow")
        elif self.status == "Error":
            text.append("● ", style="bold red")
            text.append("Error", style="red")
        else:
            text.append("● ", style="bold white")
            text.append(self.status, style="white")

        text.append(" | ", style="dim")

        # Health indicator
        if self.health == "healthy":
            text.append("♥ ", style="green")
            text.append("Healthy", style="green")
        elif self.health == "degraded":
            text.append("! ", style="yellow")
            text.append("Degraded", style="yellow")
        elif self.health == "unhealthy":
            text.append("✗ ", style="red")
            text.append("Unhealthy", style="red")
        else:
            text.append("? ", style="dim")
            text.append("Unknown", style="dim")

        text.append(" | ", style="dim")

        # Session info
        if self.session_id:
            text.append(f"Session: {self.session_id[:8]}", style="cyan")
        else:
            text.append("No session", style="dim")

        text.append(" | ", style="dim")

        # Local-only indicator
        text.append("🔒 ", style="green")
        text.append("Local Only", style="green bold")

        self.update(text)

    def update_status(self, status: str, health: str = None) -> None:
        """Update status

        Args:
            status: New status
            health: New health status (optional)
        """
        self.status = status
        if health is not None:
            self.health = health
        self.update_display()

    def set_session(self, session_id: str) -> None:
        """Set session ID

        Args:
            session_id: Session identifier
        """
        self.session_id = session_id
        self.update_display()

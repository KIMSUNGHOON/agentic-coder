"""Progress Display Component

Shows real-time task progress.
"""

from textual.widgets import Static
from rich.progress import Progress, SpinnerColumn, TextColumn, BarColumn, TaskProgressColumn
from rich.panel import Panel
from rich.text import Text


class ProgressDisplay(Static):
    """Task progress display

    Shows:
    - Current task name
    - Progress bar
    - Status (running, completed, failed)
    """

    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self.progress = Progress(
            SpinnerColumn(),
            TextColumn("[bold blue]{task.description}"),
            BarColumn(),
            TaskProgressColumn(),
            expand=True
        )
        self.current_task = None
        self.update_display()

    def update_display(self) -> None:
        """Update the progress display"""
        self.update(Panel(
            self.progress,
            border_style="blue dim",
            padding=(0, 1)
        ))

    def start_task(self, description: str, total: float = 100.0) -> None:
        """Start a new task

        Args:
            description: Task description
            total: Total progress (default 100)
        """
        if self.current_task is not None:
            self.progress.remove_task(self.current_task)

        self.current_task = self.progress.add_task(
            description,
            total=total
        )
        self.update_display()

    def update_progress(self, advance: float = None, description: str = None) -> None:
        """Update task progress

        Args:
            advance: Amount to advance (optional)
            description: New description (optional)
        """
        if self.current_task is not None:
            if advance is not None:
                self.progress.update(
                    self.current_task,
                    advance=advance
                )
            if description is not None:
                self.progress.update(
                    self.current_task,
                    description=description
                )
            self.update_display()

    def complete_task(self, message: str = "Completed") -> None:
        """Mark task as completed

        Args:
            message: Completion message
        """
        if self.current_task is not None:
            self.progress.update(
                self.current_task,
                completed=100,
                description=f"✅ {message}"
            )
            self.update_display()

    def fail_task(self, message: str = "Failed") -> None:
        """Mark task as failed

        Args:
            message: Failure message
        """
        if self.current_task is not None:
            self.progress.update(
                self.current_task,
                description=f"❌ {message}"
            )
            self.update_display()

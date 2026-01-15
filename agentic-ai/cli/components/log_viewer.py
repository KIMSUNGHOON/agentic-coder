"""Log Viewer Component

Displays real-time system logs.
"""

from textual.widgets import RichLog
from rich.text import Text
from datetime import datetime


class LogViewer(RichLog):
    """Real-time log display

    Shows logs with:
    - Timestamps
    - Log levels (INFO, WARNING, ERROR)
    - Color coding
    - Auto-scroll
    """

    def __init__(self, **kwargs):
        super().__init__(
            highlight=True,
            markup=True,
            wrap=True,
            max_lines=1000,
            **kwargs
        )
        self.can_focus = False

    def add_log(self, level: str, message: str) -> None:
        """Add a log entry

        Args:
            level: Log level (debug, info, warning, error, critical)
            message: Log message
        """
        timestamp = datetime.now().strftime("%H:%M:%S.%f")[:-3]

        text = Text()
        text.append(f"[{timestamp}] ", style="dim")

        # Level with color
        level_upper = level.upper()
        if level == "debug":
            text.append(f"{level_upper:8}", style="cyan")
        elif level == "info":
            text.append(f"{level_upper:8}", style="green")
        elif level == "warning":
            text.append(f"{level_upper:8}", style="yellow")
        elif level == "error":
            text.append(f"{level_upper:8}", style="red bold")
        elif level == "critical":
            text.append(f"{level_upper:8}", style="red bold reverse")
        else:
            text.append(f"{level_upper:8}", style="white")

        text.append(" | ", style="dim")
        text.append(message, style="white")

        self.write(text)

    def add_llm_call(self, model: str, tokens: int, duration: float) -> None:
        """Log LLM call

        Args:
            model: Model name
            tokens: Token count
            duration: Call duration in seconds
        """
        message = f"LLM Call: {model} | {tokens} tokens | {duration:.2f}s"
        self.add_log("info", message)

    def add_tool_call(self, tool: str, status: str) -> None:
        """Log tool execution

        Args:
            tool: Tool name
            status: Execution status
        """
        message = f"Tool: {tool} | Status: {status}"
        level = "info" if status == "success" else "warning"
        self.add_log(level, message)

    def add_security_event(self, event: str) -> None:
        """Log security event

        Args:
            event: Security event description
        """
        self.add_log("warning", f"Security: {event}")

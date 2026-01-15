"""Chat Panel Component

Displays conversation between user and assistant.
"""

from textual.widgets import RichLog
from textual.reactive import reactive
from rich.text import Text
from rich.panel import Panel
from datetime import datetime


class ChatPanel(RichLog):
    """Chat conversation display

    Shows messages with:
    - User messages (right-aligned, blue)
    - Assistant messages (left-aligned, green)
    - System messages (center, yellow)
    - Timestamps
    """

    message_count = reactive(0)

    def __init__(self, **kwargs):
        super().__init__(
            highlight=True,
            markup=True,
            wrap=True,
            **kwargs
        )
        self.can_focus = False

    def add_message(self, role: str, content: str) -> None:
        """Add a message to the chat

        Args:
            role: Message role (user, assistant, system)
            content: Message content
        """
        timestamp = datetime.now().strftime("%H:%M:%S")

        if role == "user":
            # User message (blue)
            text = Text()
            text.append(f"[{timestamp}] ", style="dim")
            text.append("You", style="bold blue")
            text.append(": ", style="dim")
            text.append(content, style="white")

            self.write(Panel(
                text,
                border_style="blue",
                padding=(0, 1)
            ))

        elif role == "assistant":
            # Assistant message (green)
            text = Text()
            text.append(f"[{timestamp}] ", style="dim")
            text.append("Assistant", style="bold green")
            text.append(": ", style="dim")
            text.append(content, style="white")

            self.write(Panel(
                text,
                border_style="green",
                padding=(0, 1)
            ))

        elif role == "system":
            # System message (yellow)
            text = Text()
            text.append(f"[{timestamp}] ", style="dim")
            text.append("System", style="bold yellow")
            text.append(": ", style="dim")
            text.append(content, style="yellow")

            self.write(Panel(
                text,
                border_style="yellow",
                padding=(0, 1)
            ))

        self.message_count += 1

    def add_thinking(self, thinking: str) -> None:
        """Add Chain-of-Thought thinking block

        Args:
            thinking: Thinking content from <think> tags
        """
        timestamp = datetime.now().strftime("%H:%M:%S")

        text = Text()
        text.append(f"[{timestamp}] ", style="dim")
        text.append("🤔 Thinking", style="bold magenta")
        text.append(":\n", style="dim")
        text.append(thinking, style="italic dim")

        self.write(Panel(
            text,
            border_style="magenta dim",
            padding=(0, 1),
            title="Chain of Thought"
        ))

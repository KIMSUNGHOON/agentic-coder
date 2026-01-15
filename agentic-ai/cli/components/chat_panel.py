"""Chat Panel Component

Displays conversation between user and assistant.
"""

from textual.widgets import RichLog
from textual.reactive import reactive
from rich.text import Text
from rich.panel import Panel
from rich.markdown import Markdown
from rich.syntax import Syntax
from datetime import datetime
import re
import time


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
        self._streaming_messages = {}  # {message_id: {content, role, start_time}}

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

    def add_status(self, message: str) -> None:
        """Add temporary status message (dim, small)

        Args:
            message: Status message (e.g., "Processing...", "Executing: READ_FILE")
        """
        timestamp = datetime.now().strftime("%H:%M:%S")

        text = Text()
        text.append(f"[{timestamp}] ", style="dim")
        text.append("● ", style="yellow dim")
        text.append(message, style="dim italic")

        self.write(text)

    def add_message_smart(self, role: str, content: str) -> None:
        """Add message with automatic format detection

        Detects markdown, code blocks, and applies appropriate formatting.

        Args:
            role: Message role (user, assistant, system)
            content: Message content
        """
        timestamp = datetime.now().strftime("%H:%M:%S")

        # Detect format
        format_type, language = self._detect_format(content)

        if role == "user":
            # User message (always simple text)
            text = Text()
            text.append(f"[{timestamp}] ", style="dim")
            text.append("You", style="bold blue")
            text.append(": ", style="dim")
            text.append(content, style="white")

            self.write(Panel(text, border_style="blue", padding=(0, 1)))

        elif role == "assistant":
            # Assistant message with smart formatting
            if format_type == "code" and language:
                # Code block with syntax highlighting
                self._write_code_message(timestamp, content, language)
            elif format_type == "markdown":
                # Markdown content
                self._write_markdown_message(timestamp, content)
            else:
                # Plain text
                text = Text()
                text.append(f"[{timestamp}] ", style="dim")
                text.append("Assistant", style="bold green")
                text.append(": ", style="dim")
                text.append(content, style="white")

                self.write(Panel(text, border_style="green", padding=(0, 1)))

        elif role == "system":
            # System message
            text = Text()
            text.append(f"[{timestamp}] ", style="dim")
            text.append("System", style="bold yellow")
            text.append(": ", style="dim")
            text.append(content, style="yellow")

            self.write(Panel(text, border_style="yellow", padding=(0, 1)))

        self.message_count += 1

    def _detect_format(self, content: str) -> tuple:
        """Detect content format

        Returns:
            (format, language): format is "text", "markdown", or "code"
                               language is detected programming language or None
        """
        # Check for code blocks
        code_match = re.search(r"```(\w+)?\n(.*?)```", content, re.DOTALL)
        if code_match:
            language = code_match.group(1) or "text"
            return ("code", language)

        # Check for markdown indicators
        markdown_patterns = [
            r"^#{1,6}\s",  # Headers
            r"^\*\s",      # Unordered list
            r"^-\s",       # Unordered list
            r"^\d+\.\s",   # Ordered list
            r"\[.*?\]\(.*?\)",  # Links
            r"\*\*.*?\*\*",     # Bold
            r"\*.*?\*",         # Italic
        ]
        for pattern in markdown_patterns:
            if re.search(pattern, content, re.MULTILINE):
                return ("markdown", None)

        return ("text", None)

    def _write_markdown_message(self, timestamp: str, content: str) -> None:
        """Write message with Markdown formatting"""
        md = Markdown(content)

        self.write(Panel(
            md,
            border_style="green",
            padding=(0, 1),
            title=f"Assistant [{timestamp}]",
            title_align="left"
        ))

    def _write_code_message(self, timestamp: str, content: str, language: str) -> None:
        """Write message with code syntax highlighting"""
        # Extract code from ```language ... ``` blocks
        code_match = re.search(r"```\w+\n(.*?)```", content, re.DOTALL)
        if code_match:
            code = code_match.group(1).strip()
        else:
            code = content

        syntax = Syntax(code, language, theme="monokai", line_numbers=False)

        self.write(Panel(
            syntax,
            border_style="blue",
            padding=(0, 1),
            title=f"{language.upper()} Code [{timestamp}]",
            title_align="left"
        ))

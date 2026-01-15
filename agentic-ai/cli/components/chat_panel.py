"""Chat Panel Component

Displays conversation between user and assistant.
"""

from textual.widgets import RichLog
from textual.reactive import reactive
from rich.text import Text
from rich.panel import Panel
from rich.markdown import Markdown
from rich.syntax import Syntax
from rich.table import Table
from datetime import datetime
from typing import Literal, Optional
import re
import time
import difflib


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

    def add_file_content(
        self,
        file_path: str,
        content: str,
        status: Literal["NEW", "MODIFIED", "DELETED"],
        display_mode: Literal["full", "preview", "hidden"] = "full",
        language: Optional[str] = None,
    ) -> None:
        """Display file content with line numbers and syntax highlighting

        Args:
            file_path: Path to the file
            content: File content to display
            status: File status (NEW/MODIFIED/DELETED)
            display_mode: How to display the file (full/preview/hidden)
            language: Programming language for syntax highlighting (auto-detect if None)
        """
        if display_mode == "hidden":
            return

        # Auto-detect language from file extension
        if language is None:
            ext = file_path.split('.')[-1].lower()
            language_map = {
                'py': 'python',
                'js': 'javascript',
                'ts': 'typescript',
                'tsx': 'tsx',
                'jsx': 'jsx',
                'java': 'java',
                'go': 'go',
                'rs': 'rust',
                'cpp': 'cpp',
                'c': 'c',
                'h': 'c',
                'hpp': 'cpp',
                'sh': 'bash',
                'bash': 'bash',
                'json': 'json',
                'yaml': 'yaml',
                'yml': 'yaml',
                'xml': 'xml',
                'html': 'html',
                'css': 'css',
                'md': 'markdown',
            }
            language = language_map.get(ext, 'text')

        # Status icon and color
        status_icons = {
            "NEW": "✨",
            "MODIFIED": "📝",
            "DELETED": "🗑️",
        }
        status_colors = {
            "NEW": "green",
            "MODIFIED": "yellow",
            "DELETED": "red",
        }
        status_icon = status_icons.get(status, "📄")
        border_color = status_colors.get(status, "white")

        # File size
        file_size = len(content.encode('utf-8'))
        if file_size < 1024:
            size_str = f"{file_size}B"
        elif file_size < 1024 * 1024:
            size_str = f"{file_size / 1024:.1f}KB"
        else:
            size_str = f"{file_size / (1024 * 1024):.1f}MB"

        # Display mode
        if display_mode == "preview":
            # Show only first 10 lines
            lines = content.split('\n')
            if len(lines) > 10:
                content = '\n'.join(lines[:10]) + f'\n\n... ({len(lines) - 10} more lines)'

        # Create syntax highlighted content with line numbers
        syntax = Syntax(
            content,
            language,
            theme="monokai",
            line_numbers=True,
            word_wrap=False,
            indent_guides=False,
        )

        # Create panel with file info
        title = f"{status_icon} {file_path} ({status}) - {size_str}"

        self.write(Panel(
            syntax,
            title=title,
            title_align="left",
            border_style=border_color,
            padding=(0, 1),
        ))

    def add_file_diff(
        self,
        file_path: str,
        old_content: str,
        new_content: str,
        context_lines: int = 3,
    ) -> None:
        """Display unified diff for file changes

        Args:
            file_path: Path to the file
            old_content: Original file content
            new_content: Modified file content
            context_lines: Number of context lines to show around changes
        """
        # Split into lines
        old_lines = old_content.splitlines(keepends=True)
        new_lines = new_content.splitlines(keepends=True)

        # Generate unified diff
        diff = difflib.unified_diff(
            old_lines,
            new_lines,
            fromfile=f"a/{file_path}",
            tofile=f"b/{file_path}",
            n=context_lines,
        )

        # Format diff with colors
        diff_text = Text()
        for line in diff:
            line = line.rstrip('\n')
            if line.startswith('+++') or line.startswith('---'):
                # File headers
                diff_text.append(line + '\n', style="bold white")
            elif line.startswith('@@'):
                # Hunk header
                diff_text.append(line + '\n', style="cyan")
            elif line.startswith('+'):
                # Added line
                diff_text.append(line + '\n', style="green")
            elif line.startswith('-'):
                # Removed line
                diff_text.append(line + '\n', style="red")
            else:
                # Context line
                diff_text.append(line + '\n', style="dim")

        # Create panel
        self.write(Panel(
            diff_text,
            title=f"📝 Changes: {file_path}",
            title_align="left",
            border_style="yellow",
            padding=(0, 1),
        ))

    def add_step_header(
        self,
        step_num: int,
        total_steps: int,
        description: str,
        status: Literal["pending", "in_progress", "completed", "failed"] = "in_progress",
    ) -> None:
        """Display step progress header

        Args:
            step_num: Current step number (1-indexed)
            total_steps: Total number of steps
            description: Step description
            status: Step status
        """
        # Status icons
        status_icons = {
            "pending": "⏳",
            "in_progress": "⚙️",
            "completed": "✅",
            "failed": "❌",
        }
        status_colors = {
            "pending": "dim",
            "in_progress": "yellow",
            "completed": "green",
            "failed": "red",
        }

        icon = status_icons.get(status, "●")
        color = status_colors.get(status, "white")

        # Progress bar
        progress_filled = step_num
        progress_total = total_steps
        progress_bar = "█" * progress_filled + "░" * (progress_total - progress_filled)

        # Create header
        text = Text()
        text.append(f"{icon} Step {step_num}/{total_steps}: ", style=f"bold {color}")
        text.append(description, style="white")
        text.append(f"\n{progress_bar} ", style="dim")
        text.append(f"{int(progress_filled/progress_total*100)}%", style="dim")

        self.write(Panel(
            text,
            border_style=color,
            padding=(0, 1),
        ))

    def add_plan_summary(
        self,
        plan: dict,
        task_complexity: str = "medium",
    ) -> None:
        """Display plan summary box

        Args:
            plan: Plan dictionary with steps
            task_complexity: Task complexity level
        """
        text = Text()
        text.append("🎯 Plan\n\n", style="bold cyan")

        # Add complexity
        complexity_colors = {
            "trivial": "green",
            "simple": "green",
            "medium": "yellow",
            "complex": "yellow",
            "very_complex": "red",
        }
        complexity_color = complexity_colors.get(task_complexity, "white")
        text.append(f"Complexity: ", style="dim")
        text.append(f"{task_complexity.upper()}\n\n", style=f"bold {complexity_color}")

        # Add steps
        steps = plan.get("steps", [])
        for i, step in enumerate(steps, 1):
            text.append(f"{i}. ", style="bold white")
            text.append(f"{step}\n", style="white")

        self.write(Panel(
            text,
            title="📋 Execution Plan",
            title_align="left",
            border_style="cyan",
            padding=(1, 2),
        ))

    def add_task_summary(
        self,
        duration: float,
        files_created: list,
        files_modified: list,
        files_deleted: list,
        tool_calls: int,
        iterations: int,
    ) -> None:
        """Display task completion summary box

        Args:
            duration: Task duration in seconds
            files_created: List of created file paths
            files_modified: List of modified file paths
            files_deleted: List of deleted file paths
            tool_calls: Number of tool calls executed
            iterations: Number of iterations used
        """
        text = Text()
        text.append("✅ Task Completed\n\n", style="bold green")

        # Duration
        if duration < 60:
            duration_str = f"{duration:.1f}s"
        else:
            duration_str = f"{duration / 60:.1f}m"
        text.append(f"⏱️  Duration: {duration_str}\n", style="white")
        text.append(f"🔄 Iterations: {iterations}\n", style="white")
        text.append(f"🔧 Tool calls: {tool_calls}\n\n", style="white")

        # Files
        if files_created:
            text.append(f"✨ Created ({len(files_created)}):\n", style="bold green")
            for file in files_created[:5]:  # Show max 5
                text.append(f"  • {file}\n", style="green")
            if len(files_created) > 5:
                text.append(f"  ... and {len(files_created) - 5} more\n", style="dim")
            text.append("\n")

        if files_modified:
            text.append(f"📝 Modified ({len(files_modified)}):\n", style="bold yellow")
            for file in files_modified[:5]:
                text.append(f"  • {file}\n", style="yellow")
            if len(files_modified) > 5:
                text.append(f"  ... and {len(files_modified) - 5} more\n", style="dim")
            text.append("\n")

        if files_deleted:
            text.append(f"🗑️  Deleted ({len(files_deleted)}):\n", style="bold red")
            for file in files_deleted[:5]:
                text.append(f"  • {file}\n", style="red")
            if len(files_deleted) > 5:
                text.append(f"  ... and {len(files_deleted) - 5} more\n", style="dim")

        self.write(Panel(
            text,
            title="📊 Summary",
            title_align="left",
            border_style="green",
            padding=(1, 2),
        ))

    def add_confirmation_prompt(
        self,
        message: str,
        warning_level: Literal["info", "warning", "danger"] = "warning",
        default: bool = False,
    ) -> None:
        """Display confirmation prompt

        Args:
            message: Confirmation message
            warning_level: Warning level (info/warning/danger)
            default: Default value (True=Yes, False=No)
        """
        # Warning icons and colors
        warning_icons = {
            "info": "ℹ️",
            "warning": "⚠️",
            "danger": "🚨",
        }
        warning_colors = {
            "info": "blue",
            "warning": "yellow",
            "danger": "red",
        }

        icon = warning_icons.get(warning_level, "❓")
        color = warning_colors.get(warning_level, "white")

        # Create prompt
        text = Text()
        text.append(f"{icon} ", style=f"bold {color}")
        text.append(message, style="white")
        text.append("\n\n")

        # Add default hint
        if default:
            text.append("Continue? [Y/n]: ", style="bold white")
        else:
            text.append("Continue? [y/N]: ", style="bold white")

        self.write(Panel(
            text,
            border_style=color,
            padding=(0, 1),
        ))

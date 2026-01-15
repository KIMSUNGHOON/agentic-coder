"""Rich Formatting Utilities

Helper functions for formatting terminal output.
"""

from rich.text import Text
from rich.panel import Panel
from rich.table import Table
from rich.console import Console


console = Console()


def format_message(role: str, content: str) -> Text:
    """Format a chat message

    Args:
        role: Message role (user, assistant, system)
        content: Message content

    Returns:
        Formatted Rich Text
    """
    text = Text()

    if role == "user":
        text.append("You: ", style="bold blue")
        text.append(content, style="white")
    elif role == "assistant":
        text.append("Assistant: ", style="bold green")
        text.append(content, style="white")
    elif role == "system":
        text.append("System: ", style="bold yellow")
        text.append(content, style="yellow")

    return text


def format_error(message: str) -> Panel:
    """Format an error message

    Args:
        message: Error message

    Returns:
        Formatted Rich Panel
    """
    text = Text()
    text.append("❌ Error\n\n", style="bold red")
    text.append(message, style="white")

    return Panel(
        text,
        border_style="red",
        padding=(1, 2),
        title="Error"
    )


def format_success(message: str) -> Panel:
    """Format a success message

    Args:
        message: Success message

    Returns:
        Formatted Rich Panel
    """
    text = Text()
    text.append("✅ Success\n\n", style="bold green")
    text.append(message, style="white")

    return Panel(
        text,
        border_style="green",
        padding=(1, 2),
        title="Success"
    )


def format_warning(message: str) -> Panel:
    """Format a warning message

    Args:
        message: Warning message

    Returns:
        Formatted Rich Panel
    """
    text = Text()
    text.append("⚠️  Warning\n\n", style="bold yellow")
    text.append(message, style="white")

    return Panel(
        text,
        border_style="yellow",
        padding=(1, 2),
        title="Warning"
    )


def format_code(code: str, language: str = "python") -> Panel:
    """Format code block

    Args:
        code: Code content
        language: Programming language

    Returns:
        Formatted Rich Panel
    """
    return Panel(
        Text(code, style=f"bold {language}"),
        border_style="cyan",
        padding=(1, 2),
        title=f"Code ({language})"
    )


def format_table(data: list[dict], title: str = None) -> Table:
    """Format data as table

    Args:
        data: List of dictionaries with data
        title: Table title (optional)

    Returns:
        Formatted Rich Table
    """
    if not data:
        return Table(title=title or "Empty")

    # Get columns from first row
    columns = list(data[0].keys())

    table = Table(title=title, show_header=True, header_style="bold magenta")

    # Add columns
    for col in columns:
        table.add_column(col, style="cyan")

    # Add rows
    for row in data:
        table.add_row(*[str(row.get(col, "")) for col in columns])

    return table


def format_thinking(content: str) -> Panel:
    """Format Chain-of-Thought thinking

    Args:
        content: Thinking content

    Returns:
        Formatted Rich Panel
    """
    text = Text()
    text.append("🤔 Chain of Thought\n\n", style="bold magenta")
    text.append(content, style="italic dim white")

    return Panel(
        text,
        border_style="magenta dim",
        padding=(1, 2),
        title="CoT"
    )

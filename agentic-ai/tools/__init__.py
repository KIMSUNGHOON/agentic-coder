"""Tools Module for Agentic 2.0

Cross-platform tools with safety controls:
- Filesystem operations (read, write, list, search)
- Git operations (status, diff, log, commit)
- Process execution (shell commands, Python code)
- Content search (grep-like functionality)
"""

from .filesystem import FileSystemTools, ToolResult
from .git import GitTools
from .process import ProcessTools
from .search import SearchTools, SearchMatch

__all__ = [
    # Core classes
    "FileSystemTools",
    "GitTools",
    "ProcessTools",
    "SearchTools",
    # Data classes
    "ToolResult",
    "SearchMatch",
]

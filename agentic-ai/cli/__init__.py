"""Agentic 2.0 CLI Interface

Interactive command-line interface with:
- Textual TUI for rich interactions
- Real-time progress visualization
- Chain-of-Thought display
- Session management
- Security enforcement (local-only data)
- Backend integration with workflows
"""

__version__ = "1.0.0"

from .app import AgenticApp, run_cli
from .commands import cli
from .backend_bridge import BackendBridge, get_bridge

__all__ = ["AgenticApp", "run_cli", "cli", "BackendBridge", "get_bridge"]

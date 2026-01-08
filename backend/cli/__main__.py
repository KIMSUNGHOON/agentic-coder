"""Agentic Coder CLI - Command Line Interface

Interactive CLI for Agentic Coder that provides:
- Interactive REPL mode for conversational coding
- One-shot mode for single commands
- Session management and persistence
- Rich terminal UI with streaming progress

Usage:
    # Interactive mode
    python -m cli

    # One-shot mode
    python -m cli "Create a Python calculator"

    # With options
    python -m cli --workspace ./my-project --model deepseek-r1:14b

    # Resume session
    python -m cli --session-id session-20260108-123456
"""

import sys
import os
import argparse
from pathlib import Path
from typing import Optional

# Add backend to path if running as module
backend_dir = Path(__file__).parent.parent
if str(backend_dir) not in sys.path:
    sys.path.insert(0, str(backend_dir))

# Load .env file from project root (cross-platform compatible)
def load_dotenv_file():
    """Load .env file from project root directory."""
    # Find project root (backend's parent)
    project_root = backend_dir.parent
    env_file = project_root / ".env"

    if env_file.exists():
        try:
            # Try using python-dotenv if available
            from dotenv import load_dotenv
            load_dotenv(env_file)
            return True
        except ImportError:
            # Fallback: manually parse .env file
            try:
                with open(env_file, 'r', encoding='utf-8') as f:
                    for line in f:
                        line = line.strip()
                        # Skip empty lines and comments
                        if not line or line.startswith('#'):
                            continue
                        # Parse KEY=VALUE format
                        if '=' in line:
                            key, _, value = line.partition('=')
                            key = key.strip()
                            value = value.strip()
                            # Remove surrounding quotes if present
                            if value and value[0] in ('"', "'") and value[-1] == value[0]:
                                value = value[1:-1]
                            # Only set if not already in environment
                            if key and key not in os.environ:
                                os.environ[key] = value
                return True
            except Exception:
                return False
    return False

# Load environment variables before importing other modules
_env_loaded = load_dotenv_file()

from cli.terminal_ui import TerminalUI
from cli.session_manager import SessionManager


def parse_args():
    """Parse command line arguments"""
    parser = argparse.ArgumentParser(
        description="Agentic Coder - Interactive AI coding assistant",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  agentic-coder                           # Start interactive mode
  agentic-coder "Create a Python calculator"  # One-shot mode
  agentic-coder -w ./myproject            # Specify workspace
  agentic-coder -s session-123            # Resume session
  agentic-coder -m qwen2.5-coder:32b      # Use different model

Slash Commands (in interactive mode):
  /help       - Show available commands
  /status     - Show current session status
  /history    - Show conversation history
  /context    - Show current context information
  /files      - Show generated files
  /clear      - Clear terminal screen
  /exit       - Exit CLI (also Ctrl+D)
        """
    )

    parser.add_argument(
        "prompt",
        nargs="*",
        help="Optional prompt for one-shot mode. If not provided, starts interactive mode."
    )

    parser.add_argument(
        "-w", "--workspace",
        default=".",
        help="Workspace directory (default: current directory)"
    )

    parser.add_argument(
        "-s", "--session-id",
        help="Session ID to resume (default: create new session)"
    )

    parser.add_argument(
        "-m", "--model",
        default="deepseek-r1:14b",
        help="LLM model to use (default: deepseek-r1:14b)"
    )

    parser.add_argument(
        "--version",
        action="version",
        version="Agentic Coder CLI v1.0.0"
    )

    parser.add_argument(
        "--debug",
        action="store_true",
        help="Enable debug logging"
    )

    parser.add_argument(
        "--no-save",
        action="store_true",
        help="Don't save session history"
    )

    return parser.parse_args()


def main():
    """Main CLI entry point"""
    args = parse_args()

    # Setup logging if debug mode
    if args.debug:
        import logging
        logging.basicConfig(
            level=logging.DEBUG,
            format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
        )

    try:
        # Initialize session manager
        session_mgr = SessionManager(
            workspace=args.workspace,
            session_id=args.session_id,
            model=args.model,
            auto_save=not args.no_save
        )

        # Initialize terminal UI
        ui = TerminalUI(session_mgr)

        # Check if one-shot mode or interactive mode
        if args.prompt:
            # One-shot mode
            prompt_text = " ".join(args.prompt)
            ui.execute_one_shot(prompt_text)
        else:
            # Interactive REPL mode
            ui.start_interactive()

    except KeyboardInterrupt:
        print("\n\nExiting Agentic Coder CLI...")
        return 0
    except Exception as e:
        print(f"\n❌ Error: {e}")
        if args.debug:
            import traceback
            traceback.print_exc()
        return 1

    return 0


if __name__ == "__main__":
    sys.exit(main())

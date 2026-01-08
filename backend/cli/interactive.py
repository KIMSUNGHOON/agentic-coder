"""Enhanced Interactive Mode for TestCodeAgent CLI

Features:
- Command history with persistence
- Auto-completion for slash commands and file paths
- Multi-line input support
- Vi/Emacs key bindings
- Improved input handling with prompt_toolkit
"""

import os
from pathlib import Path
from typing import List, Optional, Callable

try:
    from prompt_toolkit import PromptSession
    from prompt_toolkit.history import FileHistory
    from prompt_toolkit.auto_suggest import AutoSuggestFromHistory
    from prompt_toolkit.completion import Completer, Completion, WordCompleter, PathCompleter, merge_completers
    from prompt_toolkit.styles import Style
    from prompt_toolkit.formatted_text import HTML
    from prompt_toolkit.key_binding import KeyBindings
    from prompt_toolkit.keys import Keys
    PROMPT_TOOLKIT_AVAILABLE = True
except ImportError:
    PROMPT_TOOLKIT_AVAILABLE = False


# Slash commands with descriptions for auto-completion
SLASH_COMMANDS = {
    "/help": "Show available commands",
    "/status": "Show current session status",
    "/history": "Show conversation history",
    "/context": "Show current context information",
    "/files": "Show generated files",
    "/preview": "Preview file with syntax highlighting (/preview <file>)",
    "/clear": "Clear terminal screen",
    "/exit": "Exit CLI",
    "/quit": "Exit CLI (alias for /exit)",
    "/sessions": "List all saved sessions",
    "/config": "Show or edit configuration",
    "/model": "Show or change current model",
    "/workspace": "Show or change workspace",
    "/undo": "Undo last operation (if possible)",
    "/redo": "Redo last undone operation (if possible)",
}


class SlashCommandCompleter(Completer):
    """Completer for slash commands"""

    def get_completions(self, document, complete_event):
        text = document.text_before_cursor.lstrip()

        # Only complete if text starts with /
        if not text.startswith('/'):
            return

        # Get the command part
        cmd_text = text.lower()

        for cmd, description in SLASH_COMMANDS.items():
            if cmd.startswith(cmd_text):
                yield Completion(
                    cmd,
                    start_position=-len(text),
                    display=cmd,
                    display_meta=description
                )


class FilePathCompleter(Completer):
    """Completer for file paths in commands like /preview"""

    def __init__(self, workspace: Path):
        self.workspace = workspace
        self._path_completer = PathCompleter(
            expanduser=True,
            only_directories=False
        )

    def get_completions(self, document, complete_event):
        text = document.text_before_cursor

        # Check if this is a command that takes file path
        file_commands = ["/preview ", "/open ", "/edit "]

        for cmd in file_commands:
            if text.startswith(cmd):
                # Get the path part after command
                path_part = text[len(cmd):]

                # Try to complete from workspace
                try:
                    search_path = self.workspace / path_part if path_part else self.workspace

                    # If partial path, get directory part
                    if path_part and not path_part.endswith('/'):
                        parent = (self.workspace / path_part).parent
                        if parent.exists():
                            search_path = parent

                    if search_path.is_dir():
                        prefix = path_part.rsplit('/', 1)[0] + '/' if '/' in path_part else ''

                        for item in search_path.iterdir():
                            name = item.name
                            full_match = prefix + name

                            # Check if matches what user typed
                            if full_match.startswith(path_part) or path_part == '':
                                is_dir = item.is_dir()
                                display_name = f"{name}/" if is_dir else name

                                yield Completion(
                                    full_match + ('/' if is_dir else ''),
                                    start_position=-len(path_part),
                                    display=display_name,
                                    display_meta="directory" if is_dir else self._get_file_type(name)
                                )
                except Exception:
                    pass

                return

    def _get_file_type(self, filename: str) -> str:
        """Get file type description from extension"""
        ext = Path(filename).suffix.lower()
        type_map = {
            '.py': 'Python',
            '.js': 'JavaScript',
            '.ts': 'TypeScript',
            '.tsx': 'React TSX',
            '.jsx': 'React JSX',
            '.json': 'JSON',
            '.yaml': 'YAML',
            '.yml': 'YAML',
            '.md': 'Markdown',
            '.txt': 'Text',
            '.html': 'HTML',
            '.css': 'CSS',
            '.sh': 'Shell',
        }
        return type_map.get(ext, 'File')


class CLICompleter(Completer):
    """Combined completer for CLI"""

    def __init__(self, workspace: Path):
        self.slash_completer = SlashCommandCompleter()
        self.file_completer = FilePathCompleter(workspace)

    def get_completions(self, document, complete_event):
        text = document.text_before_cursor.lstrip()

        if text.startswith('/'):
            # First check for slash commands
            for completion in self.slash_completer.get_completions(document, complete_event):
                yield completion

            # Then check for file completions
            for completion in self.file_completer.get_completions(document, complete_event):
                yield completion


def create_prompt_style() -> Style:
    """Create custom prompt style"""
    return Style.from_dict({
        # User input styling
        '': '#ffffff',  # Default text

        # Prompt styling
        'prompt': '#00ffff bold',  # Cyan bold for "You"
        'prompt.bracket': '#888888',  # Gray brackets

        # Completion styling
        'completion-menu': 'bg:#333333 #ffffff',
        'completion-menu.completion': 'bg:#333333 #ffffff',
        'completion-menu.completion.current': 'bg:#00ffff #000000',
        'completion-menu.meta': 'bg:#333333 #888888 italic',
        'completion-menu.meta.current': 'bg:#00ffff #333333 italic',

        # Scrollbar
        'scrollbar.background': 'bg:#444444',
        'scrollbar.button': 'bg:#888888',
    })


def create_key_bindings() -> KeyBindings:
    """Create custom key bindings"""
    bindings = KeyBindings()

    @bindings.add(Keys.ControlD)
    def _(event):
        """Handle Ctrl+D to exit"""
        event.app.exit(result=None)

    @bindings.add(Keys.ControlC)
    def _(event):
        """Handle Ctrl+C to cancel current input"""
        event.app.current_buffer.reset()

    @bindings.add(Keys.ControlL)
    def _(event):
        """Handle Ctrl+L to clear screen"""
        event.app.renderer.clear()

    return bindings


class InteractiveSession:
    """Enhanced interactive session with history and completion"""

    def __init__(
        self,
        workspace: Path,
        history_file: Optional[Path] = None,
        enable_history: bool = True,
        enable_completion: bool = True
    ):
        """Initialize interactive session

        Args:
            workspace: Workspace directory
            history_file: Path to history file
            enable_history: Enable command history
            enable_completion: Enable auto-completion
        """
        self.workspace = workspace
        self.enable_history = enable_history
        self.enable_completion = enable_completion

        # Setup history
        self.history_file = history_file or (Path.home() / ".testcodeagent" / "history")
        self.history_file.parent.mkdir(parents=True, exist_ok=True)

        # Check if prompt_toolkit is available
        if not PROMPT_TOOLKIT_AVAILABLE:
            self._session = None
            return

        # Setup prompt session
        history = FileHistory(str(self.history_file)) if enable_history else None
        completer = CLICompleter(workspace) if enable_completion else None

        self._session = PromptSession(
            history=history,
            auto_suggest=AutoSuggestFromHistory() if enable_history else None,
            completer=completer,
            style=create_prompt_style(),
            key_bindings=create_key_bindings(),
            enable_history_search=True,
            complete_while_typing=True,
            complete_in_thread=True,
        )

    def prompt(self, message: str = "You") -> Optional[str]:
        """Get user input with enhanced features

        Args:
            message: Prompt message

        Returns:
            User input or None if cancelled
        """
        if self._session is None:
            # Fallback to basic input
            try:
                return input(f"\n{message}: ")
            except EOFError:
                return None
            except KeyboardInterrupt:
                return ""

        try:
            formatted_prompt = HTML(f'\n<prompt>{message}</prompt><prompt.bracket>: </prompt.bracket>')
            result = self._session.prompt(formatted_prompt)
            return result
        except EOFError:
            return None
        except KeyboardInterrupt:
            return ""

    def multiline_prompt(self, message: str = "You") -> Optional[str]:
        """Get multi-line input

        Args:
            message: Prompt message

        Returns:
            User input or None if cancelled
        """
        if self._session is None:
            # Fallback
            lines = []
            print(f"\n{message} (press Ctrl+D on empty line to finish):")
            try:
                while True:
                    line = input()
                    lines.append(line)
            except EOFError:
                return '\n'.join(lines)

        try:
            formatted_prompt = HTML(f'\n<prompt>{message}</prompt><prompt.bracket> (multiline): </prompt.bracket>')
            result = self._session.prompt(
                formatted_prompt,
                multiline=True,
                prompt_continuation=lambda width, line_number, wrap_count: '... '
            )
            return result
        except EOFError:
            return None
        except KeyboardInterrupt:
            return ""

    def update_workspace(self, workspace: Path):
        """Update workspace for file completion

        Args:
            workspace: New workspace path
        """
        self.workspace = workspace
        if self._session and self.enable_completion:
            self._session.completer = CLICompleter(workspace)

    @property
    def is_enhanced(self) -> bool:
        """Check if enhanced mode is available"""
        return self._session is not None


def get_interactive_session(
    workspace: Path,
    history_file: Optional[Path] = None,
    enable_history: bool = True,
    enable_completion: bool = True
) -> InteractiveSession:
    """Factory function to get interactive session

    Args:
        workspace: Workspace directory
        history_file: Path to history file
        enable_history: Enable command history
        enable_completion: Enable auto-completion

    Returns:
        InteractiveSession instance
    """
    return InteractiveSession(
        workspace=workspace,
        history_file=history_file,
        enable_history=enable_history,
        enable_completion=enable_completion
    )

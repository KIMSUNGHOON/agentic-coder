"""Terminal UI for TestCodeAgent CLI

Rich-based terminal interface providing:
- Interactive REPL mode
- Streaming progress indicators
- Markdown rendering for AI responses
- Syntax highlighting for code
- Slash command handling
"""

import asyncio
from typing import Optional, Dict, Any
from pathlib import Path

from rich.console import Console
from rich.markdown import Markdown
from rich.panel import Panel
from rich.prompt import Prompt
from rich.progress import Progress, SpinnerColumn, TextColumn, BarColumn
from rich.syntax import Syntax
from rich.table import Table
from rich.live import Live
from rich.text import Text

from cli.session_manager import SessionManager


class TerminalUI:
    """Rich-based terminal user interface"""

    def __init__(self, session_mgr: SessionManager):
        """Initialize terminal UI

        Args:
            session_mgr: SessionManager instance
        """
        self.session_mgr = session_mgr
        self.console = Console()

    def start_interactive(self):
        """Start interactive REPL mode"""
        self._show_welcome()

        while True:
            try:
                # Get user input
                user_input = Prompt.ask("\n[bold cyan]You[/bold cyan]")

                if not user_input.strip():
                    continue

                # Handle slash commands
                if user_input.startswith("/"):
                    self._handle_command(user_input)
                    continue

                # Execute workflow
                asyncio.run(self._execute_workflow(user_input))

            except KeyboardInterrupt:
                self.console.print("\n[yellow]Use /exit or Ctrl+D to quit[/yellow]")
                continue
            except EOFError:
                self._handle_exit()
                break

    def execute_one_shot(self, prompt: str):
        """Execute single prompt and exit

        Args:
            prompt: User prompt
        """
        self.console.print(Panel(
            f"[cyan]Executing:[/cyan] {prompt}",
            title="TestCodeAgent - One-shot Mode",
            border_style="cyan"
        ))

        asyncio.run(self._execute_workflow(prompt))

    async def _execute_workflow(self, user_request: str):
        """Execute workflow with streaming progress

        Args:
            user_request: User's request
        """
        current_agent = None
        current_content = ""
        artifacts = []
        streaming_display = None

        # Agent-specific status messages
        agent_status_map = {
            "Supervisor": "🧠 Analyzing request and planning workflow...",
            "PlanningHandler": "📋 Creating detailed implementation plan...",
            "CoderHandler": "💻 Generating code...",
            "ReviewerHandler": "🔍 Reviewing code quality...",
            "RefinerHandler": "✨ Refining and optimizing code...",
            "DebugHandler": "🐛 Debugging and fixing errors...",
            "TestHandler": "🧪 Writing tests...",
            "DocHandler": "📝 Generating documentation...",
        }

        with Progress(
            SpinnerColumn(),
            TextColumn("[progress.description]{task.description}"),
            BarColumn(),
            console=self.console,
            transient=False
        ) as progress:
            # Create progress task
            task = progress.add_task("[cyan]Initializing...", total=None)

            try:
                async for update in self.session_mgr.execute_streaming_workflow(user_request):
                    update_type = update.get("type")

                    if update_type == "agent_start":
                        current_agent = update.get("agent")

                        # Get agent-specific status message
                        status_msg = agent_status_map.get(current_agent, f"{current_agent} working...")
                        progress.update(task, description=f"[cyan]{status_msg}")

                        # Reset content for new agent
                        current_content = ""

                    elif update_type == "agent_stream":
                        # Accumulate and update streaming content
                        chunk = update.get("content", "")
                        current_content += chunk

                        # Update progress with content length indicator
                        char_count = len(current_content)
                        if char_count > 0:
                            status_msg = agent_status_map.get(current_agent, current_agent)
                            progress.update(
                                task,
                                description=f"[cyan]{status_msg} ({char_count} chars)"
                            )

                    elif update_type == "agent_end":
                        # Display accumulated content with Live rendering
                        if current_content:
                            # Stop progress to display content
                            progress.stop()
                            self._display_agent_response(current_agent, current_content)
                            # Resume progress
                            progress.start()
                            current_content = ""

                    elif update_type == "artifact":
                        # Store artifact for later display
                        artifacts.append(update)

                    elif update_type == "final_response":
                        # Display final response
                        final_content = update.get("content", "")
                        if final_content and final_content != current_content:
                            progress.stop()
                            self.console.print("\n[bold green]✅ Complete![/bold green]")
                            self.console.print(Markdown(final_content))
                            progress.start()

                    elif update_type == "error":
                        error_msg = update.get("message", "Unknown error")
                        progress.stop()
                        self.console.print(f"\n[bold red]❌ Error:[/bold red] {error_msg}")
                        progress.start()

            except Exception as e:
                self.console.print(f"\n[bold red]❌ Execution Error:[/bold red] {str(e)}")
                import traceback
                self.console.print(f"[dim]{traceback.format_exc()}[/dim]")
                return

        # Display artifacts if any
        if artifacts:
            self._display_artifacts(artifacts)

    def _display_agent_response(self, agent: str, content: str):
        """Display agent response with formatting and syntax highlighting

        Args:
            agent: Agent name
            content: Response content
        """
        if not content.strip():
            return

        self.console.print(f"\n[bold magenta]{agent}:[/bold magenta]")

        # Check if content contains code blocks for syntax highlighting
        if "```" in content:
            # Render as markdown which handles code blocks
            try:
                self.console.print(Markdown(content))
            except Exception:
                # Fallback to plain text
                self.console.print(content)
        else:
            # Plain text or markdown without code blocks
            try:
                self.console.print(Markdown(content))
            except Exception:
                self.console.print(content)

    def _display_artifacts(self, artifacts: list):
        """Display file artifacts with detailed information

        Args:
            artifacts: List of artifact updates
        """
        if not artifacts:
            return

        self.console.print("\n[bold green]📁 Files Generated:[/bold green]")

        table = Table(show_header=True, header_style="bold cyan", show_lines=False)
        table.add_column("Action", style="dim", width=10)
        table.add_column("File Path", overflow="fold")
        table.add_column("Lines", justify="right", width=8)
        table.add_column("Size", justify="right", width=10)

        for artifact in artifacts:
            action = artifact.get("action", "unknown")
            file_path = artifact.get("file_path", "")
            lines = artifact.get("lines", 0)

            # Color code by action
            if action == "created":
                action_str = "[green]CREATED[/green]"
                icon = "✨"
            elif action == "modified":
                action_str = "[yellow]MODIFIED[/yellow]"
                icon = "📝"
            elif action == "deleted":
                action_str = "[red]DELETED[/red]"
                icon = "🗑️"
            else:
                action_str = action
                icon = "📄"

            # Get file size if file exists
            file_size_str = "-"
            try:
                file_full_path = Path(self.session_mgr.workspace) / file_path
                if file_full_path.exists():
                    size_bytes = file_full_path.stat().st_size
                    if size_bytes < 1024:
                        file_size_str = f"{size_bytes}B"
                    elif size_bytes < 1024 * 1024:
                        file_size_str = f"{size_bytes / 1024:.1f}KB"
                    else:
                        file_size_str = f"{size_bytes / (1024 * 1024):.1f}MB"
            except Exception:
                pass

            # Format file path with icon
            file_display = f"{icon} {file_path}"

            table.add_row(
                action_str,
                file_display,
                str(lines) if lines else "-",
                file_size_str
            )

        self.console.print(table)

        # Summary
        total_files = len(artifacts)
        created = sum(1 for a in artifacts if a.get("action") == "created")
        modified = sum(1 for a in artifacts if a.get("action") == "modified")
        deleted = sum(1 for a in artifacts if a.get("action") == "deleted")

        summary = []
        if created:
            summary.append(f"[green]{created} created[/green]")
        if modified:
            summary.append(f"[yellow]{modified} modified[/yellow]")
        if deleted:
            summary.append(f"[red]{deleted} deleted[/red]")

        if summary:
            self.console.print(f"\n[dim]Total: {total_files} files ({', '.join(summary)})[/dim]")

    def _handle_command(self, command: str):
        """Handle slash commands

        Args:
            command: Command string (starting with /)
        """
        cmd_parts = command[1:].split()
        if not cmd_parts:
            return

        cmd_name = cmd_parts[0].lower()
        cmd_args = cmd_parts[1:]

        if cmd_name == "help":
            self._cmd_help()
        elif cmd_name == "status":
            self._cmd_status()
        elif cmd_name == "history":
            self._cmd_history()
        elif cmd_name == "context":
            self._cmd_context()
        elif cmd_name == "files":
            self._cmd_files()
        elif cmd_name == "preview":
            self._cmd_preview(cmd_args)
        elif cmd_name == "clear":
            self._cmd_clear()
        elif cmd_name in ["exit", "quit"]:
            self._handle_exit()
            raise EOFError()
        elif cmd_name == "sessions":
            self._cmd_sessions()
        else:
            self.console.print(f"[red]Unknown command: {cmd_name}[/red]")
            self.console.print("Type [cyan]/help[/cyan] for available commands")

    def _cmd_help(self):
        """Show help message"""
        help_text = """
# Available Commands

## Session Management
- `/status` - Show current session status
- `/sessions` - List all saved sessions
- `/history` - Show conversation history
- `/context` - Show extracted context information

## Workspace
- `/files` - Show generated/modified files
- `/preview <file>` - Preview file with syntax highlighting
- `/clear` - Clear terminal screen

## Utility
- `/help` - Show this help message
- `/exit` or `/quit` - Exit CLI (also Ctrl+D)

## Tips
- Press Ctrl+C to cancel current input
- Press Ctrl+D to exit
- Use arrow keys to navigate command history

## Examples
```bash
/preview calculator.py
/preview src/utils.ts
```
        """
        self.console.print(Markdown(help_text))

    def _cmd_status(self):
        """Show session status"""
        summary = self.session_mgr.get_history_summary()

        table = Table(show_header=False, box=None)
        table.add_column("Key", style="cyan")
        table.add_column("Value")

        table.add_row("Session ID", summary.get("session_id", "Unknown"))
        table.add_row("Workspace", summary.get("workspace", "Unknown"))
        table.add_row("Model", summary.get("model", "Unknown"))
        table.add_row("Total Messages", str(summary.get("total_messages", 0)))
        table.add_row("User Messages", str(summary.get("user_messages", 0)))
        table.add_row("AI Messages", str(summary.get("assistant_messages", 0)))
        table.add_row("Created", summary.get("created_at", "Unknown"))
        table.add_row("Updated", summary.get("updated_at", "N/A"))

        self.console.print(Panel(table, title="Session Status", border_style="cyan"))

    def _cmd_history(self):
        """Show conversation history"""
        history = self.session_mgr.conversation_history

        if not history:
            self.console.print("[yellow]No conversation history yet[/yellow]")
            return

        self.console.print(f"\n[bold cyan]Conversation History[/bold cyan] ({len(history)} messages)\n")

        for i, msg in enumerate(history, 1):
            role = msg.get("role", "unknown")
            content = msg.get("content", "")
            timestamp = msg.get("timestamp", "")

            role_color = "cyan" if role == "user" else "magenta"
            role_name = "You" if role == "user" else "AI"

            self.console.print(f"[bold {role_color}][{i}] {role_name}[/bold {role_color}] ({timestamp})")

            # Truncate long messages
            if len(content) > 200:
                content = content[:200] + "..."

            self.console.print(f"  {content}\n")

    def _cmd_context(self):
        """Show context information"""
        context = self.session_mgr.get_context_info()

        self.console.print("\n[bold cyan]Context Information[/bold cyan]\n")

        # Files mentioned
        files = context.get("files_mentioned", [])
        if files:
            self.console.print("[bold green]Files Mentioned:[/bold green]")
            for file in files[:10]:
                self.console.print(f"  • {file}")
            if len(files) > 10:
                self.console.print(f"  ... and {len(files) - 10} more")
            self.console.print()

        # Errors encountered
        errors = context.get("errors_encountered", [])
        if errors:
            self.console.print("[bold red]Errors Encountered:[/bold red]")
            for error in errors[:5]:
                self.console.print(f"  • {error}")
            if len(errors) > 5:
                self.console.print(f"  ... and {len(errors) - 5} more")
            self.console.print()

        # Decisions made
        decisions = context.get("decisions_made", [])
        if decisions:
            self.console.print("[bold yellow]Key Decisions:[/bold yellow]")
            for decision in decisions[:5]:
                self.console.print(f"  • {decision}")
            if len(decisions) > 5:
                self.console.print(f"  ... and {len(decisions) - 5} more")
            self.console.print()

        if not files and not errors and not decisions:
            self.console.print("[yellow]No context information extracted yet[/yellow]")

    def _cmd_files(self):
        """Show generated/modified files"""
        workspace = self.session_mgr.workspace

        # List files in workspace (simple implementation)
        # In production, this should track actual modified files
        self.console.print(f"\n[bold cyan]Workspace:[/bold cyan] {workspace}\n")
        self.console.print("[yellow]Note: File tracking will be implemented with artifact system[/yellow]")

    def _cmd_preview(self, args: list):
        """Preview file with syntax highlighting

        Args:
            args: Command arguments (file path)
        """
        if not args:
            self.console.print("[yellow]Usage: /preview <file_path>[/yellow]")
            self.console.print("Example: /preview calculator.py")
            return

        file_path = " ".join(args)  # Support paths with spaces
        full_path = Path(self.session_mgr.workspace) / file_path

        if not full_path.exists():
            self.console.print(f"[red]File not found:[/red] {file_path}")
            return

        if not full_path.is_file():
            self.console.print(f"[red]Not a file:[/red] {file_path}")
            return

        try:
            # Read file content
            content = full_path.read_text(encoding='utf-8')

            # Detect language from file extension
            ext = full_path.suffix.lower()
            language_map = {
                '.py': 'python',
                '.js': 'javascript',
                '.ts': 'typescript',
                '.tsx': 'tsx',
                '.jsx': 'jsx',
                '.java': 'java',
                '.c': 'c',
                '.cpp': 'cpp',
                '.h': 'c',
                '.hpp': 'cpp',
                '.cs': 'csharp',
                '.go': 'go',
                '.rs': 'rust',
                '.rb': 'ruby',
                '.php': 'php',
                '.swift': 'swift',
                '.kt': 'kotlin',
                '.md': 'markdown',
                '.json': 'json',
                '.yaml': 'yaml',
                '.yml': 'yaml',
                '.toml': 'toml',
                '.xml': 'xml',
                '.html': 'html',
                '.css': 'css',
                '.scss': 'scss',
                '.sql': 'sql',
                '.sh': 'bash',
                '.bash': 'bash',
                '.ps1': 'powershell',
                '.r': 'r',
                '.R': 'r',
            }
            lexer_name = language_map.get(ext, 'text')

            # Display file info
            file_size = full_path.stat().st_size
            if file_size < 1024:
                size_str = f"{file_size}B"
            elif file_size < 1024 * 1024:
                size_str = f"{file_size / 1024:.1f}KB"
            else:
                size_str = f"{file_size / (1024 * 1024):.1f}MB"

            line_count = content.count('\n') + 1

            self.console.print(f"\n[bold cyan]File:[/bold cyan] {file_path}")
            self.console.print(f"[dim]Size: {size_str} | Lines: {line_count} | Type: {lexer_name}[/dim]\n")

            # Display with syntax highlighting
            syntax = Syntax(
                content,
                lexer_name,
                theme="monokai",
                line_numbers=True,
                word_wrap=False
            )
            self.console.print(syntax)

        except UnicodeDecodeError:
            self.console.print(f"[red]Cannot preview binary file:[/red] {file_path}")
        except Exception as e:
            self.console.print(f"[red]Error reading file:[/red] {e}")

    def _cmd_clear(self):
        """Clear terminal screen"""
        self.console.clear()

    def _cmd_sessions(self):
        """List all sessions"""
        sessions = self.session_mgr.list_sessions()

        if not sessions:
            self.console.print("[yellow]No saved sessions found[/yellow]")
            return

        table = Table(show_header=True, header_style="bold cyan")
        table.add_column("Session ID", style="dim")
        table.add_column("Created")
        table.add_column("Updated")
        table.add_column("Messages", justify="right")
        table.add_column("Workspace")

        for session in sessions[:10]:  # Show latest 10
            table.add_row(
                session.get("session_id", ""),
                session.get("created_at", "")[:19],  # Truncate ISO timestamp
                session.get("updated_at", "")[:19],
                str(session.get("message_count", 0)),
                str(Path(session.get("workspace", "")).name)
            )

        self.console.print(Panel(table, title="Recent Sessions", border_style="cyan"))

        if len(sessions) > 10:
            self.console.print(f"\n[dim]Showing 10 of {len(sessions)} sessions[/dim]")

    def _handle_exit(self):
        """Handle exit"""
        self.console.print("\n[cyan]Saving session...[/cyan]")
        self.session_mgr.save_session()
        self.console.print("[green]✓[/green] Session saved")
        self.console.print("\n[bold cyan]Thank you for using TestCodeAgent![/bold cyan]")

    def _show_welcome(self):
        """Show welcome message"""
        welcome_text = f"""
[bold cyan]TestCodeAgent CLI[/bold cyan] - Interactive AI Coding Assistant

[dim]Session ID:[/dim] {self.session_mgr.session_id}
[dim]Workspace:[/dim] {self.session_mgr.workspace}
[dim]Model:[/dim] {self.session_mgr.model}

Type your request or use slash commands (type [cyan]/help[/cyan] for available commands)
Press [cyan]Ctrl+D[/cyan] to exit
        """

        self.console.print(Panel(
            welcome_text.strip(),
            border_style="cyan",
            padding=(1, 2)
        ))

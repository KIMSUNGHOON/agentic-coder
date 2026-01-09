"""Terminal UI for Agentic Coder CLI

Rich-based terminal interface providing:
- Interactive REPL mode with command history and auto-completion
- Streaming progress indicators
- Markdown rendering for AI responses
- Syntax highlighting for code
- Slash command handling
- Configuration management

Phase 3 Enhancements:
- prompt_toolkit integration for enhanced input
- Command history persistence
- Auto-completion for commands and file paths
- Configuration file support
"""

import asyncio
from typing import Optional, Dict, Any
from pathlib import Path

try:
    from rich.console import Console
    from rich.markdown import Markdown
    from rich.panel import Panel
    from rich.prompt import Prompt
    from rich.progress import Progress, SpinnerColumn, TextColumn, BarColumn
    from rich.syntax import Syntax
    from rich.table import Table
    from rich.live import Live
    from rich.text import Text
    RICH_AVAILABLE = True
except ImportError:
    RICH_AVAILABLE = False
    # Provide minimal fallback message
    raise ImportError(
        "The 'rich' package is required for CLI mode. "
        "Install it with: pip install rich"
    )

from cli.session_manager import SessionManager
from cli.config import ConfigManager, CLIConfig
from cli.interactive import get_interactive_session, InteractiveSession, SLASH_COMMANDS


class TerminalUI:
    """Rich-based terminal user interface"""

    def __init__(self, session_mgr: SessionManager, config: Optional[CLIConfig] = None):
        """Initialize terminal UI

        Args:
            session_mgr: SessionManager instance
            config: Optional CLI configuration
        """
        self.session_mgr = session_mgr
        self.console = Console()

        # Load configuration
        self.config_mgr = ConfigManager(workspace=str(session_mgr.workspace))
        self.config = config or self.config_mgr.get_config()

        # Initialize interactive session with history and completion
        self.interactive = get_interactive_session(
            workspace=session_mgr.workspace,
            history_file=self.config_mgr.get_history_path(),
            enable_history=self.config.save_history,
            enable_completion=True
        )

    def start_interactive(self):
        """Start interactive REPL mode with enhanced input"""
        self._show_welcome()

        # Show enhanced mode status
        if self.interactive.is_enhanced:
            self.console.print(
                "[dim]Enhanced mode: Command history and auto-completion enabled "
                "(Tab to complete, Up/Down for history)[/dim]\n"
            )

        while True:
            try:
                # Build dynamic prompt with workspace info
                workspace_name = self.session_mgr.workspace.name
                session_id_short = self.session_mgr.session_id.split('-')[-1][:8]
                prompt_text = f"[{workspace_name}:{session_id_short}] You"

                # Get user input using enhanced interactive session
                user_input = self.interactive.prompt(prompt_text)

                # Handle None (Ctrl+D)
                if user_input is None:
                    self._handle_exit()
                    break

                # Handle empty input
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
            title="Agentic Coder - One-shot Mode",
            border_style="cyan"
        ))

        asyncio.run(self._execute_workflow(prompt))

    async def _execute_workflow(self, user_request: str):
        """Execute workflow with streaming progress

        Args:
            user_request: User's request
        """
        artifacts = []
        current_iteration = 0
        total_iterations = 15  # Default max
        current_status = "Initializing..."

        # Show initial request in a clear panel
        self.console.print()
        self.console.print(Panel(
            f"[bold white]{user_request}[/bold white]",
            title="[bold cyan]🎯 Your Request[/bold cyan]",
            border_style="cyan",
            padding=(1, 2)
        ))
        self.console.print()

        from rich.live import Live
        from rich.table import Table

        def create_status_display():
            """Create live status display table"""
            table = Table.grid(padding=(0, 2))
            table.add_column(style="cyan", justify="right")
            table.add_column(style="white")

            # Progress indicator
            progress_bar = "█" * int((current_iteration / total_iterations) * 20) + "░" * (20 - int((current_iteration / total_iterations) * 20))
            progress_text = f"{current_iteration}/{total_iterations}"

            table.add_row("[bold]Progress:", f"[{progress_bar}] {progress_text}")
            table.add_row("[bold]Status:", current_status)

            return Panel(
                table,
                title="[bold yellow]⚙️  Working...[/bold yellow]",
                border_style="yellow",
                padding=(0, 2)
            )

        with Live(create_status_display(), console=self.console, refresh_per_second=4) as live:

            try:
                # Use Tool Use workflow (dynamic LLM-driven approach)
                async for update in self.session_mgr.execute_tool_use_workflow(user_request):
                    update_type = update.get("type")

                    # Handle different update types from Tool Use pattern
                    if update_type == "tool_iteration":
                        # New iteration starting
                        current_iteration = update.get("iteration", 0)
                        total_iterations = update.get("max_iterations", 15)
                        current_status = f"🔄 Starting iteration {current_iteration}..."
                        live.update(create_status_display())

                    elif update_type == "reasoning":
                        # LLM reasoning/thinking (CoT) - MOST IMPORTANT FOR UX!
                        reasoning = update.get("content", "")
                        if reasoning and len(reasoning.strip()) > 10:
                            current_status = "🧠 AI is thinking and planning next steps..."
                            live.update(create_status_display())

                            # Pause live display to show reasoning
                            live.stop()

                            # Show full reasoning in an expandable panel
                            reasoning_text = reasoning.strip()
                            if len(reasoning_text) > 500:
                                reasoning_preview = reasoning_text[:500] + "..."
                            else:
                                reasoning_preview = reasoning_text

                            self.console.print(Panel(
                                f"[italic dim]{reasoning_preview}[/italic dim]",
                                title="[bold cyan]💭 AI Reasoning (Chain-of-Thought)[/bold cyan]",
                                subtitle="[dim]Thinking about the best approach...[/dim]",
                                border_style="cyan",
                                padding=(1, 2)
                            ))

                            live.start()
                            current_status = "✅ Reasoning complete, executing actions..."
                            live.update(create_status_display())

                    elif update_type == "tool_call_start":
                        # Tool execution starting
                        tool_name = update.get("tool")
                        arguments = update.get("arguments", {})

                        # Create human-readable tool description
                        tool_descriptions = {
                            "write_file": "📝 Writing file",
                            "read_file": "📖 Reading file",
                            "execute_python": "🐍 Running Python code",
                            "execute_bash": "⚡ Executing command",
                            "search_files": "🔍 Searching files",
                            "list_directory": "📂 Listing directory",
                            "git_commit": "📦 Committing changes",
                            "web_search": "🌐 Searching web",
                        }

                        tool_desc = tool_descriptions.get(tool_name, f"🔧 {tool_name}")

                        # Show key argument
                        if "path" in arguments:
                            detail = f": {arguments['path']}"
                        elif "command" in arguments:
                            cmd = str(arguments['command'])[:40]
                            detail = f": {cmd}..."
                        elif "code" in arguments:
                            detail = ": <code snippet>"
                        else:
                            detail = ""

                        current_status = f"{tool_desc}{detail}"
                        live.update(create_status_display())

                    elif update_type == "tool_call_result":
                        # Tool execution completed
                        tool_name = update.get("tool")
                        result = update.get("result", {})
                        success = result.get("success", False)

                        if success:
                            # Pause live to show result
                            live.stop()

                            # Special handling for file operations with full paths
                            if tool_name == "write_file":
                                metadata = result.get("metadata", {})
                                path = metadata.get("path", "unknown")
                                lines = metadata.get("lines", 0)
                                size = metadata.get("bytes", 0)

                                # Show full path with file icon and success badge
                                self.console.print(Panel(
                                    f"[bold cyan]{path}[/bold cyan]\n"
                                    f"[dim]→ {lines} lines, {size:,} bytes[/dim]",
                                    title="[bold green]✅ File Created[/bold green]",
                                    border_style="green",
                                    padding=(0, 2)
                                ))

                                artifacts.append({
                                    "action": "created",
                                    "filename": path,
                                    "lines": lines,
                                    "size": size
                                })
                            elif tool_name == "read_file":
                                metadata = result.get("metadata", {})
                                path = metadata.get("path", "unknown")
                                lines = metadata.get("lines", 0)
                                size_mb = metadata.get("size_mb", 0)

                                self.console.print(f"[green]✓ Read:[/green] [cyan]{path}[/cyan] [dim]({lines} lines, {size_mb:.2f} MB)[/dim]")
                            elif tool_name == "execute_python":
                                output = result.get("output", {})
                                # Handle both dict and string output formats
                                if isinstance(output, dict):
                                    stdout = output.get("stdout", "")
                                    stderr = output.get("stderr", "")
                                    returncode = output.get("returncode", 0)

                                    # Show stdout if available
                                    if stdout and stdout.strip():
                                        output_preview = stdout[:200] + "..." if len(stdout) > 200 else stdout
                                        self.console.print(Panel(
                                            f"[dim]{output_preview}[/dim]",
                                            title="[bold green]✅ Python Execution Result[/bold green]",
                                            border_style="green",
                                            padding=(1, 2)
                                        ))
                                    # Show stderr if there was an error
                                    elif stderr and stderr.strip():
                                        self.console.print(Panel(
                                            f"[red]{stderr[:200]}[/red]",
                                            title="[bold red]❌ Python Error[/bold red]",
                                            border_style="red"
                                        ))
                                    else:
                                        self.console.print("[green]✓[/green] Python code executed successfully")
                                elif isinstance(output, str):
                                    # Fallback for string output
                                    if output and output.strip():
                                        output_preview = output[:200] + "..." if len(output) > 200 else output
                                        self.console.print(Panel(
                                            f"[dim]{output_preview}[/dim]",
                                            title="[bold green]✅ Python Execution Result[/bold green]",
                                            border_style="green",
                                            padding=(1, 2)
                                        ))
                                    else:
                                        self.console.print("[green]✓[/green] Python code executed successfully")
                                else:
                                    self.console.print("[green]✓[/green] Python code executed successfully")
                            elif tool_name == "execute_bash":
                                output = result.get("output", {})
                                # Handle both dict and string output formats
                                if isinstance(output, dict):
                                    stdout = output.get("stdout", "")
                                    stderr = output.get("stderr", "")
                                    command = output.get("command", "")

                                    # Show stdout if available
                                    if stdout and stdout.strip():
                                        output_preview = stdout[:200] + "..." if len(stdout) > 200 else stdout
                                        self.console.print(f"[green]✓ Command output:[/green]\n[dim]{output_preview}[/dim]")
                                    # Show stderr if there was an error
                                    elif stderr and stderr.strip():
                                        self.console.print(Panel(
                                            f"[red]{stderr[:200]}[/red]",
                                            title="[bold red]❌ Command Error[/bold red]",
                                            border_style="red"
                                        ))
                                    else:
                                        self.console.print("[green]✓[/green] Command executed successfully")
                                elif isinstance(output, str):
                                    # Fallback for string output
                                    if output and output.strip():
                                        output_preview = output[:200] + "..." if len(output) > 200 else output
                                        self.console.print(f"[green]✓ Command output:[/green]\n[dim]{output_preview}[/dim]")
                                    else:
                                        self.console.print("[green]✓[/green] Command executed successfully")
                                else:
                                    self.console.print("[green]✓[/green] Command executed successfully")
                            else:
                                # Generic tool success
                                self.console.print(f"[green]✓[/green] {tool_name} completed")

                            # Resume live display
                            current_status = f"✅ {tool_name} completed"
                            live.start()
                            live.update(create_status_display())
                        else:
                            # Show tool error with more detail
                            error = result.get("error", "Unknown error")
                            live.stop()

                            self.console.print(Panel(
                                f"[red]{error}[/red]",
                                title=f"[bold red]❌ {tool_name} Failed[/bold red]",
                                border_style="red",
                                padding=(1, 2)
                            ))

                            current_status = f"❌ {tool_name} failed"
                            live.start()
                            live.update(create_status_display())

                    elif update_type == "final_response":
                        # Final response from LLM - Task complete!
                        response = update.get("content", "")
                        summary = update.get("summary", "")

                        # Try to parse JSON response (in case LLM didn't use tool calling properly)
                        import json as json_module
                        if response.strip().startswith("{") and "response" in response:
                            try:
                                parsed = json_module.loads(response)
                                if "response" in parsed:
                                    response = parsed["response"]
                                if "summary" in parsed and not summary:
                                    summary = parsed["summary"]
                            except:
                                pass  # Keep original response if parsing fails

                        # Stop live display
                        current_status = "✅ Task completed!"
                        live.update(create_status_display())
                        live.stop()

                        self.console.print()  # Spacing

                        # Build final response panel
                        final_content = []
                        if summary and summary != "Completed without additional tools":
                            final_content.append(f"**Summary:** {summary}\n")
                        if response:
                            final_content.append(response)

                        if final_content:
                            self.console.print(Panel(
                                Markdown("\n".join(final_content)),
                                title="[bold green]✅ Task Complete[/bold green]",
                                subtitle=f"[dim]Completed in {current_iteration} iteration(s)[/dim]",
                                border_style="green",
                                padding=(1, 2)
                            ))
                        else:
                            self.console.print(Panel(
                                "[bold green]Task completed successfully![/bold green]",
                                title="[bold green]✅ Complete[/bold green]",
                                border_style="green"
                            ))

                    elif update_type == "error":
                        # Execution error
                        error_msg = update.get("message", "Unknown error")
                        live.stop()

                        self.console.print(Panel(
                            f"[red]{error_msg}[/red]",
                            title="[bold red]❌ Error[/bold red]",
                            border_style="red",
                            padding=(1, 2)
                        ))

                        current_status = f"❌ Error occurred"
                        live.start()
                        live.update(create_status_display())

                    elif update_type == "max_iterations_reached":
                        # Hit max iteration limit
                        live.stop()

                        content = update.get("content", "")
                        message = f"[yellow]Maximum iterations ({total_iterations}) reached.[/yellow]"
                        if content:
                            message += f"\n\n{content}"

                        self.console.print(Panel(
                            message,
                            title="[bold yellow]⚠️  Iteration Limit Reached[/bold yellow]",
                            border_style="yellow",
                            padding=(1, 2)
                        ))

                        current_status = "⚠️ Max iterations reached"
                        live.start()
                        live.update(create_status_display())

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
        elif cmd_name == "config":
            self._cmd_config(cmd_args)
        elif cmd_name == "model":
            self._cmd_model(cmd_args)
        elif cmd_name == "workspace":
            self._cmd_workspace(cmd_args)
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
- `/workspace [path]` - Show or change workspace
- `/clear` - Clear terminal screen

## Configuration
- `/config` - Show current configuration
- `/config init` - Create default config file
- `/config set <key> <value>` - Update configuration
- `/model [name]` - Show or change current model

## Utility
- `/help` - Show this help message
- `/exit` or `/quit` - Exit CLI (also Ctrl+D)

## Tips
- Press **Tab** for auto-completion
- Press **Up/Down** to navigate command history
- Press **Ctrl+R** to search command history
- Press **Ctrl+C** to cancel current input
- Press **Ctrl+D** to exit

## Examples
```bash
/preview calculator.py
/preview src/utils.ts
/config set llm.model qwen2.5-coder:32b
/model deepseek-r1:14b
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
        self.console.print("\n[bold cyan]Thank you for using Agentic Coder![/bold cyan]")

    def _show_welcome(self):
        """Show welcome message"""
        welcome_text = f"""
[bold cyan]Agentic Coder CLI[/bold cyan] - Interactive AI Coding Assistant

[dim]Session ID:[/dim] {self.session_mgr.session_id}
[dim]Base Workspace:[/dim] {self.session_mgr.base_workspace}
[dim]Session Workspace:[/dim] {self.session_mgr.workspace}
[dim]Model:[/dim] {self.session_mgr.model}

Type your request or use slash commands (type [cyan]/help[/cyan] for available commands)
Press [cyan]Ctrl+D[/cyan] to exit
        """

        self.console.print(Panel(
            welcome_text.strip(),
            border_style="cyan",
            padding=(1, 2)
        ))

    def _cmd_config(self, args: list):
        """Handle config command

        Args:
            args: Command arguments
        """
        if not args:
            # Show current config
            self._show_config()
            return

        subcommand = args[0].lower()

        if subcommand == "init":
            # Create default config
            location = args[1] if len(args) > 1 else "user"
            config_path = self.config_mgr.create_default_config(location)
            self.console.print(f"[green]✓[/green] Created config file: {config_path}")

        elif subcommand == "set":
            # Set config value
            if len(args) < 3:
                self.console.print("[yellow]Usage: /config set <key> <value>[/yellow]")
                self.console.print("Example: /config set llm.model qwen2.5-coder:32b")
                return

            key = args[1]
            value = " ".join(args[2:])
            self._set_config_value(key, value)

        elif subcommand == "show":
            self._show_config()

        elif subcommand == "path":
            # Show config file paths
            self.console.print("\n[bold cyan]Configuration File Paths:[/bold cyan]")
            self.console.print(f"  User config: {self.config_mgr.USER_CONFIG_FILE}")
            project_config = self.session_mgr.workspace / self.config_mgr.PROJECT_CONFIG_FILE
            self.console.print(f"  Project config: {project_config}")

        else:
            self.console.print(f"[red]Unknown config subcommand: {subcommand}[/red]")
            self.console.print("Available: show, init, set, path")

    def _show_config(self):
        """Display current configuration"""
        config = self.config

        table = Table(show_header=True, header_style="bold cyan", title="Current Configuration")
        table.add_column("Category", style="dim")
        table.add_column("Setting")
        table.add_column("Value")

        # LLM settings
        table.add_row("LLM", "model", config.model)
        table.add_row("LLM", "api_endpoint", config.api_endpoint)
        table.add_row("LLM", "temperature", str(config.temperature))

        # UI settings
        table.add_row("UI", "theme", config.theme)
        table.add_row("UI", "show_line_numbers", str(config.show_line_numbers))

        # History settings
        table.add_row("History", "file", config.history_file)
        table.add_row("History", "save_history", str(config.save_history))

        # Network settings
        table.add_row("Network", "mode", config.network_mode)
        table.add_row("Network", "timeout", str(config.timeout))

        # Debug settings
        table.add_row("Debug", "enabled", str(config.debug))

        self.console.print(table)

    def _set_config_value(self, key: str, value: str):
        """Set a configuration value

        Args:
            key: Config key (e.g., 'llm.model')
            value: Value to set
        """
        config = self.config

        # Parse key path
        parts = key.split('.')

        try:
            if parts[0] == "llm":
                if parts[1] == "model":
                    config.model = value
                elif parts[1] == "api_endpoint":
                    config.api_endpoint = value
                elif parts[1] == "temperature":
                    config.temperature = float(value)
                else:
                    raise KeyError(f"Unknown LLM setting: {parts[1]}")

            elif parts[0] == "ui":
                if parts[1] == "theme":
                    config.theme = value
                elif parts[1] == "syntax_theme":
                    config.syntax_theme = value
                else:
                    raise KeyError(f"Unknown UI setting: {parts[1]}")

            elif parts[0] == "network":
                if parts[1] == "mode":
                    if value not in ["online", "offline"]:
                        raise ValueError("Network mode must be 'online' or 'offline'")
                    config.network_mode = value
                elif parts[1] == "timeout":
                    config.timeout = int(value)
                else:
                    raise KeyError(f"Unknown network setting: {parts[1]}")

            elif parts[0] == "history":
                if parts[1] == "save":
                    config.save_history = value.lower() in ("true", "1", "yes")
                else:
                    raise KeyError(f"Unknown history setting: {parts[1]}")

            elif parts[0] == "debug":
                if parts[1] == "enabled":
                    config.debug = value.lower() in ("true", "1", "yes")
                else:
                    raise KeyError(f"Unknown debug setting: {parts[1]}")

            else:
                # Try direct attribute
                if hasattr(config, key):
                    setattr(config, key, value)
                else:
                    raise KeyError(f"Unknown config key: {key}")

            # Save to user config
            self.config_mgr.save_user_config(config)
            self.console.print(f"[green]✓[/green] Set {key} = {value}")

        except (KeyError, ValueError) as e:
            self.console.print(f"[red]Error:[/red] {e}")

    def _cmd_model(self, args: list):
        """Handle model command

        Args:
            args: Command arguments
        """
        if not args:
            # Show current model
            self.console.print(f"\n[bold cyan]Current Model:[/bold cyan] {self.session_mgr.model}")
            self.console.print("\n[dim]To change: /model <model-name>[/dim]")
            self.console.print("[dim]Examples: deepseek-r1:14b, qwen2.5-coder:32b[/dim]")
            return

        # Set new model
        new_model = args[0]
        old_model = self.session_mgr.model
        self.session_mgr.model = new_model
        self.config.model = new_model

        self.console.print(f"[green]✓[/green] Model changed: {old_model} → {new_model}")

    def _cmd_workspace(self, args: list):
        """Handle workspace command

        Args:
            args: Command arguments
        """
        if not args:
            # Show current workspace
            self.console.print(f"\n[bold cyan]Current Workspace:[/bold cyan] {self.session_mgr.workspace}")

            # Show workspace stats
            workspace = self.session_mgr.workspace
            if workspace.exists():
                files = list(workspace.rglob("*"))
                file_count = sum(1 for f in files if f.is_file())
                dir_count = sum(1 for f in files if f.is_dir())
                self.console.print(f"[dim]Files: {file_count}, Directories: {dir_count}[/dim]")

            self.console.print("\n[dim]To change: /workspace <path>[/dim]")
            return

        # Change workspace
        new_workspace = Path(args[0]).resolve()

        if not new_workspace.exists():
            self.console.print(f"[red]Directory not found:[/red] {new_workspace}")
            create = Prompt.ask("Create it?", choices=["y", "n"], default="n")
            if create == "y":
                new_workspace.mkdir(parents=True, exist_ok=True)
                self.console.print(f"[green]✓[/green] Created directory: {new_workspace}")
            else:
                return

        if not new_workspace.is_dir():
            self.console.print(f"[red]Not a directory:[/red] {new_workspace}")
            return

        old_workspace = self.session_mgr.workspace
        self.session_mgr.workspace = new_workspace

        # Update interactive session for file completion
        self.interactive.update_workspace(new_workspace)

        self.console.print(f"[green]✓[/green] Workspace changed: {old_workspace} → {new_workspace}")

"""Agentic 2.0 CLI Application

Main Textual application with interactive interface.
"""

import asyncio
from pathlib import Path
from textual.app import App, ComposeResult
from textual.containers import Container, Horizontal, Vertical
from textual.widgets import Header, Footer, Input, Static
from textual.binding import Binding
from rich.text import Text

from .components import (
    ChatPanel,
    ProgressDisplay,
    LogViewer,
    StatusBar,
    CoTViewer,
)
from .utils import SecurityChecker, CommandHistory


class AgenticApp(App):
    """Agentic 2.0 Interactive CLI

    Features:
    - Real-time conversation
    - Progress visualization
    - Chain-of-Thought display
    - System status monitoring
    - Local-only data storage
    """

    CSS = """
    Screen {
        layout: vertical;
    }

    #main-container {
        layout: horizontal;
        height: 1fr;
    }

    #left-panel {
        width: 2fr;
        layout: vertical;
    }

    #right-panel {
        width: 1fr;
        layout: vertical;
        border-left: solid $accent;
    }

    #chat-container {
        height: 1fr;
        border: solid $primary;
    }

    #input-container {
        height: auto;
        padding: 1;
        border-top: solid $accent;
    }

    #progress-container {
        height: 8;
        border: solid $primary;
    }

    #log-container {
        height: 1fr;
        border: solid $primary;
    }

    #cot-container {
        height: 1fr;
        border: solid $primary;
    }

    Input {
        border: none;
    }

    .label {
        background: $accent;
        padding: 0 1;
    }
    """

    BINDINGS = [
        Binding("ctrl+c", "quit", "Quit", show=True),
        Binding("ctrl+l", "clear_chat", "Clear Chat", show=False),
        Binding("ctrl+h", "toggle_cot", "Toggle CoT", show=False),
        Binding("ctrl+s", "save_session", "Save", show=False),
    ]

    TITLE = "Agentic 2.0 - AI Coding Assistant"
    SUB_TITLE = "Local GPT-OSS-120B | On-Premise Only"

    def __init__(self):
        super().__init__()
        self.security = SecurityChecker()
        self.history = CommandHistory()
        self.session_active = False
        self.cot_visible = True
        self.session_id = None  # Will be generated on first message

    def compose(self) -> ComposeResult:
        """Create the UI layout"""
        yield Header()

        with Container(id="main-container"):
            # Left panel: Chat + Input + Progress
            with Vertical(id="left-panel"):
                with Container(id="chat-container"):
                    yield Static("Chat", classes="label")
                    yield ChatPanel(id="chat-panel")

                with Container(id="input-container"):
                    yield Static("Message", classes="label")
                    yield Input(
                        placeholder="Type your message... (Ctrl+C to quit)",
                        id="message-input"
                    )

                with Container(id="progress-container"):
                    yield Static("Progress", classes="label")
                    yield ProgressDisplay(id="progress-display")

            # Right panel: Logs + CoT
            with Vertical(id="right-panel"):
                with Container(id="log-container"):
                    yield Static("Logs", classes="label")
                    yield LogViewer(id="log-viewer")

                if self.cot_visible:
                    with Container(id="cot-container"):
                        yield Static("Chain of Thought", classes="label")
                        yield CoTViewer(id="cot-viewer")

        yield StatusBar(id="status-bar")
        yield Footer()

    def on_mount(self) -> None:
        """Called when app is mounted"""
        self.title = self.TITLE
        self.sub_title = self.SUB_TITLE

        # Focus on input
        input_widget = self.query_one("#message-input", Input)
        input_widget.focus()

        # Security check
        if not self.security.check_local_only():
            self.notify(
                "⚠️  Security Warning: External network detected",
                severity="warning",
                timeout=10
            )

        # Load history
        self.history.load()

        # Update status
        status = self.query_one("#status-bar", StatusBar)
        status.update_status("Ready", "healthy")

    async def on_input_submitted(self, event: Input.Submitted) -> None:
        """Handle user input submission"""
        message = event.value.strip()

        if not message:
            return

        # Clear input
        input_widget = self.query_one("#message-input", Input)
        input_widget.value = ""

        # Security check
        if not self.security.validate_input(message):
            self.notify(
                "⚠️  Input blocked by security policy",
                severity="error"
            )
            return

        # Save to history (local only)
        self.history.add(message)

        # Display user message
        chat = self.query_one("#chat-panel", ChatPanel)
        chat.add_message("user", message)

        # Process command
        await self.process_message(message)

    async def process_message(self, message: str) -> None:
        """Process user message through backend workflow

        Args:
            message: User input message
        """
        import uuid
        import time
        from .backend_bridge import get_bridge, ProgressUpdate

        # Get UI components
        status = self.query_one("#status-bar", StatusBar)
        progress = self.query_one("#progress-display", ProgressDisplay)
        chat = self.query_one("#chat-panel", ChatPanel)
        log = self.query_one("#log-viewer", LogViewer)
        cot_viewer = self.query_one("#cot-viewer", CoTViewer)

        # Generate session ID on first message
        if not self.session_id:
            import os
            self.session_id = str(uuid.uuid4())
            status.set_session(self.session_id)

            # Get backend bridge and initialize to load config
            bridge = get_bridge()
            await bridge.initialize()

            # Get workspace path from config.yaml
            workspace_config = bridge.config.workspace
            base_workspace = os.path.expanduser(workspace_config.default_path)  # Expand ~ to home dir

            # Create session-specific workspace directory if isolation is enabled
            if workspace_config.isolation:
                self.session_workspace = os.path.join(base_workspace, self.session_id[:8])
                log.add_log("info", f"Isolation enabled - creating session directory")
            else:
                self.session_workspace = base_workspace
                log.add_log("info", f"Isolation disabled - using shared workspace")

            # CRITICAL: Add error handling for directory creation
            try:
                os.makedirs(self.session_workspace, exist_ok=True)
                log.add_log("info", f"✅ Session workspace created: {self.session_workspace}")
            except PermissionError as e:
                error_msg = f"❌ Permission denied creating workspace: {e}"
                log.add_log("error", error_msg)
                chat.add_status(f"❌ ERROR: Cannot create workspace - permission denied")
                chat.add_status(f"   Path: {self.session_workspace}")
                chat.add_status(f"   Please check directory permissions or run with appropriate access")
                status.update_status("Permission Error", "error")
                # Don't proceed - stop here
                return
            except OSError as e:
                error_msg = f"❌ Failed to create workspace: {e}"
                log.add_log("error", error_msg)
                chat.add_status(f"❌ ERROR: Workspace creation failed")
                chat.add_status(f"   Path: {self.session_workspace}")
                chat.add_status(f"   Error: {str(e)}")
                status.update_status("Workspace Error", "error")
                # Don't proceed - stop here
                return

            log.add_log("info", f"Session created: {self.session_id[:8]}")
            log.add_log("info", f"Config base workspace: {base_workspace}")
            log.add_log("info", f"Session workspace: {self.session_workspace}")

            # Display workspace info prominently in chat
            chat.add_status("=" * 60)
            chat.add_status(f"📁 SESSION WORKSPACE INITIALIZED")
            chat.add_status(f"   Session ID: {self.session_id[:8]}")
            chat.add_status(f"   Workspace: {self.session_workspace}")
            chat.add_status(f"   Isolation: {'Enabled' if workspace_config.isolation else 'Disabled'}")
            chat.add_status("=" * 60)

            self.session_active = True

        # Update status (use 'healthy' not 'working')
        status.update_status("Processing...", "healthy")
        progress.start_task("Analyzing task...")

        # Track file operations for summary
        files_created = []
        files_modified = []
        files_deleted = []
        files_seen = set()  # Track which files we've seen in this session
        file_contents = {}  # Track file contents for diff display {file_path: content}
        start_time = time.time()

        try:
            # Get backend bridge (already initialized if first message)
            bridge = get_bridge()

            # Execute task with progress streaming (use session workspace)
            async for update in bridge.execute_task(
                message,
                workspace=self.session_workspace
            ):
                if update.type == "status":
                    # Update progress bar
                    progress.update_progress(
                        advance=10,
                        description=update.message
                    )
                    log.add_log("info", update.message)

                    # Show step header for execute nodes
                    if update.data and "node" in update.data:
                        node = update.data.get("node")
                        iteration = update.data.get("iteration", 0)
                        max_iter = update.data.get("max_iterations")

                        if node == "execute" and isinstance(max_iter, int) and isinstance(iteration, int):
                            chat.add_step_header(
                                step_num=iteration if iteration > 0 else 1,
                                total_steps=max_iter,
                                description="Executing tools and operations",
                                status="in_progress",
                            )
                        elif node == "plan":
                            chat.add_status("🎯 Planning execution strategy...")
                        elif node == "reflect":
                            chat.add_status("💭 Reviewing results...")
                    else:
                        # Regular status message
                        chat.add_status(update.message)

                elif update.type == "llm_response":
                    # Display LLM response with more detail
                    response_preview = update.data.get("response_preview", "")
                    if response_preview:
                        # Show more of the response (300 chars instead of 150)
                        preview_text = response_preview[:300]
                        if len(response_preview) > 300:
                            preview_text += "..."
                        chat.add_status(f"🤖 AI Response: {preview_text}")
                        log.add_log("debug", f"LLM Full Response: {response_preview}")

                    # Display thinking if available (CoT)
                    thinking = update.data.get("thinking", "")
                    if thinking:
                        cot_viewer.add_thinking(thinking, update.data.get("iteration", 0))

                elif update.type == "action_decided":
                    # ✅ NEW: Display action decided by LLM
                    action = update.data.get("action", "UNKNOWN")
                    iteration = update.data.get("iteration", 0)
                    chat.add_status(f"💡 Decision [{iteration}]: {action}")
                    log.add_log("info", f"Action decided: {action}")

                elif update.type == "tool_executed":
                    # Display tool execution details with full error information
                    tool = update.data.get("tool", "UNKNOWN")
                    params = update.data.get("params", {})  # Now contains actual parameters directly from workflow
                    success = update.data.get("success", False)
                    result = update.data.get("result", {})
                    error = update.data.get("error")
                    iteration = update.data.get("iteration", 0)

                    # DEBUG: Log the full event data for troubleshooting (INFO level so it's visible)
                    log.add_log("info", f"[TOOL EVENT] {tool} - success={success}, iteration={iteration}")
                    log.add_log("info", f"  params keys: {list(params.keys())}")
                    log.add_log("info", f"  result keys: {list(result.keys())}")

                    # For WRITE_FILE, log content availability
                    if tool == "WRITE_FILE":
                        has_content = 'content' in params
                        content_len = len(params.get('content', ''))
                        log.add_log("info", f"  WRITE_FILE has_content={has_content}, content_len={content_len}")

                    # Format parameters for display
                    param_str = ""
                    if tool == "READ_FILE":
                        param_str = f"({params.get('file_path', 'N/A')})"
                    elif tool == "WRITE_FILE":
                        file_path = params.get('file_path', 'N/A')
                        param_str = f"({file_path})"
                    elif tool == "RUN_COMMAND":
                        param_str = f"('{params.get('command', 'N/A')}')"
                    elif tool == "LIST_DIRECTORY":
                        param_str = f"({params.get('path', '.')})"
                    elif tool == "SEARCH_FILES":
                        param_str = f"(pattern: '{params.get('pattern', '*')}')"
                    elif tool == "GIT_STATUS":
                        param_str = ""

                    status_icon = "✅" if success else "❌"

                    # Show tool execution in Chat with more detail
                    chat.add_status(f"🔧 Tool [{iteration}]: {tool}{param_str} {status_icon}")
                    log.add_log("info", f"Tool: {tool} - {'Success' if success else 'Failed'}")

                    # Show result message if available (includes actual file path for WRITE_FILE)
                    result_message = result.get("message", "")
                    if result_message and success:
                        log.add_log("debug", f"   Result: {result_message}")

                    # Show file content for WRITE_FILE using new method
                    if tool == "WRITE_FILE" and success:
                        file_path = params.get('file_path', '')
                        content = params.get('content', '')

                        # Get absolute path and metadata from result
                        # FileSystemTools.write_file returns metadata with absolute path
                        metadata = result.get('metadata', {})
                        absolute_path = metadata.get('path', file_path)
                        file_bytes = metadata.get('bytes', len(content.encode('utf-8')) if content else 0)
                        file_lines = metadata.get('lines', len(content.splitlines()) if content else 0)

                        # Log what we found (INFO level for visibility)
                        log.add_log("info", f"  📝 WRITE_FILE Details:")
                        log.add_log("info", f"    file_path: {file_path}")
                        log.add_log("info", f"    absolute_path: {absolute_path}")
                        log.add_log("info", f"    content_length: {len(content) if content else 0} chars")
                        log.add_log("info", f"    metadata: bytes={file_bytes}, lines={file_lines}")

                        if content and file_path:
                            log.add_log("info", f"  ✅ Content available - proceeding to display")

                            # Determine if file is new or modified
                            from pathlib import Path
                            old_content = file_contents.get(file_path)  # Get previous content if any

                            if old_content is not None:
                                # File was previously read or written - show DIFF
                                status_type = "MODIFIED"
                                files_seen.add(file_path)

                                # Track file operation
                                if file_path not in files_modified:
                                    files_modified.append(file_path)

                                # Show absolute path
                                chat.add_status(f"   📁 Full path: {absolute_path}")

                                log.add_log("info", f"  🎨 Showing DIFF (file was previously tracked)...")

                                # Display DIFF instead of full content
                                try:
                                    chat.add_file_diff(
                                        file_path=file_path,
                                        old_content=old_content,
                                        new_content=content,
                                        context_lines=3,
                                    )
                                    log.add_log("info", f"  ✅ Diff displayed: {file_path}")
                                except Exception as e:
                                    import traceback
                                    log.add_log("error", f"  ❌ Failed to display diff: {e}")
                                    log.add_log("error", f"  ❌ Traceback: {traceback.format_exc()}")
                                    chat.add_status(f"   ❌ Error displaying diff: {str(e)}")

                                # Update stored content
                                file_contents[file_path] = content

                            else:
                                # New file - show full content
                                if file_path in files_seen:
                                    status_type = "MODIFIED"
                                else:
                                    status_type = "NEW"
                                    files_seen.add(file_path)

                                # Track file operation (avoid duplicates)
                                if status_type == "NEW" and file_path not in files_created:
                                    files_created.append(file_path)
                                elif status_type == "MODIFIED" and file_path not in files_modified:
                                    files_modified.append(file_path)

                                # Show absolute path in chat status for user clarity
                                chat.add_status(f"   📁 Full path: {absolute_path}")

                                log.add_log("info", f"  🎨 Calling chat.add_file_content()...")

                                # Display with new method (full content with line numbers)
                                try:
                                    chat.add_file_content(
                                        file_path=file_path,  # Use relative path for cleaner display
                                        content=content,
                                        status=status_type,
                                        display_mode="full",  # Show full content
                                    )
                                    log.add_log("info", f"  ✅ chat.add_file_content() completed successfully")
                                    log.add_log("info", f"  ✅ File displayed: {file_path} ({file_bytes} bytes, {file_lines} lines)")
                                except Exception as e:
                                    import traceback
                                    log.add_log("error", f"  ❌ chat.add_file_content() failed: {e}")
                                    log.add_log("error", f"  ❌ Traceback: {traceback.format_exc()}")
                                    chat.add_status(f"   ❌ Error displaying file: {str(e)}")

                                # Store content for future diff comparisons
                                file_contents[file_path] = content
                                log.add_log("info", f"  💾 Stored file content for future diff tracking")
                        else:
                            # WARNING: No content found
                            log.add_log("error", f"  ❌ WRITE_FILE: No content to display!")
                            log.add_log("error", f"    file_path={file_path!r}")
                            log.add_log("error", f"    has_content={bool(content)}")
                            log.add_log("error", f"    content_len={len(content) if content else 0}")

                            chat.add_status(f"   ❌ ERROR: File written but no content available")
                            chat.add_status(f"   📁 Location: {absolute_path}")
                            chat.add_status(f"   ⚠️  BUG: Content not captured from workflow")

                    # Show file content for READ_FILE using new method
                    elif tool == "READ_FILE" and success:
                        file_path = params.get('file_path', '')
                        content = result.get("output", "")

                        log.add_log("info", f"  📖 READ_FILE Details:")
                        log.add_log("info", f"    file_path: {file_path}")
                        log.add_log("info", f"    content_length: {len(content) if content else 0} chars")

                        if content and file_path:
                            # Store content for future diff comparison
                            file_contents[file_path] = content
                            log.add_log("info", f"  💾 Stored file content for diff tracking")

                            log.add_log("info", f"  🎨 Displaying file preview in chat...")
                            # Show preview (first 10 lines) for READ_FILE
                            try:
                                chat.add_file_content(
                                    file_path=file_path,
                                    content=content,
                                    status="EXISTING",  # Existing file being read
                                    display_mode="preview",  # Preview mode (first 10 lines)
                                )
                                log.add_log("info", f"  ✅ File preview displayed: {file_path}")
                            except Exception as e:
                                import traceback
                                log.add_log("error", f"  ❌ Failed to display preview: {e}")
                                log.add_log("error", f"  ❌ Traceback: {traceback.format_exc()}")

                    # Show directory listing as file browser
                    elif tool == "LIST_DIRECTORY" and success:
                        dir_path = params.get('path', '.')
                        output = result.get("output", [])  # List of dicts, not string!

                        log.add_log("info", f"  📂 LIST_DIRECTORY Details:")
                        log.add_log("info", f"    dir_path: {dir_path}")
                        log.add_log("info", f"    output_type: {type(output)}")
                        log.add_log("info", f"    output_length: {len(output) if output else 0} entries")

                        if output and isinstance(output, list):
                            log.add_log("info", f"  🎨 Displaying file browser...")
                            try:
                                from rich.text import Text
                                from rich.panel import Panel
                                from rich.table import Table

                                # Categorize entries
                                dirs = []
                                files = []

                                for entry in output:
                                    # entry is dict: {"name": "foo.py", "type": "file", "size": 123, "path": "foo.py"}
                                    if isinstance(entry, dict):
                                        name = entry.get("name", "")
                                        entry_type = entry.get("type", "file")
                                        size = entry.get("size")

                                        if entry_type == "directory":
                                            dirs.append((name, size))
                                        else:
                                            files.append((name, size))

                                # Create table for better display
                                table = Table(
                                    show_header=True,
                                    header_style="bold cyan",
                                    border_style="cyan",
                                    show_lines=False,
                                    pad_edge=False,
                                )

                                table.add_column("Type", width=6)
                                table.add_column("Name", style="green")
                                table.add_column("Size", justify="right", width=12)

                                # Add directories first
                                for name, size in sorted(dirs):
                                    table.add_row("📁 DIR", name + "/", "")

                                # Add files
                                for name, size in sorted(files):
                                    # Detect file type by extension
                                    if name.endswith('.py'):
                                        icon = "🐍"
                                    elif name.endswith(('.js', '.ts', '.jsx', '.tsx')):
                                        icon = "📜"
                                    elif name.endswith(('.json', '.yaml', '.yml')):
                                        icon = "⚙️"
                                    elif name.endswith(('.md', '.txt')):
                                        icon = "📝"
                                    elif name.endswith(('.jpg', '.png', '.gif', '.svg')):
                                        icon = "🖼️"
                                    else:
                                        icon = "📄"

                                    # Format size
                                    size_str = ""
                                    if size is not None:
                                        if size < 1024:
                                            size_str = f"{size}B"
                                        elif size < 1024 * 1024:
                                            size_str = f"{size/1024:.1f}KB"
                                        else:
                                            size_str = f"{size/(1024*1024):.1f}MB"

                                    table.add_row(f"{icon} FILE", name, size_str)

                                # Show in panel
                                browser_panel = Panel(
                                    table,
                                    title=f"📂 {dir_path} ({len(dirs)} dirs, {len(files)} files)",
                                    title_align="left",
                                    border_style="cyan",
                                    padding=(0, 1),
                                )

                                chat.write(browser_panel)

                                log.add_log("info", f"  ✅ File browser displayed: {len(dirs)} dirs, {len(files)} files")
                            except Exception as e:
                                import traceback
                                log.add_log("error", f"  ❌ Failed to display file browser: {e}")
                                log.add_log("error", f"  ❌ Traceback: {traceback.format_exc()}")
                                # Show what we received for debugging
                                log.add_log("error", f"  ❌ Output type: {type(output)}")
                                log.add_log("error", f"  ❌ Output: {output[:3] if len(output) > 3 else output}")

                    # Show detailed error if failed
                    if not success:
                        error_detail = error or result.get("error", "Unknown error")
                        # Show full error in Chat for debugging
                        chat.add_status(f"   ❌ ERROR: {error_detail}")
                        log.add_log("error", f"Tool failure detail: {error_detail}")

                elif update.type == "plan_created":
                    # Display plan summary
                    plan = update.data.get("plan", {})
                    complexity = update.data.get("complexity", "medium")
                    if plan:
                        chat.add_plan_summary(plan=plan, task_complexity=complexity)
                    log.add_log("info", f"Plan created: {complexity} complexity")

                elif update.type == "cot":
                    # Display Chain-of-Thought
                    step = update.data.get("step", 0)
                    cot_viewer.add_thinking(update.message, step)

                elif update.type == "log":
                    # Display log message
                    level = update.data.get("level", "info")
                    log.add_log(level, update.message)
                    # Show important logs in chat too
                    if level in ["warning", "error"]:
                        chat.add_status(f"⚠️ {update.message}")

                elif update.type == "result":
                    # Display final result
                    duration = time.time() - start_time
                    iterations = update.data.get('iterations', 0)
                    metadata = update.data.get('metadata', {})
                    tool_calls_list = metadata.get('tool_calls', [])

                    if update.data["success"]:
                        output = update.data.get("output", "")

                        # Show output if present
                        if output and str(output).strip():
                            chat.add_message_smart("assistant", str(output))

                        # Show task summary with file operations
                        chat.add_task_summary(
                            duration=duration,
                            files_created=files_created,
                            files_modified=files_modified,
                            files_deleted=files_deleted,
                            tool_calls=len(tool_calls_list),
                            iterations=iterations,
                        )

                        progress.complete_task("✅ Task completed")
                        log.add_log(
                            "info",
                            f"Task completed in {iterations} iterations ({duration:.1f}s)"
                        )
                    else:
                        error = update.data.get("error", "Unknown error")
                        chat.add_message("system", f"Error: {error}")
                        progress.fail_task(f"❌ Task failed: {error}")
                        log.add_log("error", f"Task failed: {error}")

            # Reset status
            status.update_status("Ready", "healthy")

        except Exception as e:
            # Error handling
            chat.add_message("system", f"Error: {str(e)}")
            log.add_log("error", f"Error processing message: {e}")
            status.update_status("Error", "error")
            progress.fail_task(str(e))

    def action_clear_chat(self) -> None:
        """Clear chat history"""
        chat = self.query_one("#chat-panel", ChatPanel)
        chat.clear()
        self.notify("Chat cleared")

    def action_toggle_cot(self) -> None:
        """Toggle Chain-of-Thought display"""
        self.cot_visible = not self.cot_visible
        # TODO: Implement dynamic panel toggling
        self.notify(
            f"CoT display {'enabled' if self.cot_visible else 'disabled'}"
        )

    def action_save_session(self) -> None:
        """Save current session (local only)"""
        try:
            session_path = Path("./data/sessions")
            session_path.mkdir(parents=True, exist_ok=True)

            # Save history
            self.history.save()

            self.notify("✅ Session saved locally")

            log = self.query_one("#log-viewer", LogViewer)
            log.add_log("info", "Session saved")

        except Exception as e:
            self.notify(f"❌ Failed to save session: {e}", severity="error")


def run_cli():
    """Run the Agentic CLI application"""
    app = AgenticApp()
    app.run()


if __name__ == "__main__":
    run_cli()

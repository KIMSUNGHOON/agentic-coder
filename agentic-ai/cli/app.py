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
        from .backend_bridge import get_bridge, ProgressUpdate

        # Get UI components
        status = self.query_one("#status-bar", StatusBar)
        progress = self.query_one("#progress-display", ProgressDisplay)
        chat = self.query_one("#chat-panel", ChatPanel)
        log = self.query_one("#log-viewer", LogViewer)
        cot_viewer = self.query_one("#cot-viewer", CoTViewer)

        # Generate session ID on first message
        if not self.session_id:
            self.session_id = str(uuid.uuid4())
            status.set_session(self.session_id)
            log.add_log("info", f"Session created: {self.session_id[:8]}")
            self.session_active = True

        # Update status (use 'healthy' not 'working')
        status.update_status("Processing...", "healthy")
        progress.start_task("Analyzing task...")

        try:
            # Get backend bridge
            bridge = get_bridge()

            # Execute task with progress streaming
            async for update in bridge.execute_task(message):
                if update.type == "status":
                    # Update progress bar
                    progress.update_progress(
                        advance=10,
                        description=update.message
                    )
                    log.add_log("info", update.message)
                    # ✅ NEW: Also show in chat for visibility
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
                    params = update.data.get("params", {})
                    success = update.data.get("success", False)
                    result = update.data.get("result", {})
                    error = update.data.get("error")
                    iteration = update.data.get("iteration", 0)

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

                    # Show tool execution in Chat
                    chat.add_status(f"🔧 Tool [{iteration}]: {tool}{param_str} {status_icon}")
                    log.add_log("info", f"Tool: {tool} - {'Success' if success else 'Failed'}")

                    # Show file content for WRITE_FILE
                    if tool == "WRITE_FILE" and success:
                        file_path = params.get('file_path', '')
                        content = params.get('content', '')
                        if content:
                            # Show content preview in chat
                            preview_lines = content.split('\n')[:10]  # First 10 lines
                            preview = '\n'.join(preview_lines)
                            if len(content.split('\n')) > 10:
                                preview += "\n..."

                            chat.add_status(f"   📄 Created: {file_path}")
                            chat.add_status(f"   📝 Content ({len(content)} chars):")
                            # Show actual code content
                            chat.add_message_smart("assistant", f"```python\n{preview}\n```")

                    # Show detailed error if failed
                    if not success:
                        error_detail = error or result.get("error", "Unknown error")
                        # Show full error in Chat for debugging
                        chat.add_status(f"   ❌ ERROR: {error_detail}")
                        log.add_log("error", f"Tool failure detail: {error_detail}")

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
                    if update.data["success"]:
                        output = update.data.get("output", "")
                        # ✅ NEW: Use smart formatting (auto-detects markdown/code)
                        chat.add_message_smart("assistant", str(output))
                        progress.complete_task("✅ Task completed")
                        log.add_log(
                            "info",
                            f"Task completed in {update.data.get('iterations', 0)} iterations"
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

"""Remote CLI Client for Agentic Coder

Standalone executable that connects to a remote Agentic Coder server.
Can be distributed as a binary (via PyInstaller) for easy deployment.

Usage:
    python remote_client.py
    # Or as binary: ./agentic-coder-client
"""

import asyncio
import sys
from typing import Optional
from pathlib import Path

try:
    from rich.console import Console
    from rich.prompt import Prompt, Confirm
    from rich.panel import Panel
    from rich.table import Table
    from rich.markdown import Markdown
    from rich.progress import Progress, SpinnerColumn, TextColumn
    RICH_AVAILABLE = True
except ImportError:
    print("Error: 'rich' package is required. Install with: pip install rich")
    sys.exit(1)

try:
    import httpx
except ImportError:
    print("Error: 'httpx' package is required. Install with: pip install httpx")
    sys.exit(1)


class RemoteClient:
    """Client for connecting to remote Agentic Coder server"""

    def __init__(self, server_url: str):
        """Initialize remote client

        Args:
            server_url: Full URL of server (e.g., http://192.168.1.100:8000)
        """
        self.server_url = server_url.rstrip('/')
        self.console = Console()
        self.session_id: Optional[str] = None
        self.client = httpx.AsyncClient(timeout=300.0)

    async def health_check(self) -> bool:
        """Check if server is reachable and healthy

        Returns:
            True if server is healthy, False otherwise
        """
        try:
            response = await self.client.get(f"{self.server_url}/health")
            if response.status_code == 200:
                data = response.json()
                self.console.print(f"[green]✓[/green] Server is healthy")
                self.console.print(f"[dim]Version: {data.get('version', 'unknown')}[/dim]")
                self.console.print(f"[dim]Model: {data.get('model', 'unknown')}[/dim]")
                return True
            else:
                self.console.print(f"[red]✗[/red] Server returned status {response.status_code}")
                return False
        except httpx.ConnectError:
            self.console.print(f"[red]✗[/red] Cannot connect to server at {self.server_url}")
            self.console.print(f"[dim]Make sure the server is running and accessible[/dim]")
            return False
        except Exception as e:
            self.console.print(f"[red]✗[/red] Health check failed: {e}")
            return False

    async def create_session(self, workspace: Optional[str] = None) -> bool:
        """Create a new remote session

        Args:
            workspace: Optional workspace path

        Returns:
            True if session created successfully
        """
        try:
            payload = {}
            if workspace:
                payload["workspace"] = workspace

            response = await self.client.post(
                f"{self.server_url}/api/sessions",
                json=payload
            )

            if response.status_code == 200:
                data = response.json()
                self.session_id = data.get("session_id")
                workspace_path = data.get("workspace", "unknown")

                self.console.print(f"[green]✓[/green] Session created: {self.session_id[:8]}...")
                self.console.print(f"[dim]Workspace: {workspace_path}[/dim]")
                return True
            else:
                self.console.print(f"[red]✗[/red] Failed to create session: {response.text}")
                return False

        except Exception as e:
            self.console.print(f"[red]✗[/red] Session creation failed: {e}")
            return False

    async def execute_request(self, user_request: str):
        """Execute a user request on remote server

        Args:
            user_request: User's request
        """
        if not self.session_id:
            self.console.print("[red]✗[/red] No active session. Please reconnect.")
            return

        try:
            # Show request panel
            self.console.print()
            self.console.print(Panel(
                f"[bold white]{user_request}[/bold white]",
                title="[bold cyan]🎯 Your Request[/bold cyan]",
                border_style="cyan",
                padding=(1, 2)
            ))

            # Stream response using SSE (Server-Sent Events)
            async with self.client.stream(
                "POST",
                f"{self.server_url}/api/sessions/{self.session_id}/execute",
                json={"request": user_request},
                timeout=None
            ) as response:
                if response.status_code != 200:
                    error_text = await response.aread()
                    self.console.print(f"[red]✗[/red] Request failed: {error_text.decode()}")
                    return

                # Parse SSE stream
                current_status = "Processing..."
                with Progress(
                    SpinnerColumn(),
                    TextColumn("[progress.description]{task.description}"),
                    console=self.console
                ) as progress:
                    task = progress.add_task(current_status, total=None)

                    async for line in response.aiter_lines():
                        if not line or not line.startswith("data: "):
                            continue

                        data_str = line[6:]  # Remove "data: " prefix
                        if data_str == "[DONE]":
                            break

                        try:
                            import json
                            update = json.loads(data_str)
                            update_type = update.get("type")

                            if update_type == "status":
                                status = update.get("message", "Processing...")
                                progress.update(task, description=status)

                            elif update_type == "reasoning":
                                reasoning = update.get("content", "")
                                if reasoning:
                                    progress.stop()
                                    self.console.print(Panel(
                                        f"[italic dim]{reasoning[:500]}[/italic dim]",
                                        title="[bold cyan]💭 AI Reasoning[/bold cyan]",
                                        border_style="cyan"
                                    ))
                                    progress.start()

                            elif update_type == "tool_result":
                                tool = update.get("tool", "unknown")
                                success = update.get("success", False)
                                if success:
                                    progress.stop()
                                    self.console.print(f"[green]✓[/green] {tool} completed")
                                    progress.start()
                                else:
                                    error = update.get("error", "Unknown error")
                                    progress.stop()
                                    self.console.print(f"[red]✗[/red] {tool} failed: {error}")
                                    progress.start()

                            elif update_type == "final_response":
                                response_text = update.get("content", "")
                                progress.stop()
                                self.console.print()
                                self.console.print(Panel(
                                    Markdown(response_text),
                                    title="[bold green]✅ Complete[/bold green]",
                                    border_style="green",
                                    padding=(1, 2)
                                ))

                            elif update_type == "error":
                                error_msg = update.get("message", "Unknown error")
                                progress.stop()
                                self.console.print(Panel(
                                    f"[red]{error_msg}[/red]",
                                    title="[bold red]❌ Error[/bold red]",
                                    border_style="red"
                                ))

                        except json.JSONDecodeError:
                            continue

        except Exception as e:
            self.console.print(f"[red]✗[/red] Request execution failed: {e}")

    async def interactive_mode(self):
        """Start interactive REPL mode"""
        self.console.print(Panel(
            "[bold cyan]Agentic Coder Remote Client[/bold cyan]\n\n"
            f"[dim]Connected to:[/dim] {self.server_url}\n"
            f"[dim]Session:[/dim] {self.session_id[:8] if self.session_id else 'None'}...\n\n"
            "Type your request or use commands:\n"
            "  [cyan]/help[/cyan] - Show help\n"
            "  [cyan]/exit[/cyan] - Exit client",
            border_style="cyan",
            padding=(1, 2)
        ))

        while True:
            try:
                user_input = Prompt.ask("\n[bold cyan]>[/bold cyan]", console=self.console)

                if not user_input.strip():
                    continue

                if user_input.strip() in ["/exit", "/quit"]:
                    self.console.print("\n[cyan]Goodbye![/cyan]")
                    break

                if user_input.strip() == "/help":
                    self._show_help()
                    continue

                # Execute request
                await self.execute_request(user_input)

            except KeyboardInterrupt:
                self.console.print("\n[yellow]Use /exit to quit[/yellow]")
                continue
            except EOFError:
                self.console.print("\n[cyan]Goodbye![/cyan]")
                break

    def _show_help(self):
        """Show help message"""
        help_text = """
# Remote Client Commands

- `/help` - Show this help message
- `/exit` or `/quit` - Exit the client

## Examples

```
Create a simple calculator in Python
Fix the bug in my code
Add unit tests for calculator.py
```
        """
        self.console.print(Markdown(help_text))

    async def close(self):
        """Clean up resources"""
        await self.client.aclose()


async def main():
    """Main entry point for remote client"""
    console = Console()

    # Show banner
    console.print(Panel(
        "[bold cyan]Agentic Coder - Remote Client[/bold cyan]\n"
        "[dim]Connect to a remote Agentic Coder server[/dim]",
        border_style="cyan",
        padding=(1, 2)
    ))

    # Prompt for server connection details
    console.print("\n[bold]Server Connection[/bold]")

    # Check for command line arguments
    if len(sys.argv) >= 2:
        server_host = sys.argv[1]
        server_port = sys.argv[2] if len(sys.argv) >= 3 else "8000"
    else:
        # Interactive prompts
        server_host = Prompt.ask(
            "Server IP/Hostname",
            default="localhost",
            console=console
        )
        server_port = Prompt.ask(
            "Server Port",
            default="8000",
            console=console
        )

    # Build server URL
    if not server_host.startswith("http"):
        server_url = f"http://{server_host}:{server_port}"
    else:
        server_url = f"{server_host}:{server_port}"

    console.print(f"\n[dim]Connecting to {server_url}...[/dim]")

    # Create client and perform health check
    client = RemoteClient(server_url)

    with Progress(
        SpinnerColumn(),
        TextColumn("[progress.description]{task.description}"),
        console=console
    ) as progress:
        task = progress.add_task("Checking server health...", total=None)

        if not await client.health_check():
            console.print("\n[red]✗ Cannot connect to server[/red]")
            console.print("[dim]Please check:[/dim]")
            console.print("  1. Server is running")
            console.print("  2. IP/Port is correct")
            console.print("  3. Firewall allows connection")
            return

        progress.update(task, description="Creating session...")
        if not await client.create_session():
            console.print("\n[red]✗ Failed to create session[/red]")
            return

    # Start interactive mode
    try:
        await client.interactive_mode()
    finally:
        await client.close()


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        print("\n\nInterrupted by user")
        sys.exit(0)

# Agentic 2.0 CLI Interface

Interactive command-line interface for Agentic 2.0 with Textual-based TUI and backend integration.

## Features

- **Interactive Chat Mode**: Rich terminal UI with real-time conversation
- **Progress Visualization**: Live progress bars and status updates
- **Chain-of-Thought Display**: View GPT-OSS-120B reasoning process
- **Local-Only Storage**: All data stored securely on local filesystem
- **Backend Integration**: Full integration with workflow orchestrator
- **Security Enforcement**: Input validation and command safety checks

## Installation

```bash
# Install dependencies
pip install -r requirements.txt
```

## Usage

### Interactive Chat Mode

```bash
# Start interactive chat interface
agentic chat
```

Features:
- Real-time conversation with AI
- Progress visualization
- Chain-of-Thought viewer
- Log viewer
- Keyboard shortcuts (Ctrl+C to quit, Ctrl+L to clear chat)

### Direct Task Execution

```bash
# Run task directly (non-interactive)
agentic run "Write unit tests for auth.py"

# Specify workflow type
agentic run "Research best practices" --workflow research

# Custom workspace
agentic run "Analyze data.csv" --workspace ./my-workspace
```

### System Status

```bash
# Check system status
agentic status
```

Shows:
- LLM endpoint health
- Local storage usage
- Security status
- Orchestrator statistics

### Command History

```bash
# View recent commands
agentic history

# View last 50 commands
agentic history --limit 50

# Search history
agentic history --search "unit test"
```

### Health Checks

```bash
# Run health checks
agentic health
```

### Configuration

```bash
# Show current configuration
agentic config
```

### Clear Data

```bash
# Clear local data (requires confirmation)
agentic clear --confirm
```

## Architecture

### Components

```
cli/
├── app.py              # Main Textual application
├── commands.py         # Click-based CLI commands
├── backend_bridge.py   # Backend integration layer
├── components/         # UI components
│   ├── chat_panel.py
│   ├── progress_bar.py
│   ├── log_viewer.py
│   ├── status_bar.py
│   └── cot_viewer.py
└── utils/              # Utilities
    ├── formatter.py
    ├── history.py
    └── security.py
```

### Backend Integration

The CLI integrates with the backend through `BackendBridge`:

```python
from cli.backend_bridge import get_bridge

# Get singleton bridge instance
bridge = get_bridge()

# Execute task with progress streaming
async for update in bridge.execute_task("Fix authentication bug"):
    if update.type == "status":
        print(update.message)
    elif update.type == "cot":
        print(f"Thinking: {update.message}")
    elif update.type == "result":
        print(f"Result: {update.data}")
```

### Progress Updates

The backend bridge yields progress updates:

- `status`: Status messages (initializing, classifying, etc.)
- `cot`: Chain-of-Thought reasoning blocks
- `log`: Log messages
- `result`: Final result (success/failure)

### Chain-of-Thought Parsing

GPT-OSS-120B uses `<think>...</think>` tags for reasoning:

```python
response = """
<think>
First, I need to analyze the problem.
This requires careful consideration.
</think>

The answer is 42.
"""

# CoT blocks are automatically extracted and displayed
```

## Security

All CLI operations enforce security policies:

- **Input Validation**: Blocks external URLs, dangerous patterns
- **Local-Only Data**: No external data transmission
- **Command Safety**: Allowlist/denylist enforcement
- **Path Traversal Prevention**: Restricted filesystem access
- **Audit Logging**: All operations logged locally

## Configuration

CLI uses the main `config/config.yaml`:

```yaml
# LLM Configuration
llm:
  model_name: gpt-oss-120b
  endpoints:
    - url: http://localhost:8001/v1
      name: primary

# Security (local-only)
tools:
  safety:
    enabled: true
    command_allowlist: [python, git, npm]
    command_denylist: ["rm -rf /", "dd if="]
```

## Testing

Run integration tests:

```bash
python3 test_cli_integration.py
```

Tests:
1. Backend initialization
2. Chain-of-Thought parsing
3. Task execution (requires vLLM running)

## Development

### Adding New Commands

1. Add command in `commands.py`:

```python
@cli.command()
@click.argument("param")
def my_command(param):
    """My new command"""
    console.print(f"Running: {param}")
```

2. Integrate with backend if needed:

```python
from .backend_bridge import get_bridge

async def execute():
    bridge = get_bridge()
    async for update in bridge.execute_task(param):
        # Handle updates
        pass

asyncio.run(execute())
```

### Adding UI Components

1. Create component in `components/`:

```python
from textual.widgets import Static

class MyComponent(Static):
    def __init__(self):
        super().__init__()

    def update_display(self, data):
        # Update component
        pass
```

2. Add to layout in `app.py`:

```python
def compose(self) -> ComposeResult:
    # ... existing components
    yield MyComponent(id="my-component")
```

## Keyboard Shortcuts

- `Ctrl+C`: Quit application
- `Ctrl+L`: Clear chat history
- `Ctrl+H`: Toggle Chain-of-Thought display
- `Ctrl+S`: Save session

## Troubleshooting

### Backend Connection Issues

```bash
# Check if vLLM is running
curl http://localhost:8001/v1/models

# Check system status
agentic status
```

### Configuration Errors

```bash
# Verify config is valid
python3 -c "from core.config_loader import load_config; load_config('config/config.yaml')"
```

### Import Errors

```bash
# Install dependencies
pip install -r requirements.txt

# Verify imports
python3 -c "from cli import AgenticApp; print('OK')"
```

## License

Part of Agentic 2.0 project.

## Related Documentation

- [Security Guide](../docs/SECURITY.md)
- [Implementation Plan](../docs/IMPLEMENTATION_PLAN.md)
- [Backend Architecture](../docs/ARCHITECTURE.md)

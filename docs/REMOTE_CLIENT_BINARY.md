# Remote CLI Client - Deployment Binary

## 📋 Overview

The Remote CLI Client is a standalone executable that allows users to connect to an Agentic Coder server from any machine without installing Python or dependencies.

## 🎯 Features

- **Zero Installation**: No Python, no pip, no dependencies required
- **Cross-Platform**: Builds for Linux, macOS, and Windows
- **Health Check**: Automatic server availability verification
- **Interactive Mode**: Full REPL experience like local CLI
- **Session Management**: Automatic session creation and maintenance
- **Real-time Streaming**: SSE-based progress updates

## 🔧 Building the Binary

### Prerequisites

- Python 3.8+ (only for building, not for distribution)
- PyInstaller: `pip install pyinstaller`

### Build Commands

**Linux/macOS:**
```bash
cd scripts
chmod +x build_remote_client.sh
./build_remote_client.sh
```

**Windows:**
```cmd
cd scripts
build_remote_client.bat
```

### Build Output

- **Linux**: `dist/agentic-coder-client`
- **macOS**: `dist/agentic-coder-client`
- **Windows**: `dist/agentic-coder-client.exe`

**File Size**: Approximately 15-20 MB (includes Python runtime and dependencies)

## 📤 Distribution

### Option 1: Direct Copy

```bash
# Copy to remote machine
scp dist/agentic-coder-client user@192.168.1.100:~/

# On remote machine
chmod +x agentic-coder-client
./agentic-coder-client
```

### Option 2: Download from Release

```bash
# From GitHub Releases (example)
wget https://github.com/your-repo/releases/download/v1.0/agentic-coder-client-linux
chmod +x agentic-coder-client-linux
./agentic-coder-client-linux
```

### Option 3: Internal File Share

- Place binary on shared drive
- Users copy and execute directly

## 🚀 Usage

### Interactive Mode (Recommended)

```bash
./agentic-coder-client
```

The client will prompt for:
1. **Server IP/Hostname**: e.g., `192.168.1.100` or `ai-server.local`
2. **Server Port**: e.g., `8000` (default)

### Command Line Mode

```bash
# Specify server details as arguments
./agentic-coder-client 192.168.1.100 8000

# Or with full URL
./agentic-coder-client http://192.168.1.100:8000
```

### Example Session

```
┌─────────────────────────────────────┐
│ Agentic Coder - Remote Client      │
│ Connect to a remote server          │
└─────────────────────────────────────┘

Server Connection
Server IP/Hostname [localhost]: 192.168.1.100
Server Port [8000]: 8000

Connecting to http://192.168.1.100:8000...
✓ Server is healthy
  Version: 1.0.0
  Model: openai/gpt-oss-120b

✓ Session created: abc12345...
  Workspace: /workspace/session-20260109-123456

┌─────────────────────────────────────┐
│ Agentic Coder Remote Client        │
│                                     │
│ Connected to: http://192.168.1...  │
│ Session: abc12345...                │
│                                     │
│ Type your request or use commands: │
│   /help - Show help                 │
│   /exit - Exit client               │
└─────────────────────────────────────┘

> Create a calculator in Python

┌─────────────────────────────────────┐
│ 🎯 Your Request                     │
│                                     │
│ Create a calculator in Python       │
└─────────────────────────────────────┘

⚙️  Working...
Progress: [████████████░░░░░░░░] 3/15
Status: 🧠 AI is thinking...

┌───────────────────────────────────────┐
│ 💭 AI Reasoning                       │
│                                       │
│ I need to create a simple calculator  │
│ with basic operations...              │
└───────────────────────────────────────┘

✓ write_file completed

┌────────────────────────────────────────┐
│ ✅ File Created                        │
│                                        │
│ /workspace/.../calculator.py           │
│ → 45 lines, 1,234 bytes                │
└────────────────────────────────────────┘

┌────────────────────────────────────────┐
│ ✅ Task Complete                       │
│                                        │
│ Created a calculator with add,         │
│ subtract, multiply, and divide.        │
└────────────────────────────────────────┘
```

## 🔌 Server Requirements

### API Endpoints Required

The server must implement these HTTP endpoints:

#### 1. Health Check
```
GET /health
Response: {
  "status": "healthy",
  "version": "1.0.0",
  "model": "openai/gpt-oss-120b"
}
```

#### 2. Create Session
```
POST /api/sessions
Body: {
  "workspace": "/optional/workspace/path"
}
Response: {
  "session_id": "abc123",
  "workspace": "/workspace/session-abc123"
}
```

#### 3. Execute Request (SSE Stream)
```
POST /api/sessions/{session_id}/execute
Body: {
  "request": "Create a calculator"
}
Response: text/event-stream

data: {"type": "status", "message": "Processing..."}
data: {"type": "reasoning", "content": "Planning the implementation..."}
data: {"type": "tool_result", "tool": "write_file", "success": true}
data: {"type": "final_response", "content": "Created calculator.py"}
data: [DONE]
```

### Enable Server API

The server implementation is in progress. Current workaround:

```python
# backend/main.py (FastAPI)
from fastapi import FastAPI
from fastapi.responses import StreamingResponse

app = FastAPI()

@app.get("/health")
async def health_check():
    return {
        "status": "healthy",
        "version": "1.0.0",
        "model": "openai/gpt-oss-120b"
    }

@app.post("/api/sessions")
async def create_session(request: dict):
    # Implementation needed
    pass

@app.post("/api/sessions/{session_id}/execute")
async def execute_request(session_id: str, request: dict):
    # Implementation needed
    # Return StreamingResponse with SSE
    pass
```

## 🛡️ Security Considerations

### Network Security

1. **Use HTTPS**: For production, enable TLS
   ```bash
   # Server with TLS
   uvicorn main:app --ssl-keyfile key.pem --ssl-certfile cert.pem
   ```

2. **Firewall Rules**: Allow only necessary ports
   ```bash
   # Allow port 8000 from specific subnet
   sudo ufw allow from 192.168.1.0/24 to any port 8000
   ```

3. **Authentication** (Future):
   - API keys
   - OAuth tokens
   - JWT authentication

### Client Security

- Binary is safe to distribute (read-only, no privileged operations)
- All data transmitted over network (use HTTPS)
- No local file system access beyond temporary files

## 🐛 Troubleshooting

### Connection Refused

**Symptom**: `Cannot connect to server`

**Solutions**:
1. Check server is running: `curl http://server-ip:8000/health`
2. Check firewall: `telnet server-ip 8000`
3. Verify IP/port are correct
4. Check server binding: Should bind to `0.0.0.0`, not `127.0.0.1`

### Health Check Fails

**Symptom**: `Server returned status 404`

**Solutions**:
1. Server API not implemented yet
2. Wrong endpoint path
3. Server version mismatch

### Session Creation Fails

**Symptom**: `Failed to create session`

**Solutions**:
1. Server workspace directory not writable
2. Disk space full
3. Permission denied

### Slow Response

**Symptom**: Long delays between updates

**Solutions**:
1. Check network latency: `ping server-ip`
2. Server overloaded (check server logs)
3. Model inference slow (check GPU usage)

## 📊 Performance

### Network Requirements

- **Bandwidth**: Minimal (<1 KB/s steady state, burst to 100 KB/s for large responses)
- **Latency**: <100ms recommended for interactive experience
- **Connection**: Stable TCP connection (SSE requires long-lived connection)

### Recommended Setup

**Small Team (1-5 users)**:
- Server: 1x GPU (RTX 4090 or H100)
- Network: Local LAN (1 Gbps)
- Concurrent sessions: 5

**Medium Team (5-20 users)**:
- Server: 2x GPUs with load balancing
- Network: Local LAN (1 Gbps)
- Concurrent sessions: 20

**Large Team (20+ users)**:
- Server: Multiple GPU servers with load balancer
- Network: 10 Gbps backbone
- Concurrent sessions: 50+

## 🔄 Updates

### Updating the Client

1. Build new version
2. Distribute updated binary
3. Users replace old binary

**Version Check**:
```bash
./agentic-coder-client --version
```

### Auto-Update (Future)

- Client checks for updates on startup
- Downloads new version if available
- Prompts user to restart

## 📝 Development Notes

### Building from Source

```bash
# Install dependencies
pip install rich httpx pyinstaller

# Test locally
python backend/cli/remote_client.py

# Build binary
./scripts/build_remote_client.sh
```

### Debugging

```bash
# Run with debug output
./agentic-coder-client --debug

# Check build dependencies
pyinstaller --version
python --version
```

### Custom Builds

**Include Additional Files**:
```bash
pyinstaller \
    --name agentic-coder-client \
    --onefile \
    --add-data "config.yaml:." \
    --add-data "assets/*:assets" \
    backend/cli/remote_client.py
```

**Optimize Size**:
```bash
pyinstaller \
    --name agentic-coder-client \
    --onefile \
    --strip \
    --exclude-module pytest \
    --exclude-module numpy \
    backend/cli/remote_client.py
```

## 🎓 Best Practices

1. **Server Setup**:
   - Use systemd service for auto-restart
   - Enable HTTPS for production
   - Configure firewall rules
   - Monitor server health

2. **Client Distribution**:
   - Version binaries (e.g., `client-v1.2.0`)
   - Provide checksums (SHA256)
   - Document known issues per version
   - Test on target platform before distribution

3. **Network**:
   - Use VPN for remote access
   - Implement rate limiting on server
   - Log all connections for audit
   - Set connection timeouts

4. **User Experience**:
   - Provide connection instructions
   - Include troubleshooting guide
   - Collect user feedback
   - Monitor error rates

## 🔗 Related Documentation

- [Remote CLI Design](./REMOTE_CLI_DESIGN.md) - Architecture and design decisions
- [vLLM Load Balancing](./VLLM_LOAD_BALANCING.md) - Server performance optimization
- [Server API Documentation](./SERVER_API.md) - Full API reference (coming soon)

# Agent Tools Phase 2/2.5/3 - Complete Documentation

**Version**: 3.0.0
**Date**: 2026-01-08
**Status**: Production Ready

---

## Overview

This document covers all features introduced in Agent Tools Phases 2, 2.5, 3, and 4:

- **Phase 2**: Network Mode System + Web Tools (HttpRequestTool, DownloadFileTool)
- **Phase 2.5**: Code Tools (FormatCodeTool, ShellCommandTool, DocstringGeneratorTool)
- **Phase 3**: Performance Optimization (Connection Pooling, Caching, Progress Tracking)
- **Phase 4**: Sandbox Execution (SandboxExecuteTool - Docker-based isolated code execution)

### Key Features

1. **Network Mode System** - Online/Offline mode control
2. **HttpRequestTool** - REST API calls with caching (EXTERNAL_API)
3. **DownloadFileTool** - File downloads with progress tracking (EXTERNAL_DOWNLOAD)
4. **FormatCodeTool** - Code formatting with Black/autopep8/yapf (LOCAL)
5. **ShellCommandTool** - Safe shell command execution (LOCAL)
6. **DocstringGeneratorTool** - Auto-generate docstrings (LOCAL)
7. **Connection Pooling** - Shared HTTP connections for efficiency
8. **Result Caching** - LRU cache with TTL for GET requests
9. **Progress Tracking** - Real-time download progress with callbacks

**Total Tools**: 20 (14 Phase 1 + 2 Phase 2 + 3 Phase 2.5 + 1 Phase 4)

---

## Network Mode System

### Concept

Network Mode allows administrators to control which tools can access external networks, critical for secure/air-gapped environments.

### Network Types

| Type | Description | Offline Mode |
|------|-------------|--------------|
| `LOCAL` | No network needed (file, git, code tools) | Allowed |
| `INTERNAL` | Internal network only | Allowed |
| `EXTERNAL_API` | External API calls (may leak data) | **Blocked** |
| `EXTERNAL_DOWNLOAD` | One-way file downloads | Allowed |

### Security Policy

```
Offline Mode Policy:
- BLOCK: Tools that send data externally (EXTERNAL_API)
- ALLOW: Tools that only receive data (EXTERNAL_DOWNLOAD)
- ALLOW: Tools that work locally (LOCAL)

Rationale: Prevent local data leakage while allowing file downloads
```

### Configuration

```bash
# .env
NETWORK_MODE=online   # All tools available
NETWORK_MODE=offline  # Block EXTERNAL_API tools only
```

### Tool Availability by Mode

| Tool | Network Type | Online | Offline | Phase |
|------|--------------|--------|---------|-------|
| read_file | LOCAL | Yes | Yes | 1 |
| write_file | LOCAL | Yes | Yes | 1 |
| search_files | LOCAL | Yes | Yes | 1 |
| list_directory | LOCAL | Yes | Yes | 1 |
| execute_python | LOCAL | Yes | Yes | 1 |
| run_tests | LOCAL | Yes | Yes | 1 |
| lint_code | LOCAL | Yes | Yes | 1 |
| git_status | LOCAL | Yes | Yes | 1 |
| git_diff | LOCAL | Yes | Yes | 1 |
| git_log | LOCAL | Yes | Yes | 1 |
| git_branch | LOCAL | Yes | Yes | 1 |
| git_commit | LOCAL | Yes | Yes | 1 |
| code_search | LOCAL | Yes | Yes | 1 |
| web_search | EXTERNAL_API | Yes | **No** | 1 |
| http_request | EXTERNAL_API | Yes | **No** | 2 |
| download_file | EXTERNAL_DOWNLOAD | Yes | Yes | 2 |
| format_code | LOCAL | Yes | Yes | 2.5 |
| shell_command | LOCAL | Yes | Yes | 2.5 |
| generate_docstring | LOCAL | Yes | Yes | 2.5 |
| sandbox_execute | LOCAL | Yes | Yes | 4 |

---

## New Tools

### 1. HttpRequestTool

Make HTTP requests to REST APIs.

**Network Type**: `EXTERNAL_API` (blocked in offline mode)

**Capabilities**:
- HTTP methods: GET, POST, PUT, DELETE, PATCH, HEAD, OPTIONS
- Custom headers support
- Request body for POST/PUT/PATCH
- Automatic JSON parsing
- Configurable timeout

**Example Usage**:
```python
from app.tools.registry import ToolRegistry

registry = ToolRegistry()
http_tool = registry.get_tool("http_request")

# GET request
result = await http_tool.execute(
    url="https://api.example.com/users",
    method="GET",
    timeout=30
)

# POST request with JSON body
result = await http_tool.execute(
    url="https://api.example.com/users",
    method="POST",
    headers={"Authorization": "Bearer token123"},
    body='{"name": "John", "email": "john@example.com"}'
)

# Response structure
# result.output = {
#     "status_code": 200,
#     "status_text": "OK",
#     "headers": {...},
#     "body": {...} or "string",
#     "is_json": True/False,
#     "message": "HTTP GET https://... -> 200 OK"
# }
```

**Parameters**:
| Parameter | Type | Required | Default | Description |
|-----------|------|----------|---------|-------------|
| url | string | Yes | - | Target URL (http/https) |
| method | string | No | GET | HTTP method |
| headers | object | No | {} | Request headers |
| body | string | No | null | Request body |
| timeout | integer | No | 30 | Timeout in seconds (max 300) |

**Error Handling**:
- Timeout: Returns error with timeout message
- Connection errors: Returns detailed error message
- HTTP errors (4xx, 5xx): success=False with response data

---

### 2. DownloadFileTool

Download files from URLs using wget or curl.

**Network Type**: `EXTERNAL_DOWNLOAD` (allowed in offline mode)

**Why Allowed in Offline Mode?**
- One-way data flow (data IN only)
- Does not send local data externally
- Safe for air-gapped networks

**Capabilities**:
- Automatic downloader detection (wget/curl)
- Resume and retry support (3 retries)
- Parent directory auto-creation
- File overwrite protection
- Download size reporting

**Example Usage**:
```python
from app.tools.registry import ToolRegistry

registry = ToolRegistry()
download_tool = registry.get_tool("download_file")

# Download a file
result = await download_tool.execute(
    url="https://example.com/data.zip",
    output_path="/tmp/data.zip",
    timeout=120,
    overwrite=False
)

# Result structure
# result.output = {
#     "url": "https://example.com/data.zip",
#     "output_path": "/tmp/data.zip",
#     "file_size_bytes": 1048576,
#     "file_size_mb": 1.0,
#     "downloader": "wget",
#     "message": "Downloaded 1.00 MB to /tmp/data.zip"
# }
```

**Parameters**:
| Parameter | Type | Required | Default | Description |
|-----------|------|----------|---------|-------------|
| url | string | Yes | - | Download URL (http/https/ftp) |
| output_path | string | Yes | - | Local save path |
| timeout | integer | No | 60 | Timeout in seconds (max 3600) |
| overwrite | boolean | No | false | Overwrite existing file |

**Prerequisites**:
- `wget` or `curl` must be installed on the system
- Tool auto-detects available downloader

---

## Phase 2.5: Code Tools

Three new code-focused tools for enhanced development workflow.

### 3. FormatCodeTool

Format Python code using Black, autopep8, or yapf.

**Network Type**: `LOCAL`

**Capabilities**:
- Multiple formatter support (black, autopep8, yapf)
- Check-only mode (no modifications)
- Line length configuration
- Custom formatter options

**Example Usage**:
```python
from app.tools.registry import ToolRegistry

registry = ToolRegistry()
format_tool = registry.get_tool("format_code")

# Format a file with Black (default)
result = await format_tool.execute(
    file_path="/path/to/code.py",
    formatter="black",
    line_length=88
)

# Check-only mode (don't modify)
result = await format_tool.execute(
    file_path="/path/to/code.py",
    check_only=True
)

# Result structure
# result.output = {
#     "file_path": "/path/to/code.py",
#     "formatter": "black",
#     "modified": True,
#     "message": "Code formatted successfully"
# }
```

**Parameters**:
| Parameter | Type | Required | Default | Description |
|-----------|------|----------|---------|-------------|
| file_path | string | Yes | - | Path to Python file |
| formatter | string | No | black | Formatter (black/autopep8/yapf) |
| check_only | boolean | No | false | Only check, don't modify |
| line_length | integer | No | 88 | Max line length |

---

### 4. ShellCommandTool

Execute shell commands with security restrictions.

**Network Type**: `LOCAL`

**Security Features**:
- Blocked dangerous commands (rm -rf, sudo, etc.)
- Configurable timeout
- Working directory support
- Command allowlist/blocklist

**Example Usage**:
```python
registry = ToolRegistry()
shell_tool = registry.get_tool("shell_command")

# Safe command
result = await shell_tool.execute(
    command="ls -la",
    working_dir="/path/to/project"
)

# Result structure
# result.output = {
#     "stdout": "...",
#     "stderr": "",
#     "return_code": 0,
#     "command": "ls -la"
# }

# Dangerous command (blocked)
result = await shell_tool.execute(command="rm -rf /")
# result.success = False
# result.error = "Security check failed: Command blocked for safety"
```

**Parameters**:
| Parameter | Type | Required | Default | Description |
|-----------|------|----------|---------|-------------|
| command | string | Yes | - | Shell command to execute |
| working_dir | string | No | . | Working directory |
| timeout | integer | No | 30 | Timeout in seconds (max 300) |

**Blocked Commands**:
- `rm -rf /`, `rm -rf ~`, `rm -rf *`
- `sudo`, `su`
- `:(){:|:&};:`  (fork bomb)
- `mkfs`, `dd if=`
- `chmod 777`, `chmod -R 777`

---

### 5. DocstringGeneratorTool

Analyze Python files and generate docstring templates.

**Network Type**: `LOCAL`

**Capabilities**:
- Detect functions without docstrings
- Support Google/NumPy/Sphinx styles
- Generate parameter/return type hints
- Count and list undocumented functions

**Example Usage**:
```python
registry = ToolRegistry()
docstring_tool = registry.get_tool("generate_docstring")

result = await docstring_tool.execute(
    file_path="/path/to/code.py",
    style="google"
)

# Result structure
# result.output = {
#     "file_path": "/path/to/code.py",
#     "functions": [
#         {
#             "name": "my_function",
#             "lineno": 10,
#             "has_docstring": False,
#             "suggested_docstring": "..."
#         }
#     ],
#     "count": 3,
#     "style": "google"
# }
```

**Parameters**:
| Parameter | Type | Required | Default | Description |
|-----------|------|----------|---------|-------------|
| file_path | string | Yes | - | Path to Python file |
| style | string | No | google | Docstring style (google/numpy/sphinx) |

---

## Phase 3: Performance Optimization

Performance features for efficient HTTP operations and result caching.

### Connection Pooling

Shared HTTP connection pool for reduced latency and resource usage.

**Features**:
- Reuse TCP connections across requests
- DNS caching (300s TTL)
- Keep-alive connections (30s)
- Configurable connection limits

**Usage**:
```python
from app.tools.performance import ConnectionPool

# Get singleton instance
pool = await ConnectionPool.get_instance()

# Use shared session
async with pool.get_session() as session:
    async with session.get(url) as response:
        data = await response.json()

# Custom timeout
async with pool.get_session(timeout=120) as session:
    ...

# Get statistics
stats = pool.get_stats()
# {
#     "request_count": 150,
#     "max_connections": 100,
#     "max_per_host": 10,
#     "active_connections": 5,
#     "uptime_seconds": 3600
# }
```

**Configuration**:
| Parameter | Default | Description |
|-----------|---------|-------------|
| max_connections | 100 | Total connection limit |
| max_connections_per_host | 10 | Per-host limit |
| keepalive_timeout | 30 | Keep-alive seconds |
| dns_cache_ttl | 300 | DNS cache seconds |

---

### Result Caching

LRU cache for tool execution results with TTL support.

**Features**:
- Automatic GET request caching
- LRU eviction when full
- TTL-based expiration
- Cache statistics

**Usage**:
```python
from app.tools.performance import get_cache, reset_cache

cache = get_cache()

# Manual cache operations
cache.set("tool_name", {"param": "value"}, result)
cached = cache.get("tool_name", {"param": "value"})

# Invalidate specific entry
cache.invalidate("tool_name", {"param": "value"})

# Clear all
cache.clear()

# Statistics
stats = cache.get_stats()
# {
#     "enabled": True,
#     "size": 45,
#     "max_size": 100,
#     "ttl_seconds": 300,
#     "hits": 120,
#     "misses": 30,
#     "hit_rate_percent": 80.0
# }
```

**HttpRequestTool with Caching**:
```python
http_tool = HttpRequestTool(use_cache=True)

# First request - hits network
result1 = await http_tool.execute(url="https://api.example.com/data")

# Second request - returns cached result
result2 = await http_tool.execute(url="https://api.example.com/data")

# Bypass cache
result3 = await http_tool.execute(
    url="https://api.example.com/data",
    use_cache=False
)
```

---

### Progress Tracking

Real-time download progress with callbacks.

**Features**:
- Bytes downloaded / total
- Speed calculation (Mbps)
- ETA estimation
- Status updates

**Usage**:
```python
from app.tools.performance import ProgressTracker, DownloadProgress

def on_progress(progress: DownloadProgress):
    print(f"{progress.percent:.1f}% - {progress.speed_mbps:.2f} Mbps")

tracker = ProgressTracker(
    url="https://example.com/file.zip",
    output_path="/tmp/file.zip",
    total_bytes=1000000,
    callback=on_progress,
    update_interval=0.5  # seconds
)

# Update during download
async for chunk in response.content.iter_chunked(8192):
    await tracker.update(len(chunk))

tracker.complete(success=True)
```

**DownloadProgress Properties**:
| Property | Type | Description |
|----------|------|-------------|
| url | string | Download URL |
| output_path | string | Local file path |
| total_bytes | int | Total file size |
| downloaded_bytes | int | Downloaded so far |
| percent | float | Progress percentage |
| speed_bps | float | Speed in bytes/sec |
| speed_mbps | float | Speed in Mbps |
| eta_seconds | float | Estimated time remaining |
| status | string | starting/downloading/completed/failed |

---

## Phase 4: Sandbox Execution

Isolated code execution environment using AIO Sandbox (Docker-based).

### SandboxExecuteTool

Execute code in a secure, isolated Docker container.

**Network Type**: `LOCAL` (Docker runs locally)

**Features**:
- Python, Node.js, TypeScript, Shell support
- Isolated container execution (no host access)
- Resource limits (memory, CPU, timeout)
- Offline-ready (uses pre-built Docker images)

**Docker Image**: `ghcr.io/agent-infra/sandbox:latest`

**Example Usage**:
```python
from app.tools.registry import ToolRegistry

registry = ToolRegistry()
sandbox_tool = registry.get_tool("sandbox_execute")

# Python execution
result = await sandbox_tool.execute(
    code="print('Hello, World!')",
    language="python",
    timeout=60
)

# Node.js execution
result = await sandbox_tool.execute(
    code="console.log('Hello');",
    language="nodejs"
)

# Shell command
result = await sandbox_tool.execute(
    code="ls -la && cat /etc/os-release",
    language="shell"
)

# Result structure
# result.output = {
#     "stdout": "Hello, World!\n",
#     "stderr": "",
#     "exit_code": 0,
#     "language": "python",
#     "execution_time_seconds": 0.234
# }
```

**Parameters**:
| Parameter | Type | Required | Default | Description |
|-----------|------|----------|---------|-------------|
| code | string | Yes | - | Code to execute |
| language | string | No | python | Language (python/nodejs/typescript/shell) |
| timeout | integer | No | 60 | Timeout in seconds (max 300) |
| working_dir | string | No | /home/user | Working directory in container |

**Environment Variables**:
```bash
# Docker image
SANDBOX_IMAGE=ghcr.io/agent-infra/sandbox:latest

# API settings
SANDBOX_HOST=localhost
SANDBOX_PORT=8080

# Resource limits
SANDBOX_TIMEOUT=60
SANDBOX_MEMORY=1g
SANDBOX_CPU=2.0

# Optional: Enterprise registry (only for multi-server deployments)
# SANDBOX_REGISTRY=harbor.company.com
```

**Offline Setup (Local Server)**:
```bash
# Pull image once (requires internet)
docker pull ghcr.io/agent-infra/sandbox:latest

# Image is cached locally - works offline after first pull
# No additional configuration needed for single-server deployment
```

**Offline Setup (Enterprise - Multiple Servers)**:
```bash
# On machine with internet access
docker pull ghcr.io/agent-infra/sandbox:latest
docker tag ghcr.io/agent-infra/sandbox:latest harbor.company.com/sandbox/aio:latest
docker push harbor.company.com/sandbox/aio:latest

# On target servers, set environment
export SANDBOX_REGISTRY=harbor.company.com
```

---

## API Reference

### Check Tool Availability

```python
from app.tools.registry import ToolRegistry

registry = ToolRegistry()

# Get tool (returns None if unavailable in current mode)
tool = registry.get_tool("http_request")
if tool is None:
    print("Tool unavailable in current network mode")

# Check availability explicitly
tool = registry.get_tool("http_request", check_availability=False)
if not tool.is_available_in_mode("offline"):
    print(tool.get_unavailable_message())
```

### Get Statistics

```python
registry = ToolRegistry()
stats = registry.get_statistics()

# stats = {
#     "total_tools": 19,
#     "available_tools": 17,  # in offline mode
#     "disabled_tools": 2,    # http_request, web_search blocked
#     "network_mode": "offline",
#     "categories": {...}
# }
```

### List Available Tools

```python
# List only available tools (respects network mode)
available_tools = registry.list_tools()

# List all tools including unavailable
all_tools = registry.list_tools(include_unavailable=True)
```

---

## Installation

### Dependencies

```bash
# Required for HttpRequestTool and Connection Pooling
pip install aiohttp

# Required for FormatCodeTool (optional formatters)
pip install black autopep8 yapf

# Required for DownloadFileTool (system packages)
# Ubuntu/Debian:
apt-get install wget curl

# macOS:
brew install wget curl
```

### Environment Setup

```bash
# Copy example environment
cp .env.example .env

# Edit network mode
# NETWORK_MODE=online   # Development (all tools)
# NETWORK_MODE=offline  # Production/Secure network
```

---

## Testing

### Run Tests

```bash
# All Agent Tools tests (200+ tests)
pytest backend/app/tools/tests/ -v

# Individual test modules:

# Network mode tests (44 tests)
pytest backend/app/tools/tests/test_network_mode.py -v

# Web tools tests (41 tests)
pytest backend/app/tools/tests/test_web_tools_phase2.py -v

# Code tools Phase 2.5 tests (53 tests)
pytest backend/app/tools/tests/test_code_tools_phase25.py -v

# Performance module tests (24 tests)
pytest backend/app/tools/tests/test_performance.py -v

# E2E integration tests (21 tests)
pytest backend/app/tools/tests/test_e2e.py -v

# Integration tests (17 tests)
pytest backend/app/tools/tests/test_integration.py -v
```

### Manual Testing

```python
import asyncio
from app.tools.web_tools import HttpRequestTool, DownloadFileTool

async def test_http():
    tool = HttpRequestTool()
    result = await tool.execute(
        url="https://httpbin.org/get",
        method="GET"
    )
    print(f"Success: {result.success}")
    print(f"Status: {result.output['status_code']}")

async def test_download():
    tool = DownloadFileTool()
    result = await tool.execute(
        url="https://httpbin.org/robots.txt",
        output_path="/tmp/robots.txt"
    )
    print(f"Success: {result.success}")
    print(f"Size: {result.output['file_size_mb']} MB")

# Run tests
asyncio.run(test_http())
asyncio.run(test_download())
```

---

## Troubleshooting

### HttpRequestTool Issues

**Problem**: `aiohttp package not installed`
```bash
pip install aiohttp
```

**Problem**: Tool returns None
```python
# Check if in offline mode
import os
print(os.getenv("NETWORK_MODE"))  # Should be "online"
```

**Problem**: Timeout errors
```python
# Increase timeout for slow APIs
result = await tool.execute(url="...", timeout=120)
```

### DownloadFileTool Issues

**Problem**: `Neither wget nor curl found`
```bash
# Install wget
apt-get install wget  # Linux
brew install wget     # macOS
```

**Problem**: `File already exists`
```python
# Use overwrite option
result = await tool.execute(
    url="...",
    output_path="...",
    overwrite=True
)
```

**Problem**: Permission denied
```bash
# Check directory permissions
ls -la /path/to/directory
chmod 755 /path/to/directory
```

---

## Migration Guide

### From Phase 1 to Phase 2/3

1. **No breaking changes** - All Phase 1 tools work unchanged
2. **Environment variable** - Add `NETWORK_MODE=online` to .env
3. **New dependencies** - Install `aiohttp`, `black` for new features

### Updating Code

```python
# Before (Phase 1)
registry = ToolRegistry()
tool = registry.get_tool("web_search")

# After (Phase 2+) - Same API, now with network mode checking
registry = ToolRegistry()
tool = registry.get_tool("web_search")  # Returns None in offline mode

# Safe pattern
tool = registry.get_tool("web_search")
if tool:
    result = await tool.execute(query="...")
else:
    print("Tool unavailable in current network mode")
```

### Using Performance Features

```python
# HttpRequestTool now uses connection pooling automatically
http_tool = registry.get_tool("http_request")

# Enable/disable caching
result = await http_tool.execute(url="...", use_cache=True)

# DownloadFileTool now supports progress callbacks
download_tool = registry.get_tool("download_file")
result = await download_tool.execute(
    url="...",
    output_path="...",
    progress_callback=my_callback  # Optional
)
```

---

## Best Practices

### 1. Check Tool Availability

```python
tool = registry.get_tool("http_request")
if tool is None:
    # Handle unavailability gracefully
    logger.warning("HttpRequestTool unavailable, using fallback")
    return fallback_result()
```

### 2. Use Appropriate Timeouts

```python
# Short timeout for quick APIs
await http_tool.execute(url="...", timeout=10)

# Long timeout for file downloads
await download_tool.execute(url="...", timeout=300)
```

### 3. Handle Errors

```python
result = await tool.execute(...)
if not result.success:
    logger.error(f"Tool failed: {result.error}")
    # Handle error appropriately
```

### 4. Leverage Caching (Phase 3)

```python
# Cache GET requests for repeated API calls
cache = get_cache()
stats = cache.get_stats()
logger.info(f"Cache hit rate: {stats['hit_rate_percent']}%")

# Invalidate cache when data changes
cache.invalidate("http_request", {"url": "..."})
```

### 5. Monitor Connection Pool (Phase 3)

```python
pool = await ConnectionPool.get_instance()
stats = pool.get_stats()
logger.info(f"Active connections: {stats.get('active_connections', 0)}")
```

---

## Related Documentation

- [ROADMAP.md](./ROADMAP.md) - Development roadmap and phase progress
- [ARCHITECTURE.md](./ARCHITECTURE.md) - System architecture documentation
- [CLI_README.md](./CLI_README.md) - CLI interface documentation
- [SESSION_HANDOFF.md](./SESSION_HANDOFF.md) - Session continuity document

---

**Author**: Claude (Agent Tools Phase 2/2.5/3)
**Last Updated**: 2026-01-08

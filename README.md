<div align="center">

# Agentic Coder

### Enterprise-Grade AI Coding Assistant

[![Python](https://img.shields.io/badge/Python-3.12+-3776AB?style=for-the-badge&logo=python&logoColor=white)](https://www.python.org/downloads/)
[![FastAPI](https://img.shields.io/badge/FastAPI-0.100+-009688?style=for-the-badge&logo=fastapi&logoColor=white)](https://fastapi.tiangolo.com/)
[![React](https://img.shields.io/badge/React-18+-61DAFB?style=for-the-badge&logo=react&logoColor=black)](https://reactjs.org/)
[![License](https://img.shields.io/badge/License-MIT-yellow?style=for-the-badge)](LICENSE)

**Production-ready AI coding assistant with Claude Code-style Unified Workflow Architecture**

[Features](#-key-features) • [Quick Start](#-quick-start) • [Documentation](#-documentation) • [Roadmap](#-roadmap)

---

[한국어 문서 (Korean)](README_KO.md)

</div>

---

## Why Agentic Coder?

Unlike simple code generation tools, Agentic Coder provides a **complete coding workflow** similar to Claude Code and GitHub Copilot Workspace.

<table>
<tr>
<td width="50%" valign="top">

### Unique Strengths

- **Unified Workflow** - Intelligent request routing (Q&A, Planning, Code Gen, Review, Debug)
- **20 Agent Tools** - File, Git, Code, Web, Sandbox operations
- **Network Mode** - Online/Offline for air-gapped enterprise environments
- **Multi-Model** - DeepSeek-R1, Qwen3-Coder, GPT-OSS
- **Korean NLP** - Native Korean language support
- **CLI + Web UI** - Both interfaces with full feature parity

</td>
<td width="50%" valign="top">

### Enterprise Ready

- **Air-Gapped Support** - Works completely offline
- **Data Privacy** - No external API calls in offline mode
- **Sandbox Execution** - Docker isolation for secure code runs
- **Session Management** - Persistent conversation history
- **Self-Hosted** - Run on your own infrastructure
- **262 Tests** - Production-quality test coverage

</td>
</tr>
</table>

---

## Key Features

### 1. Unified Workflow Architecture

```
┌──────────────────────────────────────────────────────────────────────┐
│                         User Request                                  │
└──────────────────────────────────────────────────────────────────────┘
                                 │
                                 ▼
┌──────────────────────────────────────────────────────────────────────┐
│                    Supervisor Agent (Reasoning LLM)                   │
│                                                                       │
│   Analyzes request → Determines response type → Routes to handler    │
└──────────────────────────────────────────────────────────────────────┘
         │              │              │              │              │
         ▼              ▼              ▼              ▼              ▼
    ┌────────┐    ┌────────┐    ┌────────┐    ┌────────┐    ┌────────┐
    │QUICK_QA│    │PLANNING│    │CODE_GEN│    │ REVIEW │    │ DEBUG  │
    └────────┘    └────────┘    └────────┘    └────────┘    └────────┘
         │              │              │              │              │
         └──────────────┴──────────────┴──────────────┴──────────────┘
                                       │
                                       ▼
                    ┌──────────────────────────────────┐
                    │     Unified Response + Artifacts  │
                    └──────────────────────────────────┘
```

**What makes it special:**
- Single entry point handles all request types
- Supervisor uses Reasoning LLM (DeepSeek-R1) for intelligent analysis
- Automatic routing based on request complexity
- Consistent response format across all handlers

---

### 2. Agent Tools (20 Tools)

<table>
<tr>
<td width="33%" valign="top">

**File & Git**
| Tool | Function |
|:-----|:---------|
| `read_file` | Read contents |
| `write_file` | Write/create |
| `search_files` | Pattern search |
| `list_directory` | List files |
| `git_status` | Repo status |
| `git_diff` | View changes |
| `git_log` | History |
| `git_branch` | Branches |
| `git_commit` | Commit |

</td>
<td width="33%" valign="top">

**Code Operations**
| Tool | Function |
|:-----|:---------|
| `execute_python` | Run Python |
| `run_tests` | Test runner |
| `lint_code` | Linting |
| `format_code` | Formatting |
| `shell_command` | Shell exec |
| `generate_docstring` | Docstrings |
| `sandbox_execute` | Isolated run |

</td>
<td width="33%" valign="top">

**Web & Search**
| Tool | Function |
|:-----|:---------|
| `code_search` | Code search |
| `web_search` | Web search |
| `http_request` | REST API |
| `download_file` | Downloads |

**Network Mode**
- `online` = All tools
- `offline` = Block external API

</td>
</tr>
</table>

---

### 3. Network Mode (Air-Gapped Support)

Perfect for **enterprise environments** with strict security requirements.

| Mode | Description | Blocked Tools |
|:-----|:------------|:--------------|
| `online` | Full functionality | None |
| `offline` | Air-gapped mode | `web_search`, `http_request` |

**Security Policy:**
- **Block**: Tools that send data externally
- **Allow**: Tools that only receive data (downloads)
- **Allow**: All local tools (file, git, code)

```bash
# Enable offline mode
NETWORK_MODE=offline
```

---

### 4. Sandbox Execution (Docker Isolation)

Execute untrusted code safely in isolated containers.

```python
sandbox = registry.get_tool("sandbox_execute")

# Python execution
result = await sandbox.execute(
    code="import os; print(os.getcwd())",
    language="python",
    timeout=60
)

# Shell execution
result = await sandbox.execute(
    code="ls -la && whoami",
    language="shell"
)
```

**Supported Languages**: Python, Node.js, TypeScript, Shell

**Offline Setup:**
```bash
docker pull ghcr.io/agent-infra/sandbox:latest
# Works offline after first pull
```

---

### 5. CLI Interface

Full-featured command-line interface with:

- **Command History** - Persistent across sessions
- **Auto-Completion** - Tab completion for commands and files
- **Slash Commands** - `/help`, `/status`, `/preview`, `/config`
- **Streaming Output** - Real-time code generation display

```bash
# Start interactive mode
python -m cli

# One-shot mode
python -m cli "Create a Python REST API"

# With options
python -m cli --workspace ./project --model qwen2.5-coder:32b
```

---

## Quick Start

### Prerequisites

| Requirement | Version |
|:------------|:--------|
| Python | 3.12+ |
| Node.js | 20+ |
| Docker | Latest (for sandbox) |
| GPU | NVIDIA recommended (for vLLM) |

### Installation

```bash
# 1. Clone
git clone https://github.com/your-org/agentic-coder.git
cd agentic-coder

# 2. Environment
cp .env.example .env

# 3. Backend
cd backend
python -m venv venv
source venv/bin/activate  # Windows: venv\Scripts\activate
pip install -r requirements.txt

# 4. Frontend
cd ../frontend
npm install

# 5. Sandbox (optional)
docker pull ghcr.io/agent-infra/sandbox:latest
```

### Start Services

```bash
# Terminal 1: vLLM (Reasoning)
vllm serve deepseek-ai/DeepSeek-R1 --port 8001

# Terminal 2: vLLM (Coding)
vllm serve Qwen/Qwen3-8B-Coder --port 8002

# Terminal 3: Backend
cd backend && uvicorn app.main:app --port 8000 --reload

# Terminal 4: Frontend
cd frontend && npm run dev
```

**Access:** http://localhost:5173

### Mock Mode (No GPU)

```bash
./RUN_MOCK.sh  # Linux/Mac
RUN_MOCK.bat   # Windows
```

---

## Configuration

```bash
# .env

# LLM Endpoints
VLLM_REASONING_ENDPOINT=http://localhost:8001/v1
VLLM_CODING_ENDPOINT=http://localhost:8002/v1
REASONING_MODEL=deepseek-ai/DeepSeek-R1
CODING_MODEL=Qwen/Qwen3-8B-Coder

# Network Mode
NETWORK_MODE=online  # or 'offline'

# Sandbox
SANDBOX_IMAGE=ghcr.io/agent-infra/sandbox:latest
SANDBOX_HOST=localhost
SANDBOX_PORT=8080
SANDBOX_TIMEOUT=60
```

---

## API Reference

### Unified Chat

```http
POST /chat/unified
Content-Type: application/json

{
  "message": "Create a Python calculator with tests",
  "session_id": "session-123",
  "workspace": "/path/to/workspace"
}
```

### Streaming

```http
POST /chat/unified/stream
```

---

## Testing

```bash
cd backend
pytest app/tools/tests/ -v

# 262 passed, 8 skipped
```

---

## Documentation

| Document | Description |
|:---------|:------------|
| [Agent Tools Guide](docs/AGENT_TOOLS_PHASE2_README.md) | All 20 tools documentation |
| [Architecture](docs/ARCHITECTURE.md) | System design |
| [CLI Guide](docs/CLI_README.md) | Command-line interface |
| [Mock Mode](docs/MOCK_MODE.md) | Testing without GPU |
| [Roadmap](docs/ROADMAP.md) | Development roadmap & future plans |

---

## Roadmap

- [x] **Phase 1** - Core tools (14 tools)
- [x] **Phase 2** - Network mode + Web tools
- [x] **Phase 2.5** - Code formatting tools
- [x] **Phase 3** - CLI & Performance optimization
- [x] **Phase 4** - Sandbox execution
- [ ] **Phase 5** - Plan mode with approval workflow
- [ ] **Phase 6** - Context window optimization
- [ ] **Phase 7** - MCP (Model Context Protocol) integration
- [ ] **Phase 8** - Multi-agent collaboration

See [ROADMAP.md](docs/ROADMAP.md) for detailed plans and feature backlog.

---

## Supported Models

| Model | Type | Strengths |
|:------|:-----|:----------|
| DeepSeek-R1 | Reasoning | Complex analysis, planning |
| Qwen3-Coder | Coding | Code generation, completion |
| GPT-OSS | General | Balanced performance |

---

## Contributing

1. Fork the repository
2. Create feature branch (`git checkout -b feature/amazing`)
3. Commit changes (`git commit -m 'Add amazing feature'`)
4. Push branch (`git push origin feature/amazing`)
5. Open Pull Request

---

## License

MIT License - see [LICENSE](LICENSE) for details.

---

<div align="center">

**Built with**

[![Python](https://img.shields.io/badge/-Python-3776AB?style=flat-square&logo=python&logoColor=white)](https://python.org)
[![FastAPI](https://img.shields.io/badge/-FastAPI-009688?style=flat-square&logo=fastapi&logoColor=white)](https://fastapi.tiangolo.com)
[![React](https://img.shields.io/badge/-React-61DAFB?style=flat-square&logo=react&logoColor=black)](https://reactjs.org)
[![vLLM](https://img.shields.io/badge/-vLLM-FF6F00?style=flat-square&logo=lightning&logoColor=white)](https://vllm.ai)
[![Docker](https://img.shields.io/badge/-Docker-2496ED?style=flat-square&logo=docker&logoColor=white)](https://docker.com)

---

**If this project helps you, please give it a ⭐**

</div>

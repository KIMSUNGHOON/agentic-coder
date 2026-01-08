# Agentic Coder - Development Roadmap

**Last Updated**: 2026-01-08
**Current Version**: 1.0.0
**Status**: Phase 4 Complete

---

## Overview

This document tracks the development progress of Agentic Coder, including completed work, ongoing development, and future plans.

---

## Completed Phases

### Phase 1: Core Tools (14 Tools)

**Status**: Complete

Core agent tools for file operations, Git, and code execution.

| Category | Tools | Description |
|----------|-------|-------------|
| **File Operations** | `read_file`, `write_file`, `search_files`, `list_directory` | Basic file system operations |
| **Git Operations** | `git_status`, `git_diff`, `git_log`, `git_branch`, `git_commit` | Version control integration |
| **Code Execution** | `execute_python`, `run_tests`, `lint_code` | Code running and validation |
| **Search** | `code_search`, `web_search` | Semantic code and web search |

---

### Phase 2: Network Mode + Web Tools

**Status**: Complete
**Commit**: `a266500`

Added network security modes and HTTP tools for enterprise environments.

#### New Tools
| Tool | Network Type | Description |
|------|--------------|-------------|
| `http_request` | EXTERNAL_API | REST API calls (blocked in offline mode) |
| `download_file` | EXTERNAL_DOWNLOAD | File downloads (allowed in offline mode) |

#### Network Modes
| Mode | Description | Blocked Tools |
|------|-------------|---------------|
| `online` | Full functionality | None |
| `offline` | Air-gapped/secure environments | `web_search`, `http_request` |

**Security Policy**:
- **Block**: Tools that send data externally (interactive)
- **Allow**: Tools that only receive data (downloads)
- **Allow**: All local tools (file, git, code)

---

### Phase 2.5: Code Formatting Tools

**Status**: Complete
**Commit**: `7571753`

| Tool | Description |
|------|-------------|
| `format_code` | Auto-format code (Black, Prettier) |
| `shell_command` | Execute shell commands |
| `generate_docstring` | Generate docstrings for functions |

---

### Phase 3: CLI & Performance Optimization

**Status**: Complete
**Commit**: `dd4860d`

#### CLI Features
- **Interactive REPL Mode**: Conversational coding interface
- **One-shot Mode**: Single command execution
- **Session Management**: Persistent conversation history (`.agentic-coder/sessions/`)
- **Command History**: prompt_toolkit with persistent history
- **Auto-completion**: Tab completion for commands and files
- **Configuration**: YAML-based config (`~/.agentic-coder/config.yaml`)
- **Slash Commands**: `/help`, `/status`, `/history`, `/context`, `/files`, `/preview`

#### Key Files
| File | Description |
|------|-------------|
| `backend/cli/__main__.py` | CLI entry point with argparse |
| `backend/cli/session_manager.py` | Session persistence and workflow integration |
| `backend/cli/terminal_ui.py` | Rich-based terminal interface |
| `backend/cli/interactive.py` | prompt_toolkit integration |
| `backend/cli/config.py` | Configuration management |

---

### Phase 4: Sandbox Execution

**Status**: Complete
**Commit**: `6c3411e`

Docker-based isolated code execution using AIO Sandbox.

#### New Tool
| Tool | Description |
|------|-------------|
| `sandbox_execute` | Execute code in isolated Docker container |

#### Supported Languages
- Python (via Jupyter API)
- Node.js / TypeScript (via Shell API)
- Shell/Bash

#### Key Components
| Component | Description |
|-----------|-------------|
| `SandboxConfig` | Configuration with environment variable support |
| `SandboxManager` | Singleton Docker container lifecycle manager |
| `SandboxExecuteTool` | Main tool for code execution |
| `SandboxFileManager` | File operations inside sandbox |

#### Configuration (.env)
```bash
SANDBOX_IMAGE=ghcr.io/agent-infra/sandbox:latest
SANDBOX_HOST=localhost
SANDBOX_PORT=8080
SANDBOX_TIMEOUT=60
SANDBOX_MEMORY=1g
SANDBOX_CPU=2.0
# Optional for enterprise: SANDBOX_REGISTRY=harbor.company.com
```

---

## Tool Summary

**Total: 20 Tools**

| Phase | Tools Added | Running Total |
|-------|-------------|---------------|
| Phase 1 | 14 | 14 |
| Phase 2 | 2 | 16 |
| Phase 2.5 | 3 | 19 |
| Phase 4 | 1 | 20 |

---

## Planned Phases

### Phase 5: Plan Mode with Approval Workflow

**Status**: Planned
**Priority**: High

Implementation of a planning phase before code generation, with human-in-the-loop approval.

#### Core Concept
```
User Request
    │
    ▼
┌─────────────────────┐
│ Plan Agent          │ ← Analyzes request, creates implementation plan
│ (Reasoning LLM)     │
└─────────────────────┘
    │
    ▼
┌─────────────────────┐
│ User Review         │ ← Approve / Modify / Reject plan
│ (Chat UI or Modal)  │
└─────────────────────┘
    │
    ▼
┌─────────────────────┐
│ Step-by-step        │ ← Execute with checkpoints
│ Execution           │
└─────────────────────┘
```

#### Planned Features

**AI-Driven HITL**:
- Agent detects uncertainty during reasoning
- Automatically generates clarifying questions
- Waits for user feedback before proceeding

**User-Driven HITL**:
- Pause button to interrupt workflow at any time
- Feedback via chat UI (not separate modal)
- Modify plan mid-execution

**Plan Structure**:
```json
{
  "plan_id": "plan-abc123",
  "steps": [
    {
      "step": 1,
      "action": "create_file",
      "target": "src/calculator.py",
      "description": "Create main calculator module",
      "requires_approval": true
    },
    {
      "step": 2,
      "action": "modify_file",
      "target": "src/main.py",
      "description": "Import and use calculator",
      "requires_approval": false
    }
  ],
  "estimated_files": ["calculator.py", "test_calculator.py"],
  "risks": ["Breaking change to main.py imports"]
}
```

#### Implementation Tasks
- [ ] Plan generation prompt engineering
- [ ] Plan review UI component
- [ ] Step-by-step execution with checkpoints
- [ ] Plan modification API
- [ ] Integration with existing HITL infrastructure

---

### Phase 6: Context Window Optimization

**Status**: Planned
**Priority**: High

Improve context management for large codebases and long conversations.

#### Current Limitations
```python
# Current: Only 6 messages, 200 chars each
recent_context = conversation_history[-6:]
content[:200]  # Truncated!
```

#### Planned Improvements

**1. Expanded Context Window**:
```python
# Target: 20 messages, 1000 chars each
recent_context = conversation_history[-20:]
content[:1000]
```

**2. Structured Context Extraction**:
- Extract file names mentioned in conversation
- Track error messages and their resolutions
- Maintain decision history

**3. Context Sharing Across Agents**:
- Currently only Supervisor has context
- Target: All agents (Coder, Reviewer, Refiner) access context
- Shared state for file references

**4. RAG Integration** (Optional):
```
User Query → Embedding → Vector Search → Top-K Results
                                              │
                                              ▼
                              LLM + Retrieved Context
```

Components:
- ChromaDB for vector storage
- Sentence-transformers for embeddings
- Chunked code indexing
- Semantic code search

---

### Phase 7: MCP (Model Context Protocol) Integration

**Status**: Planned
**Priority**: Medium

Integration with Anthropic's Model Context Protocol.

#### Planned Features

**MCP Server Mode**:
- Expose all 20 tools as MCP-compatible endpoints
- Standardized tool schemas
- Compatible with Claude Desktop, etc.

**MCP Client Mode**:
- Connect to external MCP servers
- Dynamic tool discovery
- Tool chaining across servers

#### Benefits
- Interoperability with MCP ecosystem
- Easy tool sharing
- Standardized context management

---

### Phase 8: Multi-Agent Collaboration

**Status**: Planned
**Priority**: Low

Enable multiple specialized agents to work together.

#### Architecture
```
┌─────────────────────────────────────────┐
│           Supervisor Agent              │
│   (Task analysis and delegation)        │
└─────────────────────────────────────────┘
         │           │           │
         ▼           ▼           ▼
    ┌─────────┐ ┌─────────┐ ┌─────────┐
    │Research │ │ Coder   │ │ Tester  │
    │ Agent   │ │ Agent   │ │ Agent   │
    └─────────┘ └─────────┘ └─────────┘
         │           │           │
         └───────────┴───────────┘
                     │
                     ▼
            ┌─────────────┐
            │ Aggregator  │
            └─────────────┘
```

#### Specialized Agents
| Agent | Role | Tools |
|-------|------|-------|
| Research Agent | Web search, documentation | `web_search`, `http_request` |
| Coder Agent | Code generation | `write_file`, `execute_python` |
| Tester Agent | Test execution | `run_tests`, `sandbox_execute` |
| Reviewer Agent | Code review | `read_file`, `lint_code` |

---

## Performance Optimization Notes

### GPU Configuration (H100)
```python
# Recommended for H100 96GB NVL
max_parallel_agents = 25  # (default: 10)
```

### Session Pipelining
```
Session A: [Planning@GPU0] → [Coding@GPU1] → [Review@GPU1]
Session B:                    [Planning@GPU0] → [Coding@GPU1]
                                            ↑ GPU0 can handle Session B
```

### Expected Improvements
- GPU utilization: 40% → 80%+
- Workflow completion: 30-40% faster
- Multi-user throughput: 3x improvement

---

## Feature Backlog

### High Priority
| Feature | Description | Phase |
|---------|-------------|-------|
| Plan Mode | Pre-implementation planning | 5 |
| Context Optimization | Smart context management | 6 |
| Error Recovery | Automatic retry and correction | 5 |

### Medium Priority
| Feature | Description | Phase |
|---------|-------------|-------|
| MCP Support | Model Context Protocol | 7 |
| Plugin System | User-defined tool extensions | - |
| Git Auto-commit | Automatic commit management | - |
| File Watching | React to file changes | - |

### Low Priority
| Feature | Description | Phase |
|---------|-------------|-------|
| Multi-Agent | Parallel agent execution | 8 |
| Web UI Improvements | Enhanced frontend | - |
| RAG Enhancement | Embeddings-based search | 6 |
| Metrics Dashboard | Usage tracking | - |

---

## Known Limitations

1. **Single Model per Role**: Only one reasoning + one coding model
2. **No Plan Mode**: Code generation starts immediately
3. **Limited Context**: 6 messages, 200 chars (improvement planned)
4. **No MCP**: Not compatible with MCP ecosystem yet
5. **Sequential Workflow**: Limited parallelization within single session

---

## Test Coverage

```
262 passed, 8 skipped, 3 warnings
```

- Phase 4 sandbox: 38 tests
- CLI: 2 tests skipped (optional `rich` dependency)

---

## Version History

| Version | Date | Changes |
|---------|------|---------|
| 1.0.0 | 2026-01-08 | Phase 1-4 complete, 20 tools, CLI ready |
| 0.9.0 | 2026-01-07 | Phase 3 CLI enhancements |
| 0.8.0 | 2026-01-06 | Phase 2 network mode |
| 0.7.0 | 2026-01-05 | Phase 1 core tools |

---

## References

- [Architecture](./ARCHITECTURE.md) - System design
- [Agent Tools](./AGENT_TOOLS_PHASE2_README.md) - Tool documentation
- [CLI Guide](./CLI_README.md) - CLI usage
- [Main README](../README.md) - Project overview

---

**Maintainer**: Agentic Coder Team
**License**: MIT

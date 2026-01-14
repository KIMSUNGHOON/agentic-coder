# Agentic 2.0 - Universal On-Premise Agentic AI

**Version:** 1.0.0
**Status:** Phase 0 - Foundation

## Overview

Agentic 2.0 is a universal, on-premise Agentic AI system built with LangChain ecosystem. Unlike coding-focused agents, Agentic 2.0 handles diverse tasks:

- **Coding**: Implementation, debugging, refactoring
- **Research**: Technical research, document analysis, report generation
- **Data**: Data processing, analysis, automation
- **General**: Q&A, planning, recommendations

## Key Features

✅ **On-Premise Only** - No external SaaS dependencies, works in air-gapped environments
✅ **Dual LLM Endpoints** - Active-active or primary/secondary with automatic failover
✅ **Cross-Platform** - Identical behavior on Windows, macOS, Linux
✅ **Dynamic Workflows** - Sub-agent spawning based on task complexity
✅ **Self-Reflection** - Automatic retry with critic feedback
✅ **Tool Safety** - Explicit allowlist/denylist for commands

## Technology Stack

| Component | Technology |
|-----------|-----------|
| **LLM** | GPT-OSS-120B via vLLM |
| **Orchestration** | LangGraph StateGraph |
| **Agents** | LangChain + DeepAgents |
| **Tools** | Custom Python tools (FS, Git, Search, Process) |
| **Persistence** | SQLite / PostgreSQL |
| **Logging** | JSONL structured logs |

## Prerequisites

- Python 3.10+
- vLLM server(s) running GPT-OSS-120B
- Git

## Quick Start

```bash
# 1. Start vLLM servers
vllm serve openai/gpt-oss-120b --port 8001
vllm serve openai/gpt-oss-120b --port 8002  # Optional secondary

# 2. Install dependencies
pip install -r requirements.txt

# 3. Configure
cp config/config.yaml.example config/config.yaml
# Edit config.yaml with your vLLM endpoints

# 4. Initialize
python -m core.memory init

# 5. Run
python cli.py "Your task here"
```

## Project Structure

```
agentic-ai/
├── core/               # Core infrastructure
│   ├── llm_client.py   # DualEndpointLLMClient
│   ├── router.py       # Intent classification
│   ├── state_graph.py  # LangGraph workflows
│   └── memory.py       # Persistence
├── agents/             # Agent implementations
│   ├── planner.py
│   ├── executor.py
│   ├── reviewer.py
│   └── finalizer.py
├── tools/              # Tool layer
│   ├── fs.py           # Filesystem tools
│   ├── git.py          # Git tools
│   ├── process.py      # Process execution
│   └── search.py       # Code search
├── workflows/          # Workflow definitions
│   ├── coding.py
│   ├── research.py
│   ├── data.py
│   └── general.py
├── config/             # Configuration
│   └── config.yaml
└── cli.py              # Command-line interface
```

## Architecture

```
User Prompt
    ↓
Intent Router (GPT-OSS-120B)
    ↓
Workflow Selection (coding | research | data | general)
    ↓
LangGraph State Machine
    INIT → ROUTE → PLAN → ACT → REVIEW → ITERATE → FINAL
    ↓
Agents:
    - Planner (DeepAgents TodoListMiddleware)
    - Executor (ReAct pattern with tools)
    - Reviewer (Critic with self-reflection)
    - Finalizer (Report generation)
    - Sub-Agents (Dynamic spawning)
    ↓
Tool Layer (FS | Git | Process | Search)
    ↓
Dual vLLM Endpoints (Primary ←→ Secondary)
```

## Development Status

### Phase 0: Foundation (Current) ✅
- [x] Project structure
- [x] DualEndpointLLMClient with failover
- [x] Multi-domain Intent Router
- [ ] Tool Safety Module
- [ ] Basic tools implementation
- [ ] Simplified state schema

### Phase 1: Core Workflow (Next)
- [ ] LangGraph state machine
- [ ] Core agents (Planner, Executor, Reviewer, Finalizer)
- [ ] Coding workflow end-to-end

### Phase 2: Multi-Workflow
- [ ] Research workflow
- [ ] Data workflow
- [ ] General workflow

### Phase 3: Advanced Features
- [ ] Sub-agent spawning (DeepAgents)
- [ ] Persistence (SQLite)
- [ ] Observability (JSONL logs)

### Phase 4: Production Readiness
- [ ] Performance optimization
- [ ] Complete documentation
- [ ] Deployment packaging

## Configuration

See `config/config.yaml` for all configuration options.

Key settings:
- LLM endpoints (primary/secondary)
- Health check intervals
- Retry parameters
- Tool safety (allowlist/denylist)
- Workflow limits

## Testing

```bash
# Run all tests
pytest tests/

# Unit tests only
pytest tests/unit/

# Integration tests
pytest tests/integration/

# End-to-end tests
pytest tests/e2e/
```

## License

[Your License Here]

## References

- [LangChain Documentation](https://docs.langchain.com)
- [LangGraph Documentation](https://www.langchain.com/langgraph)
- [DeepAgents Documentation](https://github.com/langchain-ai/deepagents)
- [vLLM Documentation](https://docs.vllm.ai)
- [GPT-OSS Documentation](https://github.com/openai/gpt-oss)

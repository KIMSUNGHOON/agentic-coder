# Coding Agent - Full Stack AI Assistant

A full-stack coding agent powered by **dual agent frameworks** (Microsoft Agent Framework + LangChain/LangGraph) and vLLM, featuring a Claude.ai inspired React frontend and FastAPI backend.

## 🏗️ Architecture

```
┌─────────────────────┐
│   React Frontend    │ (Port 3000/80)
│  - Claude.ai Style  │
│  - Chat & Workflow  │
└─────────┬───────────┘
          │ REST API
          ▼
┌─────────────────────┐
│   FastAPI Server    │ (Port 8000)
│    - API Gateway    │
│    - Agent Factory  │
└─────────┬───────────┘
          │
          ▼
┌─────────────────────────────────────────┐
│         Agent Framework Layer           │
│  ┌─────────────┐  ┌─────────────────┐   │
│  │  Microsoft  │  │    LangChain    │   │
│  │   Agent     │  │   + LangGraph   │   │
│  │  Framework  │  │                 │   │
│  └──────┬──────┘  └────────┬────────┘   │
│         │                  │            │
│         └────────┬─────────┘            │
│                  ▼                      │
│  ┌─────────────────────────────────┐    │
│  │    Tool System (11 Tools)       │    │
│  │  - File: read, write, search    │    │
│  │  - Code: execute, lint, test    │    │
│  │  - Git: status, log, diff       │    │
│  └─────────────────────────────────┘    │
│                  │                      │
│  ┌─────────────────────────────────┐    │
│  │    Specialized Agents           │    │
│  │  - Research Agent (DeepSeek-R1) │    │
│  │  - Testing Agent (Qwen3-Coder)  │    │
│  └─────────────────────────────────┘    │
└─────────────────────────────────────────┘
          │
          ▼
┌───────────┐  ┌───────────┐
│ vLLM #1   │  │ vLLM #2   │
│ DeepSeek  │  │ Qwen3     │
│ R1        │  │ Coder     │
│ (Port     │  │ (Port     │
│  8001)    │  │  8002)    │
└───────────┘  └───────────┘
```

## 📋 Features

### Agent Frameworks
- 🔀 **Dual Framework Support**: Choose between Microsoft Agent Framework or LangChain/LangGraph
- 🤖 **Specialized Agents**: Research Agent (codebase exploration) and Testing Agent (test generation)
- 🛠️ **Tool System**: 11 integrated tools for file operations, code execution, and git commands
- 📊 **Agent Registry**: Dynamic agent spawning and management

### AI Models & Prompts
- 🧠 **Dual Model Support**: DeepSeek-R1 for reasoning, Qwen3-Coder for code generation
- 📝 **Optimized Prompts**: DeepSeek R1 style (`<think>` tags) and Qwen3 style (THOUGHTS/PLAN markers)
- 🌊 **Streaming Responses**: Real-time token streaming support

### User Interface
- 🎨 **Unified AI Assistant**: Single interface with automatic chat/workflow detection
- 💬 **Intelligent Routing**: Automatically chooses chat or workflow based on request type
- 🔄 **Multi-Agent Workflow**: Planning → Coding (Parallel) → Review pipeline
- 📱 **Responsive Design**: Works on desktop and mobile
- 📝 **Streaming Code Preview**: Real-time code generation with 6-line previews
- 💾 **Conversation Management**: Auto-save with user preferences, conversation history
- 📁 **Project Setup**: Guided project name and workspace configuration

### Infrastructure
- 🐳 **Docker Support**: Easy deployment with Docker Compose
- 🐍 **Conda Support**: Alternative setup using Conda/Miniconda environments
- 🔄 **Session Management**: Persistent conversation history

## 🚀 Quick Start

### Prerequisites

1. **vLLM servers running** (required before starting the app):
   ```bash
   # Terminal 1: Start DeepSeek-R1 for reasoning
   vllm serve deepseek-ai/DeepSeek-R1 --port 8001

   # Terminal 2: Start Qwen3-Coder for coding
   vllm serve Qwen/Qwen3-8B-Coder --port 8002
   ```

2. **Python 3.12** and **Node.js 20+** installed (or Conda/Miniconda)

### Development Setup

#### Backend

```bash
cd backend

# Create virtual environment
python -m venv venv
source venv/bin/activate  # On Windows: venv\Scripts\activate

# Install dependencies
pip install -r requirements.txt

# Additional dependencies for full functionality
pip install pydantic-settings aiofiles langchain langchain-openai langgraph

# Copy and configure environment
cp .env.example .env

# Run the server
uvicorn app.main:app --host 0.0.0.0 --port 8000 --reload
```

#### Frontend

```bash
cd frontend

# Install dependencies
npm install

# Start development server
npm run dev
```

The frontend will be available at http://localhost:5173

## 📁 Project Structure

```
TestCodeAgent/
├── backend/
│   ├── app/
│   │   ├── main.py                    # FastAPI entry point
│   │   ├── core/
│   │   │   └── config.py              # Configuration (agent_framework setting)
│   │   ├── api/
│   │   │   ├── routes.py              # API endpoints
│   │   │   └── models.py              # Pydantic models
│   │   ├── agent/
│   │   │   ├── factory.py             # Framework selection factory
│   │   │   ├── registry.py            # Agent registry & spawner
│   │   │   ├── base/
│   │   │   │   └── interface.py       # Abstract interfaces
│   │   │   ├── microsoft/             # Microsoft Agent Framework
│   │   │   │   ├── agent_manager.py   # Chat agent management
│   │   │   │   └── workflow_manager.py # Multi-agent workflow
│   │   │   ├── langchain/             # LangChain/LangGraph
│   │   │   │   ├── agent_manager.py   # LangChain agent
│   │   │   │   ├── workflow_manager.py # LangGraph workflow
│   │   │   │   ├── tool_adapter.py    # Native→LangChain tool bridge
│   │   │   │   └── specialized/       # LangChain specialized agents
│   │   │   └── specialized/           # Microsoft specialized agents
│   │   │       ├── research_agent.py  # Codebase exploration
│   │   │       └── testing_agent.py   # Test generation
│   │   ├── tools/                     # Tool system
│   │   │   ├── base.py                # BaseTool interface
│   │   │   ├── registry.py            # ToolRegistry
│   │   │   ├── executor.py            # ToolExecutor
│   │   │   ├── file_tools.py          # File operations
│   │   │   ├── code_tools.py          # Code execution
│   │   │   └── git_tools.py           # Git commands
│   │   └── services/
│   │       └── vllm_client.py         # vLLM client & router
│   ├── requirements.txt
│   └── Dockerfile
├── frontend/
│   ├── src/
│   │   ├── components/
│   │   │   ├── ChatInterface.tsx      # Claude.ai style chat
│   │   │   ├── ChatMessage.tsx        # Message bubbles
│   │   │   ├── WorkflowInterface.tsx  # Multi-agent workflow
│   │   │   ├── WorkflowStep.tsx       # Workflow step cards
│   │   │   ├── ConversationList.tsx   # Sidebar
│   │   │   └── AgentStatus.tsx        # Status panel
│   │   ├── api/
│   │   │   └── client.ts              # API client
│   │   ├── App.tsx                    # Main app
│   │   └── index.css                  # Claude.ai color palette
│   └── package.json
├── docker-compose.yml
└── README.md
```

## 🔀 Agent Framework Selection

Configure which framework to use in `backend/app/core/config.py`:

```python
agent_framework: Literal["microsoft", "langchain"] = "microsoft"
```

Or set via environment variable:
```bash
export AGENT_FRAMEWORK=langchain
```

### Microsoft Agent Framework
- **ChatAgent**: Conversation management with system prompts
- **WorkflowBuilder**: Sequential multi-agent pipelines
- Best for: Structured workflows, enterprise use cases

### LangChain/LangGraph
- **LangGraph StateGraph**: Flexible agent graphs with conditional routing
- **ReAct Pattern**: Reasoning + Acting with tool use
- Best for: Complex tool-use scenarios, research tasks

## 🛠️ Tool System

The agent has access to 11 integrated tools:

| Category | Tool | Description |
|----------|------|-------------|
| **File** | `read_file` | Read file contents |
| | `write_file` | Write/create files |
| | `search_files` | Glob pattern search |
| | `list_directory` | List directory contents |
| **Code** | `execute_python` | Run Python code safely |
| | `run_tests` | Execute pytest tests |
| | `lint_code` | Check with flake8 |
| **Git** | `git_status` | Repository status |
| | `git_log` | Commit history |
| | `git_diff` | Show changes |
| | `git_show` | Show commit details |

## 📝 Prompt Engineering

### DeepSeek R1 Style (Reasoning Models)
Used for: Research Agent, Planning Agent

```
<think>
Break down the request into steps.
Consider dependencies.
</think>

<output_format>
Structured output here
</output_format>
```

### Qwen3 Style (Coding Models)
Used for: Testing Agent, Coding Agent, Review Agent

```
<tools>
tool_name: description (params)
</tools>

<response_format>
THOUGHTS: [analysis]
PLAN:
1. [step]
ACTION: [tool]
</response_format>
```

## 🎨 UI Design

The frontend uses a Claude.ai inspired design:

| Element | Color |
|---------|-------|
| Background | `#FAF9F7` (warm off-white) |
| Accent | `#DA7756` (terracotta) |
| Text Primary | `#1A1A1A` |
| Text Secondary | `#666666` |
| Border | `#E5E5E5` |

## 🎯 API Endpoints

### Chat
- `POST /api/chat` - Send message (non-streaming)
- `POST /api/chat/stream` - Send message (streaming)

### Workflow
- `POST /api/workflow/execute` - Execute multi-agent workflow

### Agent Management
- `GET /api/agent/status/{session_id}` - Get agent status
- `POST /api/agent/clear/{session_id}` - Clear history
- `DELETE /api/agent/session/{session_id}` - Delete session

### Tools
- `POST /api/tools/execute` - Execute a tool directly
- `GET /api/tools/list` - List available tools

## 🔧 Configuration

### Environment Variables

```env
# vLLM Endpoints
VLLM_REASONING_ENDPOINT=http://localhost:8001/v1
VLLM_CODING_ENDPOINT=http://localhost:8002/v1

# Model names
REASONING_MODEL=deepseek-ai/DeepSeek-R1
CODING_MODEL=Qwen/Qwen3-8B-Coder

# Agent Framework: "microsoft" or "langchain"
AGENT_FRAMEWORK=microsoft

# API Configuration
API_HOST=0.0.0.0
API_PORT=8000
CORS_ORIGINS=http://localhost:3000,http://localhost:5173
```

## 🐛 Troubleshooting

### Missing Dependencies
```bash
# Backend
pip install pydantic-settings aiofiles langchain langchain-openai langgraph

# Frontend
npm install
```

### vLLM Connection Issues
```bash
# Verify vLLM servers
curl http://localhost:8001/v1/models
curl http://localhost:8002/v1/models
```

### Import Errors
Ensure all dependencies are installed and the virtual environment is activated.

## 🚀 Recent Improvements

### v2.0 - Unified AI Assistant (December 2025)

**Major UX Overhaul:**
- ✅ **Unified Interface**: Removed separate Chat/Workflow modes - single interface with intelligent routing
- ✅ **Context-Aware Routing**: Supervisor automatically detects if request needs workflow or simple chat
- ✅ **Streaming Code Preview**: Real-time code generation with 6-line previews during parallel execution
- ✅ **Project Setup Wizard**: Two-step guided setup (Project Name → Workspace Path)
- ✅ **Conversation Management**: User-configurable auto-save with localStorage persistence

**Backend Improvements:**
- 🔧 **Fixed Task Type Parsing**: Improved regex-based TASK_TYPE extraction from supervisor
- 🔧 **Default to Code Generation**: Changed fallback from "general" to "code_generation" for better UX
- 🔧 **Progress Callbacks**: Added streaming progress for code generation tasks
- 🔧 **Async Queue System**: Real-time code preview delivery via asyncio.Queue

**Frontend Improvements:**
- 🎨 **Code Preview Component**: New `code_preview` type in WorkflowStep with syntax highlighting
- 🎨 **Two-Step Project Dialog**: Guided project name and workspace path configuration
- 🎨 **Save Confirmation Dialog**: Three options (Save Once / Always Save / Don't Save)
- 🎨 **Auto-Refresh Conversations**: Conversation list refreshes every 5 seconds
- 🎨 **Improved Type Safety**: Added `CodePreview` interface to TypeScript types

**Context Awareness:**
```python
# Supervisor now checks context before routing
<context_awareness>
1. Is there EXISTING CODE in the context?
2. Is the user asking HOW TO USE/RUN existing code?
3. Is the user asking for EXPLANATIONS/DOCUMENTATION?
→ Route to chat mode (general)
→ Route to workflow (code_generation, bug_fix, etc.)
</context_awareness>
```

### v2.1 - DeepAgents Integration (December 2025)

**Dual Framework Architecture:**
- 🔀 **Framework Selection**: Choose between Standard (LangChain) and DeepAgents workflow frameworks
- 🎛️ **Per-Session Configuration**: Each session can use a different framework independently
- 🔄 **Runtime Switching**: Change frameworks on-the-fly via UI dropdown selector

**DeepAgents Middleware Stack:**
```python
# Hybrid DeepAgents with Parallel Execution
DeepAgentWorkflowManager(
    enable_subagents=True,      # SubAgentMiddleware: Isolated sub-agent contexts
    enable_filesystem=True,     # FilesystemMiddleware: Persistent conversation state
    enable_parallel=True,       # Parallel execution with SharedContext
    max_parallel_agents=25      # H100 GPU optimization (25 concurrent agents)
)
```

**Key Benefits:**

1. **TodoListMiddleware** - Structured Task Tracking
   - Automatic task creation from user requests
   - Real-time progress updates in frontend
   - Structured task state (pending, in_progress, completed)
   - No manual checklist management needed

2. **SubAgentMiddleware** - Isolated Execution Contexts
   - Each sub-task runs in isolated context
   - Prevents context pollution across tasks
   - Cleaner state management
   - Better error isolation

3. **SummarizationMiddleware** - Automatic Context Management
   - Auto-compresses conversation at 170k tokens
   - No manual context truncation needed
   - Preserves important information
   - Prevents token limit overflow

4. **FilesystemMiddleware** - Persistent Backend
   - Conversations saved to `.deepagents/` directory
   - Automatic state persistence
   - Easy conversation recovery
   - Filesystem-backed conversation history

**Framework Comparison:**

| Feature | Standard (LangChain) | DeepAgents |
|---------|---------------------|------------|
| **Task Tracking** | Manual checklist | TodoListMiddleware (automatic) |
| **Context Management** | SharedContext (global) | SubAgentMiddleware (isolated) |
| **Token Overflow** | Manual handling | Auto-summarization at 170k |
| **Persistence** | Database (SQLite) | Filesystem + Database |
| **Middleware** | Custom implementation | Built-in stack |
| **Human-in-Loop** | Manual checkpoints | Built-in approval gates |

**How to Use:**

1. **Backend Setup:**
   ```bash
   # Install DeepAgents framework
   pip install deepagents

   # IMPORTANT: tavily-python is OPTIONAL
   # Only install if you have external API access
   # Skip in secure internal networks
   # pip install tavily-python
   ```

   **Note for Internal Networks:**
   - tavily-python provides web search capabilities
   - Requires external API access (not available in secure networks)
   - DeepAgents works without tavily (SubAgent & Filesystem middleware only)

2. **Frontend - Select Framework:**
   - Click the framework selector in the header (gear icon)
   - Choose between "Standard" or "DeepAgents"
   - Selection persists per session
   - Switch anytime without losing conversation state

3. **API Usage:**
   ```python
   # Select framework for session
   POST /framework/select?session_id={id}&framework=deepagents

   # Get current framework for session
   GET /framework/session/{session_id}
   ```

**Implementation Details:**

- **Backend:** `backend/app/agent/langchain/deepagent_workflow.py`
- **Routes:** `backend/app/api/routes.py` (lines 239-284, 315-343, 420-431)
- **Frontend UI:** `frontend/src/App.tsx` (framework selector dropdown)
- **API Client:** `frontend/src/api/client.ts` (selectFramework, getSessionFramework methods)

**Architecture Diagram:**
```
┌──────────────────────────────────────────────────────────────┐
│                      Workflow Execution                      │
├──────────────────────────────────────────────────────────────┤
│                                                              │
│  ┌─────────────────────┐      ┌──────────────────────────┐  │
│  │   Standard Mode     │      │    DeepAgents Mode       │  │
│  ├─────────────────────┤      ├──────────────────────────┤  │
│  │ - Manual Context    │      │ - TodoListMiddleware     │  │
│  │ - SharedContext     │      │ - SubAgentMiddleware     │  │
│  │ - Manual Tracking   │      │ - SummarizationMW        │  │
│  │ - Database Persist  │      │ - FilesystemMW           │  │
│  └──────────┬──────────┘      └────────────┬─────────────┘  │
│             │                              │                │
│             └──────────┬───────────────────┘                │
│                        ▼                                    │
│              ┌──────────────────┐                           │
│              │  Common Workflow  │                           │
│              │  - Planning       │                           │
│              │  - Coding         │                           │
│              │  - Review         │                           │
│              └──────────────────┘                           │
└──────────────────────────────────────────────────────────────┘
```

**Migration Path:**

Existing sessions using standard framework continue to work. New features:
- Per-session framework selection
- Gradual migration supported
- Both frameworks can run concurrently
- No breaking changes to existing API

**Performance Considerations:**

- **Standard:** Lower overhead, faster startup
- **DeepAgents:** Higher overhead, better for complex multi-step tasks
- **Recommendation:** Use Standard for simple tasks, DeepAgents for complex workflows

## 📚 References

- [Microsoft Agent Framework](https://github.com/microsoft/agent-framework)
- [LangChain Documentation](https://python.langchain.com)
- [LangGraph Documentation](https://langchain-ai.github.io/langgraph)
- [DeepAgents Framework](https://github.com/langchain-ai/deepagents)
- [vLLM Documentation](https://docs.vllm.ai)
- [FastAPI Documentation](https://fastapi.tiangolo.com)
- [React Documentation](https://react.dev)

## 📄 License

MIT License - see LICENSE file for details

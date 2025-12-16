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
- 🎨 **Claude.ai Inspired UI**: Modern, clean design with warm color palette
- 💬 **Chat Mode**: Interactive conversation with the coding agent
- 🔄 **Workflow Mode**: Multi-agent pipeline (Planning → Coding → Review)
- 📱 **Responsive Design**: Works on desktop and mobile

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

## 📚 References

- [Microsoft Agent Framework](https://github.com/microsoft/agent-framework)
- [LangChain Documentation](https://python.langchain.com)
- [LangGraph Documentation](https://langchain-ai.github.io/langgraph)
- [vLLM Documentation](https://docs.vllm.ai)
- [FastAPI Documentation](https://fastapi.tiangolo.com)
- [React Documentation](https://react.dev)

## 📄 License

MIT License - see LICENSE file for details

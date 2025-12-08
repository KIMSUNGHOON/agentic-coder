# Coding Agent - Full Stack AI Assistant

A full-stack coding agent powered by Microsoft Agent Framework and vLLM, featuring React frontend and FastAPI backend.

## 🏗️ Architecture

```
┌─────────────────┐
│  React Frontend │ (Port 3000/80)
│   - Chat UI     │
│   - Code Display│
└────────┬────────┘
         │ REST API
         ▼
┌─────────────────┐
│  FastAPI Server │ (Port 8000)
│   - API Gateway │
│   - Agent Mgmt  │
└────────┬────────┘
         │
         ▼
┌─────────────────────────────┐
│ Microsoft Agent Framework   │
│  - Agent Orchestration      │
│  - OpenAI Client (Custom)   │
└───────┬──────────┬──────────┘
        │          │
        ▼          ▼
┌───────────┐  ┌───────────┐
│ vLLM #1   │  │ vLLM #2   │
│ DeepSeek  │  │ Qwen3     │
│ R1        │  │ Coder     │
│ (Port     │  │ (Port     │
│  8001)    │  │  8002)    │
└───────────┘  └───────────┘
```

## 📋 Features

- 🤖 **Dual Model Support**: DeepSeek-R1 for reasoning, Qwen3-Coder for code generation
- 💬 **Interactive Chat Interface**: Real-time conversation with the agent
- 🌊 **Streaming Responses**: Option for streaming or batch responses
- 📊 **Agent Status Monitoring**: Live status and model information
- 🎨 **Modern UI**: Built with React, TypeScript, and TailwindCSS
- 🔄 **Session Management**: Persistent conversation history per session
- 🐳 **Docker Support**: Easy deployment with Docker Compose
- 🐍 **Conda Support**: Alternative setup using Conda/Miniconda environments

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

You can set up the development environment using either **pip/venv** or **Conda**. Choose the method that works best for you.

---

#### Option 1: Using Conda (Recommended for Data Scientists)

**Prerequisites:** Conda or Miniconda installed, Python 3.12 environment

📘 **Detailed installation guide:** See [INSTALL_CONDA.md](INSTALL_CONDA.md) for comprehensive instructions.

**Quick Start - Using Existing Environment:**

```bash
# Activate your existing conda environment (with Python 3.12)
conda activate <your-env-name>

# Install backend dependencies
cd backend
pip install -r requirements.txt

# Setup environment file
cp .env.example .env
# Edit .env to configure vLLM endpoints

# Install frontend dependencies
cd ../frontend
npm install

# Run backend (Terminal 1)
cd ../backend
uvicorn app.main:app --host 0.0.0.0 --port 8000 --reload

# Run frontend (Terminal 2)
cd frontend
npm run dev
```

**Create New Environment (Optional):**

If you don't have a conda environment yet, you can create one:

```bash
# Option A: Create from environment.yml (includes Python 3.12 + Node.js 20)
conda env create -f environment.yml
conda activate coding-agent

# Option B: Backend-only environment
cd backend
conda env create -f environment.yml
conda activate coding-agent-backend

# Then follow the Quick Start steps above
```

**Convenience Script:**

```bash
# Run entire stack with one command (requires 'coding-agent' environment)
./run_conda.sh
```

---

#### Option 2: Using pip/venv

**Backend:**

```bash
cd backend

# Create virtual environment
python -m venv venv
source venv/bin/activate  # On Windows: venv\Scripts\activate

# Install dependencies
pip install -r requirements.txt

# Copy and configure environment
cp .env.example .env
# Edit .env if needed to match your vLLM endpoints

# Run the server
uvicorn app.main:app --host 0.0.0.0 --port 8000 --reload
```

Or use the dev script:
```bash
cd backend
./run_dev.sh
```

**Frontend:**

```bash
cd frontend

# Install dependencies
npm install

# Start development server
npm run dev
```

The frontend will be available at http://localhost:3000

### Production Deployment with Docker

```bash
# Make sure vLLM servers are running on host machine

# Copy environment file
cp .env.example .env

# Build and start services
docker-compose up -d

# View logs
docker-compose logs -f

# Stop services
docker-compose down
```

The application will be available at:
- Frontend: http://localhost
- Backend API: http://localhost:8000
- API Documentation: http://localhost:8000/docs

## 📁 Project Structure

```
TestCodeAgent/
├── backend/
│   ├── app/
│   │   ├── main.py              # FastAPI entry point
│   │   ├── core/
│   │   │   └── config.py        # Configuration management
│   │   ├── api/
│   │   │   ├── routes.py        # API endpoints
│   │   │   └── models.py        # Pydantic models
│   │   ├── agent/
│   │   │   └── agent_manager.py # Agent Framework integration
│   │   └── services/
│   │       └── vllm_client.py   # vLLM client & router
│   ├── requirements.txt         # pip dependencies
│   ├── environment.yml          # Conda environment (backend only, Python 3.12)
│   ├── Dockerfile
│   └── run_dev.sh              # pip/venv dev script
├── frontend/
│   ├── src/
│   │   ├── components/
│   │   │   ├── ChatInterface.tsx
│   │   │   ├── ChatMessage.tsx
│   │   │   └── AgentStatus.tsx
│   │   ├── api/
│   │   │   └── client.ts        # API client
│   │   ├── types/
│   │   │   └── api.ts           # TypeScript types
│   │   ├── App.tsx
│   │   └── main.tsx
│   ├── package.json
│   ├── Dockerfile
│   └── nginx.conf
├── environment.yml              # Conda environment (full stack, Python 3.12)
├── run_conda.sh                # Run full stack with Conda
├── docker-compose.yml
├── INSTALL_CONDA.md            # Detailed Conda installation guide
├── .env.example
└── README.md
```

## 🔧 Configuration

### Environment Variables

Create a `.env` file in the backend directory:

```env
# vLLM Endpoints
VLLM_REASONING_ENDPOINT=http://localhost:8001/v1
VLLM_CODING_ENDPOINT=http://localhost:8002/v1

# Model names
REASONING_MODEL=deepseek-ai/DeepSeek-R1
CODING_MODEL=Qwen/Qwen3-8B-Coder

# API Configuration
API_HOST=0.0.0.0
API_PORT=8000
CORS_ORIGINS=http://localhost:3000,http://localhost:5173

# Logging
LOG_LEVEL=INFO
```

## 🐍 Conda Environment Management

📘 **See [INSTALL_CONDA.md](INSTALL_CONDA.md) for detailed installation and setup instructions.**

### Available Conda Environments

**Full Stack Environment (`coding-agent`):**
- Includes Python 3.12, Node.js 20, and all backend dependencies
- Best for running both frontend and backend
- File: `environment.yml`

**Backend Only Environment (`coding-agent-backend`):**
- Includes Python 3.12 and backend dependencies only
- Best for API development
- File: `backend/environment.yml`

### Quick Installation

**Using Existing Environment:**
```bash
# Activate your conda environment (must have Python 3.12)
conda activate <your-env-name>

# Install dependencies
cd backend && pip install -r requirements.txt
cd ../frontend && npm install
```

**Create New Environment:**
```bash
# Full stack
conda env create -f environment.yml
conda activate coding-agent

# Backend only
cd backend
conda env create -f environment.yml
conda activate coding-agent-backend
```

### Common Conda Commands

```bash
# List all conda environments
conda env list

# Activate environment
conda activate coding-agent

# Deactivate environment
conda deactivate

# Update environment from YAML file
conda env update -f environment.yml --prune

# Remove environment
conda env remove -n coding-agent

# Export current environment
conda env export > environment_snapshot.yml

# View installed packages
conda list
```

### Updating Dependencies

**Update backend dependencies:**
```bash
conda activate <your-env-name>
cd backend
pip install -r requirements.txt --upgrade
```

**Update frontend dependencies:**
```bash
cd frontend
npm update
```

## 🎯 API Endpoints

### Chat

- `POST /api/chat` - Send a message (non-streaming)
- `POST /api/chat/stream` - Send a message (streaming)

### Agent Management

- `GET /api/agent/status/{session_id}` - Get agent status
- `POST /api/agent/clear/{session_id}` - Clear conversation history
- `DELETE /api/agent/session/{session_id}` - Delete session
- `GET /api/agent/sessions` - List active sessions

### Models

- `GET /api/models` - List available models
- `GET /health` - Health check

### Example Request

```bash
curl -X POST http://localhost:8000/api/chat \
  -H "Content-Type: application/json" \
  -d '{
    "message": "Write a Python function to calculate fibonacci numbers",
    "session_id": "test-session",
    "task_type": "coding"
  }'
```

## 🛠️ Technology Stack

### Backend
- **FastAPI** - Modern Python web framework
- **Microsoft Agent Framework** - Agent orchestration
- **OpenAI Python SDK** - vLLM communication
- **Pydantic** - Data validation
- **Uvicorn** - ASGI server

### Frontend
- **React 18** - UI framework
- **TypeScript** - Type safety
- **Vite** - Build tool
- **TailwindCSS** - Styling
- **Axios** - HTTP client
- **React Markdown** - Markdown rendering
- **React Syntax Highlighter** - Code highlighting

### Infrastructure
- **Docker & Docker Compose** - Containerization
- **Nginx** - Frontend serving & reverse proxy

## 🔄 Task Types

### Coding Mode (Qwen3-Coder)
Best for:
- Code generation
- Code fixes and debugging
- Code explanation
- Refactoring suggestions

### Reasoning Mode (DeepSeek-R1)
Best for:
- Complex problem solving
- Algorithm design
- Architecture decisions
- Planning and analysis

## 📝 Development

### Running Tests

```bash
# Backend
cd backend
pytest

# Frontend
cd frontend
npm test
```

### Building for Production

```bash
# Backend
cd backend
pip install -r requirements.txt

# Frontend
cd frontend
npm run build
```

## 🐛 Troubleshooting

### vLLM Connection Issues

If the backend can't connect to vLLM:

1. Verify vLLM servers are running:
   ```bash
   curl http://localhost:8001/v1/models
   curl http://localhost:8002/v1/models
   ```

2. Check firewall settings
3. Verify environment variables in `.env`

### Docker Networking

When running in Docker, vLLM endpoints should use `host.docker.internal`:

```env
VLLM_REASONING_ENDPOINT=http://host.docker.internal:8001/v1
VLLM_CODING_ENDPOINT=http://host.docker.internal:8002/v1
```

## 📄 License

MIT License - see LICENSE file for details

## 🤝 Contributing

Contributions are welcome! Please feel free to submit a Pull Request.

## 📚 References

- [Microsoft Agent Framework](https://github.com/microsoft/agent-framework)
- [vLLM Documentation](https://docs.vllm.ai)
- [FastAPI Documentation](https://fastapi.tiangolo.com)
- [React Documentation](https://react.dev)

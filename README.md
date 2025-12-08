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

## 🚀 Quick Start

### Prerequisites

1. **vLLM servers running** (required before starting the app):
   ```bash
   # Terminal 1: Start DeepSeek-R1 for reasoning
   vllm serve deepseek-ai/DeepSeek-R1 --port 8001

   # Terminal 2: Start Qwen3-Coder for coding
   vllm serve Qwen/Qwen3-8B-Coder --port 8002
   ```

2. **Python 3.11+** and **Node.js 20+** installed

### Development Setup

#### Backend

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

#### Frontend

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
│   ├── requirements.txt
│   ├── Dockerfile
│   └── run_dev.sh
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
├── docker-compose.yml
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

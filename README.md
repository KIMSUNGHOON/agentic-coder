# Coding Agent - Full Stack AI Assistant

Claude Code / OpenAI Codex 방식의 **Unified Workflow Architecture**를 구현한 AI 코딩 어시스턴트입니다.

## 🏗️ Architecture

```
User Prompt
    │
    ▼
┌─────────────────────────────────────────────────────────────────┐
│                    Unified Chat Endpoint                         │
│                    POST /chat/unified                            │
└─────────────────────────────────────────────────────────────────┘
    │
    ▼
┌─────────────────────────────────────────────────────────────────┐
│                    UnifiedAgentManager                           │
│  - 세션 컨텍스트 관리                                              │
│  - Supervisor 분석 요청                                           │
│  - 응답 타입별 라우팅                                             │
└─────────────────────────────────────────────────────────────────┘
    │
    ▼
┌─────────────────────────────────────────────────────────────────┐
│                    SupervisorAgent                               │
│  - 요청 분석 (Reasoning LLM)                                     │
│  - response_type 결정                                            │
│  - 복잡도 평가                                                    │
└─────────────────────────────────────────────────────────────────┘
    │
    ├─► QUICK_QA ─────────► Direct LLM Response
    ├─► PLANNING ─────────► PlanningHandler (계획 생성 + 파일 저장)
    ├─► CODE_GENERATION ──► CodeGenerationHandler (워크플로우 실행)
    ├─► CODE_REVIEW ──────► CodeReviewHandler
    └─► DEBUGGING ────────► DebuggingHandler
    │
    ▼
┌─────────────────────────────────────────────────────────────────┐
│                    ResponseAggregator                            │
│  - UnifiedResponse 생성                                          │
│  - Next Actions 제안                                             │
│  - 컨텍스트 DB 저장                                               │
└─────────────────────────────────────────────────────────────────┘
```

## 📋 Features

### Unified Workflow Architecture
- **단일 진입점**: 모든 요청이 Supervisor를 통과
- **지능적 라우팅**: 요청 유형에 따른 자동 경로 결정 (QUICK_QA, PLANNING, CODE_GENERATION 등)
- **통합 응답 포맷**: 모든 경로에서 동일한 응답 구조
- **컨텍스트 영속성**: 대화 및 작업 컨텍스트 DB 저장
- **Next Actions UI**: 응답 타입별 맞춤형 다음 행동 제안

### LLM Provider Abstraction
- **다중 모델 지원**: DeepSeek-R1, Qwen3-Coder, GPT-OSS
- **모델별 어댑터**: 자동 프롬프트 최적화
- **한국어 지원**: 동사 어간 기반 패턴 매칭

### User Interface
- **Claude.ai 스타일**: 깔끔한 대화형 인터페이스
- **실시간 스트리밍**: 코드 생성 과정 실시간 표시
- **계획 파일 뷰어**: 복잡한 작업 계획 미리보기
- **반응형 디자인**: 데스크톱/모바일 지원

## 🚀 Quick Start

### Prerequisites

1. **vLLM 서버** (앱 시작 전 실행 필요):
   ```bash
   # Terminal 1: Reasoning Model
   vllm serve deepseek-ai/DeepSeek-R1 --port 8001

   # Terminal 2: Coding Model
   vllm serve Qwen/Qwen3-8B-Coder --port 8002
   ```

2. **Python 3.12** and **Node.js 20+**

### Development Setup

```bash
# 1. 환경 설정
cp .env.example .env
# .env 파일에서 설정:
#   - LLM 엔드포인트 (VLLM_REASONING_ENDPOINT, VLLM_CODING_ENDPOINT)
#   - Workspace 디렉토리 (DEFAULT_WORKSPACE)
#
# 예시:
# DEFAULT_WORKSPACE=/home/username/Workspaces/TestCode
# → 프로젝트는 /home/username/Workspaces/TestCode/{session_id}/{project_name}에 저장됩니다

# 2. Backend
cd backend
python -m venv venv
source venv/bin/activate  # Windows: venv\Scripts\activate
pip install -r requirements.txt
uvicorn app.main:app --host 0.0.0.0 --port 8000 --reload

# 3. Frontend
cd frontend
npm install
npm run dev
```

Frontend: http://localhost:5173

### Mock Mode (vLLM 없이 테스트)

```bash
./RUN_MOCK.sh  # 또는 Windows: RUN_MOCK.bat
```

## 📁 Project Structure

```
TestCodeAgent/
├── backend/
│   ├── app/
│   │   ├── main.py                         # FastAPI entry point
│   │   ├── agent/
│   │   │   ├── unified_agent_manager.py    # 통합 에이전트 매니저
│   │   │   └── handlers/                   # 응답 타입별 핸들러
│   │   └── api/
│   │       └── main_routes.py              # /chat/unified 엔드포인트
│   ├── core/
│   │   ├── supervisor.py                   # SupervisorAgent
│   │   ├── response_aggregator.py          # UnifiedResponse
│   │   └── context_store.py                # 컨텍스트 저장소
│   └── shared/
│       └── llm/
│           ├── base.py                     # LLMProvider 인터페이스
│           └── adapters/                   # 모델별 어댑터
├── frontend/
│   └── src/
│       ├── components/
│       │   ├── WorkflowInterface.tsx       # Unified 모드 UI
│       │   ├── NextActionsPanel.tsx        # 다음 행동 버튼
│       │   └── PlanFileViewer.tsx          # 계획 파일 뷰어
│       └── api/
│           └── client.ts                   # API 클라이언트
└── docs/                                   # 기술 문서
```

## 🎯 API Endpoints

### Unified Chat (Non-streaming)
```
POST /chat/unified
```

```json
// Request
{
  "message": "Python으로 계산기 만들어줘",
  "session_id": "session-123",
  "workspace": "/home/user/workspace"
}

// Response
{
  "response_type": "code_generation",
  "content": "## 코드 생성 완료\n\n...",
  "artifacts": [...],
  "next_actions": ["테스트 실행", "코드 리뷰 요청"],
  "session_id": "session-123",
  "success": true
}
```

### Unified Chat (Streaming)
```
POST /chat/unified/stream
```

## 🔧 Configuration

### Environment Variables

```env
# Primary LLM
LLM_ENDPOINT=http://localhost:8001/v1
LLM_MODEL=deepseek-ai/DeepSeek-R1
MODEL_TYPE=deepseek  # deepseek, qwen, gpt-oss, generic

# Optional: Task-specific endpoints
VLLM_REASONING_ENDPOINT=http://localhost:8001/v1
VLLM_CODING_ENDPOINT=http://localhost:8002/v1
REASONING_MODEL=deepseek-ai/DeepSeek-R1
CODING_MODEL=Qwen/Qwen3-8B-Coder

# Server
API_HOST=0.0.0.0
API_PORT=8000
CORS_ORIGINS=http://localhost:3000,http://localhost:5173
```

## 📚 Documentation

| 문서 | 설명 |
|------|------|
| [ARCHITECTURE.md](docs/ARCHITECTURE.md) | 시스템 아키텍처 상세 |
| [MOCK_MODE.md](docs/MOCK_MODE.md) | Mock 모드 테스트 가이드 |
| [MULTI_USER_ANALYSIS.md](docs/MULTI_USER_ANALYSIS.md) | 다중 사용자 동시 접속 분석 |
| [OPTIMIZATION_RECOMMENDATIONS.md](docs/OPTIMIZATION_RECOMMENDATIONS.md) | H100 GPU 최적화 권장사항 |
| [REFINEMENT_CYCLE_GUIDE.md](docs/REFINEMENT_CYCLE_GUIDE.md) | 코드 개선 워크플로우 가이드 |
| [INSTALL_CONDA.md](INSTALL_CONDA.md) | Conda 환경 설치 가이드 |

### Archive (완료된 작업 문서)
| 문서 | 설명 |
|------|------|
| [LLM_MODEL_CHANGE_PLAN.md](docs/archive/LLM_MODEL_CHANGE_PLAN.md) | LLM 추상화 계층 구현 완료 |
| [AGENT_COMPATIBILITY_AUDIT.md](docs/archive/AGENT_COMPATIBILITY_AUDIT.md) | 프롬프트 호환성 감사 완료 |
| [IMPROVEMENT_PLAN.md](docs/archive/IMPROVEMENT_PLAN.md) | 시스템 개선 Phase 1&2 완료 |
| [AGENT_EXPANSION_PROPOSAL.md](docs/archive/AGENT_EXPANSION_PROPOSAL.md) | 에이전트 확장 제안서 |

## 🎨 UI Design

Claude.ai 스타일 디자인:

| Element | Color |
|---------|-------|
| Background | `#FAF9F7` (warm off-white) |
| Accent | `#DA7756` (terracotta) |
| Text Primary | `#1A1A1A` |
| Text Secondary | `#666666` |

## 🛠️ Supported LLM Models

| 모델 | 특징 | 프롬프트 형식 |
|------|------|---------------|
| DeepSeek-R1 | 추론 모델 | `<think></think>` 태그 |
| Qwen3-Coder | 코딩 특화 | Standard prompts |
| GPT-OSS | OpenAI Harmony | Structured reasoning |

## 📄 License

MIT License - see LICENSE file for details

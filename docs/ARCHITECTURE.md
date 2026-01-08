# Agentic Coder 시스템 아키텍처

**버전**: 2.2
**최종 업데이트**: 2026-01-09

---

## 1. 시스템 개요

Agentic Coder는 **Claude Code / OpenAI Codex 방식**의 통합 워크플로우 아키텍처를 구현한 AI 코딩 어시스턴트입니다.

### 1.1 핵심 설계 원칙

1. **단일 진입점**: 모든 요청이 Supervisor를 통과
2. **지능적 라우팅**: 요청 유형에 따른 자동 경로 결정
3. **통합 응답 포맷**: 모든 경로에서 동일한 응답 구조
4. **컨텍스트 영속성**: 대화 및 작업 컨텍스트 DB 저장
5. **사용자 친화적 출력**: 내부 분석이 아닌 사용자용 응답

---

## 2. 아키텍처 다이어그램

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
│  - 세션 컨텍스트 로드                                             │
│  - Supervisor 분석 요청                                           │
│  - 응답 타입별 라우팅                                             │
└─────────────────────────────────────────────────────────────────┘
    │
    ▼
┌─────────────────────────────────────────────────────────────────┐
│                    SupervisorAgent                               │
│  - 요청 분석 (Reasoning LLM)                                     │
│  - response_type 결정                                            │
│  - 필요 에이전트 결정                                             │
│  - 복잡도 평가                                                    │
└─────────────────────────────────────────────────────────────────┘
    │
    ├─► QUICK_QA ─────────► Direct LLM Response
    │                        (간단한 질문 답변)
    │
    ├─► PLANNING ─────────► PlanningHandler
    │                        ├─► 계획 생성 (LLM)
    │                        ├─► 사용자 응답 생성
    │                        └─► 계획 파일 저장 (옵션)
    │
    ├─► CODE_GENERATION ──► CodeGenerationHandler
    │                        ├─► Dynamic Workflow 실행
    │                        ├─► Architect → Coder → Review
    │                        └─► Artifacts 생성
    │
    ├─► CODE_REVIEW ──────► CodeReviewHandler
    │                        ├─► 코드 분석
    │                        └─► 리뷰 피드백 생성
    │
    └─► DEBUGGING ────────► DebuggingHandler
                             ├─► RCA 분석
                             └─► 수정 제안
    │
    ▼
┌─────────────────────────────────────────────────────────────────┐
│                    ResponseAggregator                            │
│  - 스트리밍 업데이트 수집                                         │
│  - 최종 UnifiedResponse 생성                                     │
│  - Artifacts 첨부                                                │
│  - 컨텍스트 저장                                                  │
└─────────────────────────────────────────────────────────────────┘
```

---

## 3. 핵심 컴포넌트

### 3.1 UnifiedAgentManager

**파일**: `backend/app/agent/unified_agent_manager.py`

모든 요청의 통합 처리 + 컨텍스트 관리를 담당합니다.

```python
class UnifiedAgentManager:
    def __init__(self):
        self.supervisor = SupervisorAgent(use_api=True)
        self.context_store = ContextStore()
        self.response_aggregator = ResponseAggregator()
        self.handlers = {
            ResponseType.QUICK_QA: QuickQAHandler(),
            ResponseType.PLANNING: PlanningHandler(),
            ResponseType.CODE_GENERATION: CodeGenerationHandler(),
            # ...
        }
```

### 3.2 Response Type Handlers

**파일**: `backend/app/agent/handlers/`

| 핸들러 | 역할 |
|--------|------|
| `QuickQAHandler` | 간단한 질문-답변 처리 |
| `PlanningHandler` | 계획 수립 + 파일 저장 |
| `CodeGenerationHandler` | 전체 워크플로우 실행 |
| `CodeReviewHandler` | 코드 분석 및 리뷰 |
| `DebuggingHandler` | RCA 분석 및 수정 제안 |

### 3.3 ContextStore

**파일**: `backend/core/context_store.py`

- SQLAlchemy를 통한 대화 컨텍스트 DB 저장
- 메모리 캐시 + DB 영속성 하이브리드 방식
- 저장 데이터: 메시지, 아티팩트, 분석 결과, 워크스페이스

---

## 4. API 엔드포인트

### 4.1 통합 채팅 (비스트리밍)

```
POST /chat/unified
```

**Request:**
```json
{
  "message": "Python으로 계산기 만들어줘",
  "session_id": "session-123",
  "workspace": "/home/user/workspace/calculator"
}
```

**Response:**
```json
{
  "response_type": "code_generation",
  "content": "## 코드 생성 완료\n\n다음 파일들이 생성되었습니다...",
  "artifacts": [...],
  "plan_file": null,
  "analysis": {
    "complexity": "moderate",
    "task_type": "implementation",
    "required_agents": ["coder", "reviewer"],
    "confidence": 0.85
  },
  "next_actions": ["테스트 실행", "코드 리뷰 요청", "추가 기능 구현"],
  "session_id": "session-123",
  "success": true
}
```

### 4.2 통합 채팅 (스트리밍)

```
POST /chat/unified/stream
```

**Response:** Server-Sent Events
```
data: {"agent": "Supervisor", "type": "analysis", "status": "completed", ...}
data: {"agent": "CodeGenerationHandler", "type": "progress", ...}
data: {"agent": "Coder", "type": "artifact", ...}
data: {"agent": "UnifiedAgentManager", "type": "done", ...}
data: [DONE]
```

---

## 5. LLM Provider 구조

### 5.1 지원 모델

| 모델 | 특징 | 프롬프트 형식 |
|------|------|---------------|
| DeepSeek-R1 | 추론 모델 | `<think></think>` 태그 |
| Qwen3 | 범용 코딩 모델 | Standard prompts |
| GPT-OSS | OpenAI Harmony 포맷 | Structured reasoning |

### 5.2 어댑터 구조

```
shared/llm/
├── base.py              # BaseLLMProvider 추상 클래스
└── adapters/
    ├── deepseek_adapter.py
    ├── gpt_oss_adapter.py
    ├── qwen_adapter.py
    └── generic_adapter.py
```

---

## 6. 프론트엔드 컴포넌트

### 6.1 Unified 모드 지원

| 컴포넌트 | 파일 | 역할 |
|----------|------|------|
| WorkflowInterface | `WorkflowInterface.tsx` | Unified 모드 메인 UI |
| NextActionsPanel | `NextActionsPanel.tsx` | 다음 행동 버튼 UI |
| PlanFileViewer | `PlanFileViewer.tsx` | 계획 파일 미리보기 모달 |

### 6.2 Next Actions 기능

응답 타입별 맞춤형 다음 행동 제안:

| 응답 타입 | 제안 행동 |
|-----------|-----------|
| QUICK_QA | "추가 질문하기" |
| PLANNING | "코드 생성 시작", "계획 수정 요청", "계획 파일 확인" |
| CODE_GENERATION | "테스트 실행", "코드 리뷰 요청", "추가 기능 구현" |
| CODE_REVIEW | "수정 사항 적용", "추가 리뷰 요청" |
| DEBUGGING | "수정 사항 적용", "테스트 실행" |

---

## 7. 데이터 흐름

```
┌──────────────────────────────────────────────────────────────────┐
│                        Frontend (React)                          │
│  ┌────────────┐    ┌────────────┐    ┌────────────────────────┐  │
│  │ ChatInput  │───►│ API Client │───►│ WorkflowInterface      │  │
│  └────────────┘    └────────────┘    │ - NextActionsPanel     │  │
│                                      │ - PlanFileViewer       │  │
│                                      └────────────────────────┘  │
└──────────────────────────────────────────────────────────────────┘
                              │
                              ▼
┌──────────────────────────────────────────────────────────────────┐
│                     Backend (FastAPI)                            │
│  ┌────────────────┐    ┌────────────────────────────────────┐    │
│  │  main_routes   │───►│     UnifiedAgentManager            │    │
│  │/chat/unified   │    │  ┌──────────────────────────────┐  │    │
│  │/chat/unified/  │    │  │     SupervisorAgent          │  │    │
│  │       stream   │    │  │  - analyze_request_async()   │  │    │
│  └────────────────┘    │  └──────────────────────────────┘  │    │
│                        │                  │                 │    │
│                        │     ┌────────────┴────────────┐    │    │
│                        │     ▼            ▼            ▼    │    │
│                        │  QuickQA    Planning    CodeGen    │    │
│                        │  Handler    Handler     Handler    │    │
│                        └────────────────────────────────────┘    │
│                                      │                           │
│                                      ▼                           │
│                        ┌────────────────────────────────────┐    │
│                        │         ContextStore (DB)          │    │
│                        │   - messages, artifacts            │    │
│                        │   - analysis, workspace            │    │
│                        └────────────────────────────────────┘    │
└──────────────────────────────────────────────────────────────────┘
                              │
                              ▼
┌──────────────────────────────────────────────────────────────────┐
│                     LLM Layer (vLLM)                             │
│  ┌──────────────┐  ┌──────────────┐  ┌──────────────────────┐    │
│  │ DeepSeek-R1  │  │   GPT-OSS    │  │    Qwen3-Coder       │    │
│  │  (Reasoning) │  │  (General)   │  │     (Coding)         │    │
│  │   Port 8001  │  │   Port 8001  │  │    Port 8002         │    │
│  └──────────────┘  └──────────────┘  └──────────────────────┘    │
└──────────────────────────────────────────────────────────────────┘
```

---

## 8. 파일 구조

```
backend/
├── app/
│   ├── agent/
│   │   ├── unified_agent_manager.py    # 통합 에이전트 매니저
│   │   └── handlers/
│   │       ├── base.py                 # BaseHandler 추상 클래스
│   │       ├── quick_qa.py             # QUICK_QA 핸들러
│   │       ├── planning.py             # PLANNING 핸들러
│   │       └── code_generation.py      # CODE_GENERATION 핸들러
│   └── api/
│       └── main_routes.py              # /chat/unified 엔드포인트
├── core/
│   ├── supervisor.py                   # SupervisorAgent
│   ├── response_aggregator.py          # UnifiedResponse 정의
│   └── context_store.py                # 컨텍스트 저장소
└── shared/
    └── llm/
        ├── base.py                     # LLMProvider 인터페이스
        └── adapters/                   # 모델별 어댑터

frontend/
├── src/
│   ├── api/
│   │   └── client.ts                   # unifiedChat(), unifiedChatStream()
│   ├── components/
│   │   ├── WorkflowInterface.tsx       # Unified 모드 UI
│   │   ├── NextActionsPanel.tsx        # 다음 행동 버튼
│   │   └── PlanFileViewer.tsx          # 계획 파일 뷰어
│   └── types/
│       └── api.ts                      # UnifiedChatResponse 타입
```

---

## 9. Plan Mode 아키텍처 (Phase 5)

### 9.1 Plan Mode 개요

Plan Mode는 코드 생성 전 사용자 승인 기반의 계획 수립 단계를 제공합니다.

```
User Request
    │
    ▼
┌─────────────────────────────────────────────────────────────────┐
│                    Plan Generation                               │
│  - PlanningHandler.generate_structured_plan()                   │
│  - JSON 형식 실행 계획 생성                                       │
│  - 단계별 작업, 영향 파일, 위험 요소 분석                         │
└─────────────────────────────────────────────────────────────────┘
    │
    ▼
┌─────────────────────────────────────────────────────────────────┐
│                    User Approval                                 │
│  - PlanApprovalModal 컴포넌트                                    │
│  - Approve / Modify / Reject 선택                               │
│  - 단계별 승인 요구사항 설정 가능                                 │
└─────────────────────────────────────────────────────────────────┘
    │
    ▼
┌─────────────────────────────────────────────────────────────────┐
│                    Step-by-step Execution                        │
│  - PlanExecutor 노드                                            │
│  - 단계별 진행 상황 추적                                         │
│  - HITL 통합 (승인 필요 단계)                                    │
│  - 오류 시 롤백/건너뛰기 옵션                                    │
└─────────────────────────────────────────────────────────────────┘
```

### 9.2 Plan Mode 컴포넌트

| 컴포넌트 | 파일 | 역할 |
|----------|------|------|
| `ExecutionPlan` | `backend/app/agent/langgraph/schemas/plan.py` | 실행 계획 스키마 |
| `PlanStep` | `backend/app/agent/langgraph/schemas/plan.py` | 개별 단계 스키마 |
| `PlanningHandler` | `backend/app/agent/handlers/planning.py` | 구조화된 계획 생성 |
| `PlanExecutor` | `backend/app/agent/langgraph/nodes/plan_executor.py` | 단계별 실행 |
| `plan_routes` | `backend/app/api/routes/plan_routes.py` | Plan API 엔드포인트 |
| `PlanApprovalModal` | `frontend/src/components/PlanApprovalModal.tsx` | 계획 승인 UI |

### 9.3 Plan API 엔드포인트

| 엔드포인트 | 메서드 | 설명 |
|------------|--------|------|
| `/api/plan/generate` | POST | 실행 계획 생성 |
| `/api/plan/{plan_id}` | GET | 계획 상세 조회 |
| `/api/plan/{plan_id}/approve` | POST | 계획 승인 |
| `/api/plan/{plan_id}/modify` | POST | 단계 수정 |
| `/api/plan/{plan_id}/reject` | POST | 계획 거부 |
| `/api/plan/{plan_id}/execute` | POST | 실행 시작 |
| `/api/plan/{plan_id}/execute/stream` | GET | 실행 스트리밍 (SSE) |
| `/api/plan/{plan_id}/status` | GET | 실행 상태 조회 |

### 9.4 Plan 데이터 구조

```json
{
  "plan_id": "plan-abc12345",
  "session_id": "session-123",
  "user_request": "Python 계산기 만들어줘",
  "steps": [
    {
      "step": 1,
      "action": "create_file",
      "target": "src/calculator.py",
      "description": "계산기 모듈 생성",
      "requires_approval": false,
      "estimated_complexity": "low",
      "dependencies": [],
      "status": "pending"
    },
    {
      "step": 2,
      "action": "create_file",
      "target": "tests/test_calculator.py",
      "description": "유닛 테스트 생성",
      "requires_approval": false,
      "estimated_complexity": "low",
      "dependencies": [1],
      "status": "pending"
    }
  ],
  "estimated_files": ["src/calculator.py", "tests/test_calculator.py"],
  "risks": [],
  "approval_status": "pending",
  "total_steps": 2
}
```

---

## 10. Context Management 아키텍처 (Phase 6)

### 10.1 Context Management 개요

Phase 6에서 구현된 컨텍스트 관리 시스템은 대규모 코드베이스와 긴 대화에서 효율적인 컨텍스트 처리를 제공합니다.

```
User Message
    │
    ▼
┌─────────────────────────────────────────┐
│         Context Store                    │
│  - MAX_MESSAGES: 100                    │
│  - RECENT_MESSAGES_FOR_LLM: 30          │
│  - RECENT_MESSAGES_FOR_CONTEXT: 20      │
└─────────────────────────────────────────┘
    │
    ▼
┌─────────────────────────────────────────┐
│         Context Compressor               │
│  - Sliding window (20 recent msgs)      │
│  - Important content extraction         │
│  - ~34% token savings                   │
└─────────────────────────────────────────┘
    │
    ▼
┌─────────────────────────────────────────┐
│         Token Budget Manager             │
│  - Model-specific limits                │
│  - Context utilization tracking         │
│  - Overflow warnings                    │
└─────────────────────────────────────────┘
    │
    ▼
┌─────────────────────────────────────────┐
│         RAG Context Builder              │
│  - 7 code search results                │
│  - 5 conversation search results        │
│  - Compressed history integration       │
└─────────────────────────────────────────┘
```

### 10.2 주요 컴포넌트

| 컴포넌트 | 파일 | 설명 |
|----------|------|------|
| Token Utils | `shared/utils/token_utils.py` | 정확한 토큰 카운팅, 버짓 관리 |
| Context Compressor | `backend/core/context_compressor.py` | 스마트 컨텍스트 압축 |
| Context Store | `backend/core/context_store.py` | 확장된 컨텍스트 윈도우 |
| RAG Builder | `backend/app/services/rag_context.py` | RAG 통합 강화 |

### 10.3 압축 알고리즘

```python
# Context Compressor 동작 방식
입력: [msg1, msg2, ..., msg100]
        │
        ▼
┌─────────────────────────────────────────┐
│ 1. 최근 20개 메시지 유지                 │
│    [msg81, msg82, ..., msg100]          │
└─────────────────────────────────────────┘
        │
        ▼
┌─────────────────────────────────────────┐
│ 2. 나머지 메시지 분석                    │
│    - 코드 블록 추출 (CRITICAL)          │
│    - 파일명/경로 추출 (HIGH)            │
│    - 오류 메시지 추출 (CRITICAL)        │
│    - 결정 사항 추출 (MEDIUM)            │
└─────────────────────────────────────────┘
        │
        ▼
┌─────────────────────────────────────────┐
│ 3. 요약 메시지 생성                      │
│    [summary_msg] + [recent 20]          │
│    ~34% 토큰 절감                       │
└─────────────────────────────────────────┘
```

### 10.4 확장된 설정값

| 설정 | Phase 5 | Phase 6 | 개선율 |
|------|---------|---------|--------|
| MAX_MESSAGES | 50 | 100 | 100% |
| RECENT_MESSAGES_FOR_LLM | 20 | 30 | 50% |
| RECENT_MESSAGES_FOR_CONTEXT | 10 | 20 | 100% |
| MAX_ARTIFACTS | 20 | 50 | 150% |
| Handler content limit | 200 chars | 2000 chars | 900% |
| Supervisor content limit | 1000 chars | 4000 chars | 300% |
| RAG code results | 5 | 7 | 40% |
| RAG conversation results | 3 | 5 | 67% |
| RAG MAX_CONTEXT_LENGTH | 8000 | 12000 | 50% |

---

## 11. 관련 문서

| 문서 | 설명 |
|------|------|
| [ROADMAP.md](./ROADMAP.md) | 개발 로드맵 및 Phase 진행 상황 |
| [MOCK_MODE.md](./MOCK_MODE.md) | vLLM 없이 Mock 테스트 가이드 |
| [AGENT_TOOLS_PHASE2_README.md](./AGENT_TOOLS_PHASE2_README.md) | Agent Tools 문서 |
| [CLI_README.md](./CLI_README.md) | CLI 사용 가이드 |
| [SESSION_HANDOFF.md](./SESSION_HANDOFF.md) | 세션 인계 문서 |

---

*이 문서는 Agentic Coder의 핵심 아키텍처를 설명합니다.*

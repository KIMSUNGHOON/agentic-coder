# Unified Workflow Architecture Design

**작성일**: 2026-01-06
**버전**: 2.0 (구현 완료)
**목적**: Claude Code / OpenAI Codex 방식의 통합 워크플로우 아키텍처 설계
**상태**: ✅ 구현 완료

---

## 1. 현재 문제점 요약

### 1.1 핵심 문제

| 문제 | 현재 상태 | 영향 |
|------|----------|------|
| **분리된 경로** | `/chat`과 `/workflow/execute`가 완전 별개 | 사용자가 엔드포인트 선택 필요 |
| **Supervisor 미사용** | `/chat`이 Supervisor 완전 무시 | 지능적 라우팅 불가 |
| **응답 집계 없음** | 스트리밍만, 최종 응답 없음 | 프론트엔드가 재구성 필요 |
| **컨텍스트 손실** | 10개 메시지만 메모리 유지 | 복잡한 작업 컨텍스트 손실 |
| **응답 포맷 불일치** | 3가지 다른 포맷 | 프론트엔드 혼란 |

### 1.2 현재 흐름 (문제점)

```
User Prompt
    │
    ├──► /chat endpoint ──────────────────► LangChainAgent.process_message()
    │    (agent_manager.py)                      │
    │                                            ▼
    │                                     직접 LLM 호출 (Supervisor 없음)
    │                                            │
    │                                            ▼
    │                                     Plain Text 응답
    │                                     {"response": "...", "session_id": "..."}
    │
    └──► /workflow/execute endpoint ──────► WorkflowManager.execute_stream()
         (main_routes.py:304)                    │
                                                 ▼
                                           Supervisor 분석
                                                 │
                                                 ▼
                                           Workflow 실행 (스트리밍)
                                                 │
                                                 ▼
                                           JSON 이벤트 스트림 (최종 응답 없음)
```

---

## 2. 목표 아키텍처

### 2.1 설계 원칙

1. **단일 진입점**: 모든 요청이 Supervisor를 통과
2. **지능적 라우팅**: 요청 유형에 따른 자동 경로 결정
3. **통합 응답 포맷**: 모든 경로에서 동일한 응답 구조
4. **컨텍스트 영속성**: 대화 및 작업 컨텍스트 DB 저장
5. **사용자 친화적 출력**: 내부 분석이 아닌 사용자용 응답

### 2.2 목표 흐름

```
User Prompt
    │
    ▼
┌─────────────────────────────────────────────────────────────────┐
│                    Unified Chat Endpoint                         │
│                    POST /chat (통합)                              │
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
    │
    ▼
┌─────────────────────────────────────────────────────────────────┐
│                    UnifiedResponse                               │
│  {                                                               │
│    "response_type": "quick_qa|planning|code_generation|...",    │
│    "content": "사용자 친화적 응답 텍스트",                        │
│    "artifacts": [...],                                           │
│    "plan_file": "path/to/plan.md",  // optional                 │
│    "analysis": {...},               // supervisor analysis       │
│    "next_actions": [...],           // suggested follow-ups     │
│    "metadata": {...}                                             │
│  }                                                               │
└─────────────────────────────────────────────────────────────────┘
```

---

## 3. 컴포넌트 상세 설계

### 3.1 UnifiedAgentManager

**파일**: `backend/app/agent/unified_agent_manager.py` (신규)

**역할**: 모든 요청의 통합 처리 + 컨텍스트 관리

```python
class UnifiedAgentManager:
    """통합 에이전트 매니저 - 모든 요청을 Supervisor 통해 라우팅"""

    def __init__(self):
        self.supervisor = SupervisorAgent(use_api=True)
        self.context_store = ContextStore()  # DB 연동
        self.response_aggregator = ResponseAggregator()

        # 응답 타입별 핸들러
        self.handlers = {
            ResponseType.QUICK_QA: QuickQAHandler(),
            ResponseType.PLANNING: PlanningHandler(),
            ResponseType.CODE_GENERATION: CodeGenerationHandler(),
            ResponseType.CODE_REVIEW: CodeReviewHandler(),
            ResponseType.DEBUGGING: DebuggingHandler(),
        }

    async def process_request(
        self,
        session_id: str,
        user_message: str,
        workspace: Optional[str] = None,
        stream: bool = False
    ) -> Union[UnifiedResponse, AsyncGenerator]:
        """통합 요청 처리"""

        # 1. 컨텍스트 로드
        context = await self.context_store.load(session_id)

        # 2. Supervisor 분석
        analysis = await self.supervisor.analyze_request_async(
            user_message,
            context=context.to_dict()
        )

        # 3. 핸들러 선택 및 실행
        handler = self.handlers[analysis.response_type]

        if stream:
            # 스트리밍 모드
            return self._stream_response(handler, user_message, analysis, context)
        else:
            # 비스트리밍 모드
            result = await handler.execute(user_message, analysis, context)

            # 4. 응답 집계
            response = self.response_aggregator.aggregate(result, analysis)

            # 5. 컨텍스트 저장
            await self.context_store.save(session_id, context, analysis, response)

            return response
```

**인터페이스**:
```python
async def process_request(
    session_id: str,
    user_message: str,
    workspace: Optional[str] = None,
    stream: bool = False
) -> Union[UnifiedResponse, AsyncGenerator[StreamUpdate, None]]
```

---

### 3.2 ResponseType Handler 인터페이스

**파일**: `backend/app/agent/handlers/base.py` (신규)

```python
from abc import ABC, abstractmethod
from typing import Dict, Any, AsyncGenerator, Optional
from dataclasses import dataclass

@dataclass
class HandlerResult:
    """핸들러 실행 결과"""
    content: str                          # 사용자 응답 텍스트
    artifacts: List[Dict[str, Any]]       # 생성된 파일들
    plan_file: Optional[str] = None       # 저장된 계획 파일 경로
    metadata: Dict[str, Any] = None       # 추가 메타데이터


class BaseHandler(ABC):
    """응답 타입별 핸들러 베이스 클래스"""

    @abstractmethod
    async def execute(
        self,
        user_message: str,
        analysis: SupervisorAnalysis,
        context: ConversationContext
    ) -> HandlerResult:
        """핸들러 실행 (비스트리밍)"""
        pass

    @abstractmethod
    async def execute_stream(
        self,
        user_message: str,
        analysis: SupervisorAnalysis,
        context: ConversationContext
    ) -> AsyncGenerator[StreamUpdate, None]:
        """핸들러 실행 (스트리밍)"""
        pass
```

---

### 3.3 QuickQAHandler

**파일**: `backend/app/agent/handlers/quick_qa.py` (신규)

```python
class QuickQAHandler(BaseHandler):
    """간단한 질문-답변 처리"""

    def __init__(self):
        self.llm = ChatOpenAI(
            base_url=settings.vllm_coding_endpoint,
            model=settings.coding_model,
            temperature=0.7
        )

    async def execute(
        self,
        user_message: str,
        analysis: SupervisorAnalysis,
        context: ConversationContext
    ) -> HandlerResult:
        # 대화 히스토리 포함하여 LLM 호출
        messages = context.to_langchain_messages()
        messages.append(HumanMessage(content=user_message))

        response = await self.llm.ainvoke(messages)

        return HandlerResult(
            content=response.content,
            artifacts=[],
            metadata={"tokens_used": response.usage_metadata}
        )
```

---

### 3.4 PlanningHandler

**파일**: `backend/app/agent/handlers/planning.py` (신규)

```python
class PlanningHandler(BaseHandler):
    """계획 수립 처리 - 계획 생성 + 파일 저장"""

    def __init__(self):
        self.reasoning_llm = ChatOpenAI(
            base_url=settings.vllm_reasoning_endpoint,
            model=settings.reasoning_model,
            temperature=0.7
        )

    async def execute(
        self,
        user_message: str,
        analysis: SupervisorAnalysis,
        context: ConversationContext
    ) -> HandlerResult:
        # 1. 계획 생성 프롬프트 구성
        prompt = self._build_planning_prompt(user_message, analysis, context)

        # 2. LLM으로 계획 생성
        response = await self.reasoning_llm.ainvoke([
            SystemMessage(content=self._get_system_prompt()),
            HumanMessage(content=prompt)
        ])

        plan_content = response.content

        # 3. 사용자 친화적 응답 생성
        user_response = self._format_user_response(plan_content)

        # 4. 계획 파일 저장 (옵션)
        plan_file = None
        if analysis.complexity in [TaskComplexity.COMPLEX, TaskComplexity.CRITICAL]:
            plan_file = await self._save_plan_file(plan_content, context.workspace)

        return HandlerResult(
            content=user_response,
            artifacts=[],
            plan_file=plan_file,
            metadata={
                "complexity": analysis.complexity,
                "required_agents": analysis.required_agents
            }
        )

    def _format_user_response(self, plan_content: str) -> str:
        """내부 계획을 사용자 친화적 응답으로 변환"""
        # <think> 태그 제거, 마크다운 정리 등
        clean_content = re.sub(r'<think>.*?</think>', '', plan_content, flags=re.DOTALL)

        return f"""## 개발 계획

{clean_content}

---
다음 단계로 진행할까요? 계획을 수정하거나 코드 생성을 시작할 수 있습니다."""

    async def _save_plan_file(self, content: str, workspace: str) -> str:
        """계획을 마크다운 파일로 저장"""
        from datetime import datetime

        filename = f"PLAN_{datetime.now().strftime('%Y%m%d_%H%M%S')}.md"
        filepath = Path(workspace) / ".plans" / filename
        filepath.parent.mkdir(parents=True, exist_ok=True)

        async with aiofiles.open(filepath, 'w') as f:
            await f.write(content)

        return str(filepath)
```

---

### 3.5 CodeGenerationHandler

**파일**: `backend/app/agent/handlers/code_generation.py` (신규)

```python
class CodeGenerationHandler(BaseHandler):
    """코드 생성 처리 - 전체 워크플로우 실행"""

    def __init__(self):
        self.workflow_manager = get_workflow_manager()

    async def execute(
        self,
        user_message: str,
        analysis: SupervisorAnalysis,
        context: ConversationContext
    ) -> HandlerResult:
        # 1. 워크플로우 실행
        workflow = await self.workflow_manager.get_workflow(
            session_id=context.session_id,
            workspace=context.workspace
        )

        # 2. 스트리밍 결과 수집
        artifacts = []
        updates = []

        async for update in workflow.execute_stream(user_message, context.to_dict()):
            updates.append(update)
            if update.get("artifacts"):
                artifacts.extend(update["artifacts"])

        # 3. 사용자 응답 생성
        user_response = self._format_code_response(updates, artifacts)

        return HandlerResult(
            content=user_response,
            artifacts=artifacts,
            metadata={
                "workflow_id": updates[0].get("workflow_id") if updates else None,
                "agents_used": list(set(u.get("agent") for u in updates if u.get("agent")))
            }
        )

    def _format_code_response(self, updates: List, artifacts: List) -> str:
        """워크플로우 결과를 사용자 친화적 응답으로 변환"""
        if not artifacts:
            return "코드 생성을 완료하지 못했습니다. 요청을 더 구체적으로 설명해주세요."

        files_summary = "\n".join([
            f"- `{a['filename']}` ({a.get('language', 'unknown')})"
            for a in artifacts
        ])

        return f"""## 코드 생성 완료

다음 파일들이 생성되었습니다:
{files_summary}

### 생성된 코드

{self._format_artifacts(artifacts)}

---
추가 수정이나 테스트가 필요하면 말씀해주세요."""
```

---

### 3.6 ResponseAggregator

**파일**: `backend/core/response_aggregator.py` (신규)

```python
@dataclass
class UnifiedResponse:
    """통합 응답 구조"""
    response_type: str
    content: str
    artifacts: List[Dict[str, Any]]
    plan_file: Optional[str] = None
    analysis: Optional[Dict[str, Any]] = None
    next_actions: List[str] = None
    metadata: Dict[str, Any] = None

    def to_dict(self) -> Dict[str, Any]:
        return {
            "response_type": self.response_type,
            "content": self.content,
            "artifacts": self.artifacts,
            "plan_file": self.plan_file,
            "analysis": self.analysis,
            "next_actions": self.next_actions or [],
            "metadata": self.metadata or {}
        }


class ResponseAggregator:
    """핸들러 결과를 UnifiedResponse로 집계"""

    def aggregate(
        self,
        result: HandlerResult,
        analysis: SupervisorAnalysis
    ) -> UnifiedResponse:
        return UnifiedResponse(
            response_type=analysis.response_type,
            content=result.content,
            artifacts=result.artifacts,
            plan_file=result.plan_file,
            analysis={
                "complexity": analysis.complexity,
                "task_type": analysis.task_type,
                "required_agents": analysis.required_agents,
                "confidence": analysis.confidence_score
            },
            next_actions=self._suggest_next_actions(analysis, result),
            metadata=result.metadata
        )

    def _suggest_next_actions(
        self,
        analysis: SupervisorAnalysis,
        result: HandlerResult
    ) -> List[str]:
        """다음 가능한 행동 제안"""
        actions = []

        if analysis.response_type == ResponseType.PLANNING:
            actions.append("코드 생성 시작")
            actions.append("계획 수정")
        elif analysis.response_type == ResponseType.CODE_GENERATION:
            actions.append("테스트 실행")
            actions.append("코드 리뷰 요청")
            actions.append("추가 기능 구현")
        elif analysis.response_type == ResponseType.CODE_REVIEW:
            actions.append("수정 사항 적용")
            actions.append("추가 리뷰 요청")

        return actions
```

---

### 3.7 ContextStore

**파일**: `backend/core/context_store.py` (신규)

```python
@dataclass
class ConversationContext:
    """대화 컨텍스트"""
    session_id: str
    messages: List[Dict[str, str]]
    artifacts: List[Dict[str, Any]]
    workspace: Optional[str]
    last_analysis: Optional[Dict[str, Any]]
    created_at: datetime
    updated_at: datetime

    def to_langchain_messages(self) -> List:
        """LangChain 메시지 형식으로 변환"""
        messages = []
        for msg in self.messages[-20:]:  # 최근 20개
            if msg["role"] == "user":
                messages.append(HumanMessage(content=msg["content"]))
            elif msg["role"] == "assistant":
                messages.append(AIMessage(content=msg["content"]))
            elif msg["role"] == "system":
                messages.append(SystemMessage(content=msg["content"]))
        return messages

    def to_dict(self) -> Dict[str, Any]:
        return {
            "session_id": self.session_id,
            "messages": self.messages[-10:],  # 컨텍스트용 최근 10개
            "artifacts": self.artifacts[-5:],  # 최근 5개 아티팩트
            "workspace": self.workspace,
            "last_analysis": self.last_analysis
        }


class ContextStore:
    """컨텍스트 영속성 관리 - DB 연동"""

    def __init__(self, db_session: Session = None):
        self.db = db_session or get_db()
        self.cache: Dict[str, ConversationContext] = {}  # 메모리 캐시

    async def load(self, session_id: str) -> ConversationContext:
        """세션 컨텍스트 로드"""
        # 1. 캐시 확인
        if session_id in self.cache:
            return self.cache[session_id]

        # 2. DB 조회
        db_context = await self._load_from_db(session_id)

        if db_context:
            self.cache[session_id] = db_context
            return db_context

        # 3. 신규 생성
        new_context = ConversationContext(
            session_id=session_id,
            messages=[],
            artifacts=[],
            workspace=None,
            last_analysis=None,
            created_at=datetime.now(),
            updated_at=datetime.now()
        )
        self.cache[session_id] = new_context
        return new_context

    async def save(
        self,
        session_id: str,
        context: ConversationContext,
        analysis: SupervisorAnalysis,
        response: UnifiedResponse
    ):
        """컨텍스트 저장"""
        # 메시지 추가
        context.messages.append({
            "role": "user",
            "content": analysis.user_request
        })
        context.messages.append({
            "role": "assistant",
            "content": response.content
        })

        # 아티팩트 추가
        context.artifacts.extend(response.artifacts)

        # 분석 결과 저장
        context.last_analysis = response.analysis
        context.updated_at = datetime.now()

        # 캐시 업데이트
        self.cache[session_id] = context

        # DB 저장 (비동기)
        await self._save_to_db(context)
```

---

## 4. API 변경 사항

### 4.1 통합 /chat 엔드포인트

**파일**: `backend/app/api/main_routes.py` (수정)

```python
# 기존 agent_manager 대신 unified_agent_manager 사용
from app.agent.unified_agent_manager import UnifiedAgentManager

unified_manager = UnifiedAgentManager()


@router.post("/chat", response_model=UnifiedChatResponse)
async def unified_chat(request: ChatRequest):
    """통합 채팅 엔드포인트 - 모든 요청을 Supervisor 통해 라우팅"""
    try:
        if request.stream:
            # 스트리밍 모드 - /chat/stream으로 리다이렉트
            raise HTTPException(
                status_code=400,
                detail="Use /chat/stream endpoint for streaming responses"
            )

        response = await unified_manager.process_request(
            session_id=request.session_id,
            user_message=request.message,
            workspace=request.workspace,
            stream=False
        )

        return UnifiedChatResponse(
            response_type=response.response_type,
            content=response.content,
            artifacts=response.artifacts,
            plan_file=response.plan_file,
            analysis=response.analysis,
            next_actions=response.next_actions,
            session_id=request.session_id,
            metadata=response.metadata
        )

    except Exception as e:
        logger.error(f"Error in unified chat: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/chat/stream")
async def unified_chat_stream(request: ChatRequest):
    """통합 스트리밍 채팅 엔드포인트"""
    try:
        async def generate():
            async for update in unified_manager.process_request(
                session_id=request.session_id,
                user_message=request.message,
                workspace=request.workspace,
                stream=True
            ):
                yield f"data: {json.dumps(update.to_dict())}\n\n"

            yield "data: [DONE]\n\n"

        return StreamingResponse(
            generate(),
            media_type="text/event-stream"
        )

    except Exception as e:
        logger.error(f"Error in unified chat stream: {e}")
        raise HTTPException(status_code=500, detail=str(e))
```

### 4.2 응답 모델 추가

**파일**: `backend/app/api/models.py` (수정)

```python
class UnifiedChatResponse(BaseModel):
    """통합 채팅 응답 모델"""
    response_type: str = Field(..., description="Response type: quick_qa, planning, code_generation, etc.")
    content: str = Field(..., description="User-friendly response content")
    artifacts: List[Dict[str, Any]] = Field(default_factory=list, description="Generated artifacts")
    plan_file: Optional[str] = Field(None, description="Saved plan file path")
    analysis: Optional[Dict[str, Any]] = Field(None, description="Supervisor analysis summary")
    next_actions: List[str] = Field(default_factory=list, description="Suggested next actions")
    session_id: str = Field(..., description="Session identifier")
    metadata: Optional[Dict[str, Any]] = Field(None, description="Additional metadata")
```

---

## 5. 파일 변경 목록

### 5.1 신규 파일

| 파일 경로 | 역할 |
|-----------|------|
| `backend/app/agent/unified_agent_manager.py` | 통합 에이전트 매니저 |
| `backend/app/agent/handlers/__init__.py` | 핸들러 패키지 |
| `backend/app/agent/handlers/base.py` | 핸들러 베이스 클래스 |
| `backend/app/agent/handlers/quick_qa.py` | QUICK_QA 핸들러 |
| `backend/app/agent/handlers/planning.py` | PLANNING 핸들러 |
| `backend/app/agent/handlers/code_generation.py` | CODE_GENERATION 핸들러 |
| `backend/app/agent/handlers/code_review.py` | CODE_REVIEW 핸들러 |
| `backend/app/agent/handlers/debugging.py` | DEBUGGING 핸들러 |
| `backend/core/response_aggregator.py` | 응답 집계기 |
| `backend/core/context_store.py` | 컨텍스트 저장소 |

### 5.2 수정 파일

| 파일 경로 | 수정 내용 |
|-----------|----------|
| `backend/app/api/main_routes.py` | 통합 엔드포인트로 변경 |
| `backend/app/api/models.py` | UnifiedChatResponse 추가 |
| `backend/app/agent/__init__.py` | unified_agent_manager 익스포트 |

### 5.3 Deprecated (하위 호환성 유지)

| 파일 경로 | 상태 |
|-----------|------|
| `backend/app/agent/langchain/agent_manager.py` | 레거시, deprecated warning 추가 |

---

## 6. 구현 순서

### Phase 1: 핵심 인프라 (1시간)
1. `backend/core/response_aggregator.py` 생성
2. `backend/core/context_store.py` 생성
3. `backend/app/api/models.py`에 `UnifiedChatResponse` 추가

### Phase 2: 핸들러 구현 (2시간)
1. `backend/app/agent/handlers/base.py` 생성
2. `backend/app/agent/handlers/quick_qa.py` 생성
3. `backend/app/agent/handlers/planning.py` 생성
4. `backend/app/agent/handlers/code_generation.py` 생성

### Phase 3: 통합 매니저 (1시간)
1. `backend/app/agent/unified_agent_manager.py` 생성
2. 모든 핸들러 연동

### Phase 4: API 통합 (30분)
1. `backend/app/api/main_routes.py` 수정
2. 기존 `/chat` 엔드포인트를 통합 버전으로 교체

### Phase 5: 테스트 (30분)
1. 각 응답 타입별 동작 테스트
2. 컨텍스트 영속성 테스트
3. 스트리밍 테스트

---

## 7. 테스트 시나리오

### 7.1 QUICK_QA 테스트
```
입력: "Python의 리스트와 튜플의 차이점이 뭐야?"
기대 출력:
{
  "response_type": "quick_qa",
  "content": "Python의 리스트와 튜플의 주요 차이점은...",
  "artifacts": [],
  "next_actions": []
}
```

### 7.2 PLANNING 테스트
```
입력: "REST API 서버를 어떻게 설계해야 할까?"
기대 출력:
{
  "response_type": "planning",
  "content": "## 개발 계획\n\n### 1. API 설계...",
  "artifacts": [],
  "plan_file": null,  // 복잡도 낮으면 저장 안함
  "next_actions": ["코드 생성 시작", "계획 수정"]
}
```

### 7.3 CODE_GENERATION 테스트
```
입력: "Python으로 계산기를 만들고 싶습니다."
기대 출력:
{
  "response_type": "code_generation",
  "content": "## 코드 생성 완료\n\n다음 파일들이 생성되었습니다:\n- `calculator.py`...",
  "artifacts": [
    {"filename": "calculator.py", "language": "python", "content": "..."}
  ],
  "next_actions": ["테스트 실행", "추가 기능 구현"]
}
```

---

## 8. 마이그레이션 전략

### 8.1 하위 호환성
- 기존 `/workflow/execute` 엔드포인트는 유지
- 기존 `LangChainAgent`는 deprecated로 표시하되 동작 유지
- 프론트엔드가 새 응답 포맷 지원할 때까지 점진적 마이그레이션

### 8.2 롤백 계획
- 환경 변수 `USE_UNIFIED_AGENT=true/false`로 전환 가능
- 문제 발생 시 기존 경로로 폴백

---

## 9. 구현 결과 (2026-01-06)

### 9.1 구현된 백엔드 컴포넌트

| 파일 | 상태 | 설명 |
|------|------|------|
| `backend/core/response_aggregator.py` | ✅ 완료 | UnifiedResponse, HandlerResult, StreamUpdate 정의 |
| `backend/core/context_store.py` | ✅ 완료 | ConversationContext, ContextStore (DB 영속성 포함) |
| `backend/app/agent/unified_agent_manager.py` | ✅ 완료 | 통합 에이전트 매니저 |
| `backend/app/agent/handlers/base.py` | ✅ 완료 | BaseHandler 추상 클래스, StreamUpdate |
| `backend/app/agent/handlers/quick_qa.py` | ✅ 완료 | QUICK_QA 핸들러 |
| `backend/app/agent/handlers/planning.py` | ✅ 완료 | PLANNING 핸들러 (계획 파일 저장 포함) |
| `backend/app/agent/handlers/code_generation.py` | ✅ 완료 | CODE_GENERATION 핸들러 |
| `backend/app/api/main_routes.py` | ✅ 완료 | `/chat/unified`, `/chat/unified/stream` 엔드포인트 |

### 9.2 구현된 프론트엔드 컴포넌트

| 파일 | 상태 | 설명 |
|------|------|------|
| `frontend/src/types/api.ts` | ✅ 완료 | UnifiedChatResponse, UnifiedStreamUpdate 타입 |
| `frontend/src/api/client.ts` | ✅ 완료 | unifiedChat(), unifiedChatStream() 메서드 |
| `frontend/src/components/WorkflowInterface.tsx` | ✅ 완료 | Unified 모드 지원, Next Actions 연동 |
| `frontend/src/components/NextActionsPanel.tsx` | ✅ 완료 | 다음 행동 버튼 UI |
| `frontend/src/components/PlanFileViewer.tsx` | ✅ 완료 | 계획 파일 미리보기 모달 |

### 9.3 주요 기능

#### 9.3.1 Next Actions UI
- 워크플로우 완료 후 자동으로 다음 행동 버튼 표시
- 응답 타입별 맞춤형 제안:
  - QUICK_QA: "추가 질문하기"
  - PLANNING: "코드 생성 시작", "계획 수정 요청", "계획 파일 확인"
  - CODE_GENERATION: "테스트 실행", "코드 리뷰 요청", "추가 기능 구현"
  - CODE_REVIEW: "수정 사항 적용", "추가 리뷰 요청"
  - DEBUGGING: "수정 사항 적용", "테스트 실행"

#### 9.3.2 Plan File Viewer
- 복잡한 작업의 경우 계획을 마크다운 파일로 저장
- 저장 위치: `{workspace}/.plans/PLAN_{keyword}_{timestamp}.md`
- 모달 UI로 계획 내용 미리보기
- "코드 생성 시작" 버튼으로 바로 구현 시작 가능

#### 9.3.3 DB 영속성 (ContextStore)
- SQLAlchemy를 통한 대화 컨텍스트 DB 저장
- 메모리 캐시 + DB 영속성 하이브리드 방식
- 저장 데이터:
  - 대화 메시지 (role, content, timestamp)
  - 생성된 아티팩트 (filename, language, content)
  - Supervisor 분석 결과 (last_analysis)
  - 워크스페이스 경로

### 9.4 API 엔드포인트

#### POST `/chat/unified`
통합 채팅 (비스트리밍)

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
  "artifacts": [
    {
      "filename": "calculator.py",
      "language": "python",
      "content": "...",
      "saved_path": "/home/user/workspace/calculator/calculator.py"
    }
  ],
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

#### POST `/chat/unified/stream`
통합 채팅 (스트리밍)

**Request:** 동일

**Response:** Server-Sent Events
```
data: {"agent": "Supervisor", "type": "analysis", "status": "completed", "message": "분석 완료: code_generation", "data": {...}}

data: {"agent": "CodeGenerationHandler", "type": "progress", "status": "running", "message": "코드 생성 워크플로우를 시작합니다..."}

data: {"agent": "Coder", "type": "artifact", "status": "running", "message": "calculator.py 생성 중..."}

data: {"agent": "UnifiedAgentManager", "type": "done", "status": "completed", "message": "모든 처리가 완료되었습니다.", "data": {"next_actions": [...], "plan_file": null}}

data: [DONE]
```

### 9.5 해결된 이슈

1. **async for 오류** - `process_request` 반환값에 `await` 누락 수정
2. **StreamUpdate 타입 불일치** - 모든 모듈에서 동일한 필드 사용
3. **collectArtifactsFromUpdates 참조 오류** - `extractArtifacts`로 통합

---

*이 문서는 Unified Workflow Architecture의 설계 및 구현 결과를 기록합니다.*

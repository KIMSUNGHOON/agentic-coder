# HITL (Human-In-The-Loop) Enhancement Plan

**버전**: 1.0
**작성일**: 2026-01-07
**목표**: 진정한 HITL 워크플로우 구현 - 동적 피드백, 실시간 인터럽트, 스마트 체크포인트

---

## 1. 현재 상태 분석

### 1.1 이미 구현된 HITL 기능

#### 백엔드
- **HITLManager** (`backend/app/hitl/manager.py`)
  - 완전한 HITL 요청/응답 관리 시스템
  - WebSocket을 통한 실시간 통신
  - 비동기 대기 및 타임아웃 처리
  - 5가지 체크포인트 타입 지원 (approval, review, edit, choice, confirm)

- **human_approval_node** (`backend/app/agent/langgraph/nodes/human_approval.py`)
  - LangGraph 워크플로우 통합
  - 워크플로우 일시 정지/재개 메커니즘
  - 상태 기반 HITL 요청 생성

- **HITL API Routes** (`backend/app/api/routes/hitl_routes.py`)
  - REST API 엔드포인트 (/hitl/pending, /hitl/respond, etc.)
  - WebSocket 실시간 이벤트 브로드캐스팅
  - 워크플로우별 요청 관리

#### 프론트엔드
- **HITLModal** (`frontend/src/components/HITLModal.tsx`)
  - 완전한 HITL UI 컴포넌트
  - 체크포인트 타입별 맞춤 UI
  - 코드 에디터, 리뷰 뷰어, 선택 옵션 등

- **WorkflowInterface** (`frontend/src/components/WorkflowInterface.tsx`)
  - HITL 요청 상태 관리
  - WebSocket 통합 (추정)

### 1.2 현재 구현의 한계

1. **정적 체크포인트**: 워크플로우에 하드코딩된 특정 노드에서만 HITL 발생
2. **제한된 피드백 채널**: HITL 모달을 통해서만 피드백 가능
3. **수동 인터럽트 불가**: 사용자가 워크플로우 실행 중 임의로 일시 정지 불가
4. **Reasoning 중 피드백 없음**: Agent가 스스로 불확실성을 감지하고 질문하는 기능 부재
5. **대화 흐름 단절**: HITL 모달이 별도 UI로 대화 맥락 단절

---

## 2. 개선 목표 및 요구사항

### 2.1 핵심 요구사항 (사용자 피드백 기반)

> "프롬프트 입력창을 통해서 중간에 다이나믹하게 Human In The Loop을 통해서 피드백을 받는것입니다."

> "reasoning을 통해서 스스로 feedback을 받을것인지. 아니면 항상 인터럽트가 가능하게 할 것인지."

> "진정한 HITL을 워크플로우에 적용하기 위해서 어떻게 해야 하는지 너가 판단해서 계획을 수립해봐."

### 2.2 개선 목표

1. **동적 HITL 요청**
   - Agent가 reasoning 중 불확실성 감지 시 자동으로 HITL 요청
   - LLM이 중요한 결정 시점을 스스로 판단

2. **실시간 사용자 인터럽트**
   - 워크플로우 실행 중 언제든지 사용자가 일시 정지 가능
   - "Pause" 버튼으로 즉시 중단 후 피드백 입력

3. **통합 채팅 인터페이스**
   - HITL 모달이 아닌 채팅창에서 직접 피드백
   - 대화 흐름을 유지하며 자연스러운 상호작용

4. **스마트 체크포인트**
   - 사용자 설정에 따른 자동/수동 모드
   - 프로젝트 이름, 파일 경로 등 중요 결정 시점 자동 감지

---

## 3. 설계 방향

### 3.1 아키텍처 전략

#### 3.1.1 두 가지 HITL 모드

**모드 A: AI-Driven HITL (스마트 체크포인트)**
- Agent가 reasoning 중 불확실성 감지 시 자동으로 HITL 요청
- LLM 프롬프트에 "If you need clarification, generate a HITL request" 추가
- 특수 출력 형식으로 HITL 요청 생성

**모드 B: User-Driven HITL (실시간 인터럽트)**
- 사용자가 UI에서 "Pause" 버튼 클릭
- 현재 실행 중인 노드에서 즉시 일시 정지
- 사용자 피드백 후 재개

#### 3.1.2 통합 전략

현재 시스템은 이미 강력한 HITL 인프라를 보유하고 있으므로, **기존 시스템을 확장**하는 방식으로 진행:

1. **HITLManager 확장** (이미 완성도 높음, 최소 수정)
2. **Agent 프롬프트 강화** (AI-Driven HITL을 위한 프롬프트 추가)
3. **새로운 체크포인트 타입 추가**: `dynamic_question`
4. **프론트엔드 채팅 통합** (HITL 요청을 채팅 메시지로 표시)

### 3.2 핵심 컴포넌트 설계

#### 3.2.1 AI-Driven HITL: Agent Prompt Enhancement

**목표**: Agent가 스스로 HITL 요청을 생성하도록 프롬프트 강화

**구현 위치**:
- `backend/app/agent/langchain/specialized/base_langchain_agent.py`
- `backend/app/core/supervisor.py`
- 각 Agent의 시스템 프롬프트

**프롬프트 예시**:
```python
HITL_PROMPT_ENHANCEMENT = """
When you encounter situations requiring user input, you can request human feedback using the following format:

**HITL_REQUEST:**
- **Type**: question | choice | approval | confirm
- **Title**: Brief title (e.g., "Project Name Confirmation")
- **Question**: Your question to the user
- **Options** (for choice type): ["Option 1", "Option 2", ...]
- **Context**: Relevant context for the decision

Example:
**HITL_REQUEST:**
- **Type**: question
- **Title**: Project Directory Name
- **Question**: You mentioned creating a new project. What should I name the project directory?
- **Context**: This will determine the folder structure and module naming conventions.

After generating a HITL_REQUEST, STOP and wait for user response.

Situations where you SHOULD request human input:
1. Unclear or ambiguous requirements
2. Critical decisions (project names, file paths, architectural choices)
3. Security-sensitive operations (file deletion, external API calls)
4. Multiple valid implementation approaches
"""
```

#### 3.2.2 Dynamic HITL Request Parser

**새로운 컴포넌트**: `backend/app/hitl/dynamic_parser.py`

```python
class DynamicHITLParser:
    """Parse agent output for dynamic HITL requests"""

    def parse_agent_output(self, output: str) -> Optional[HITLRequest]:
        """
        Parse agent output for HITL_REQUEST markers.

        Returns:
            HITLRequest if found, None otherwise
        """
        # Parse markdown-style HITL_REQUEST block
        # Extract type, title, question, options, context
        # Generate HITLRequest object

    def inject_response_into_context(
        self,
        original_output: str,
        user_response: str
    ) -> str:
        """
        Inject user response into agent context for continuation.

        Returns:
            Modified output with user response included
        """
```

#### 3.2.3 User-Driven Pause/Resume

**새로운 API 엔드포인트**: `POST /workflow/pause/{workflow_id}`

```python
@router.post("/workflow/pause/{workflow_id}")
async def pause_workflow(workflow_id: str):
    """
    User-initiated workflow pause.

    1. Set workflow status to 'paused_by_user'
    2. Wait for current node to complete (graceful pause)
    3. Create a generic HITL request for user feedback
    4. Return pause confirmation
    """
```

**프론트엔드 Pause 버튼**:
- WorkflowStatusPanel에 "⏸️ Pause" 버튼 추가
- 클릭 시 `/workflow/pause/{workflow_id}` 호출
- HITL 요청 생성되면 채팅창에 표시

#### 3.2.4 통합 채팅 + HITL UI

**현재**:
- HITL 요청 → HITLModal (별도 모달)

**개선**:
- HITL 요청 → 채팅 메시지로 표시 (inline HITL component)
- 사용자 응답 → 채팅 입력창으로 제출
- 대화 흐름 유지

**구현 방법**:

1. **새로운 메시지 타입**: `hitl_request`

```typescript
// frontend/src/types/api.ts
interface HITLMessage {
  role: 'assistant';
  type: 'hitl_request';
  hitl_request: HITLRequest;
  timestamp: number;
}
```

2. **ChatMessage 컴포넌트 확장**:

```tsx
// frontend/src/components/ChatMessage.tsx
const ChatMessage = ({ message }: { message: ConversationMessage }) => {
  if (message.type === 'hitl_request') {
    return <InlineHITLRequest request={message.hitl_request} />;
  }
  // ... existing rendering logic
}
```

3. **InlineHITLRequest 컴포넌트**:

```tsx
const InlineHITLRequest = ({ request }: { request: HITLRequest }) => {
  return (
    <div className="inline-hitl-request">
      <div className="hitl-question">
        <strong>{request.title}</strong>
        <p>{request.description}</p>
      </div>

      {/* Render based on checkpoint_type */}
      {request.checkpoint_type === 'question' && (
        <QuestionInput onSubmit={handleResponse} />
      )}

      {request.checkpoint_type === 'choice' && (
        <ChoiceButtons options={request.content.options} onSelect={handleResponse} />
      )}

      {/* ... other types */}
    </div>
  );
}
```

---

## 4. 구현 계획 (Phase별)

### Phase 1: AI-Driven HITL (동적 질문 생성)

**목표**: Agent가 스스로 불확실성 감지하고 HITL 요청 생성

**작업 항목**:
1. ✅ Agent 프롬프트에 HITL 요청 생성 가이드라인 추가
2. ✅ DynamicHITLParser 구현
3. ✅ Agent 출력 파싱 및 HITL 요청 생성 로직 추가
4. ✅ 새로운 체크포인트 타입 `dynamic_question` 추가
5. ✅ 테스트: Supervisor가 프로젝트 이름 질문 생성

**예상 기간**: 2-3일

**핵심 파일**:
- `backend/app/hitl/dynamic_parser.py` (신규)
- `backend/app/hitl/models.py` (체크포인트 타입 추가)
- `backend/app/core/supervisor.py` (프롬프트 수정)
- `backend/app/agent/langchain/specialized/*.py` (각 Agent 프롬프트 수정)

### Phase 2: User-Driven Pause/Resume (실시간 인터럽트)

**목표**: 사용자가 워크플로우 실행 중 언제든지 일시 정지 가능

**작업 항목**:
1. ✅ `/workflow/pause/{workflow_id}` API 엔드포인트 구현
2. ✅ Workflow 상태 관리 확장 (`paused_by_user` 상태 추가)
3. ✅ 프론트엔드 Pause 버튼 추가
4. ✅ Pause 시 generic HITL 요청 생성
5. ✅ Resume 로직 구현

**예상 기간**: 2일

**핵심 파일**:
- `backend/app/api/routes/langgraph_routes.py` (Pause API 추가)
- `frontend/src/components/WorkflowStatusPanel.tsx` (Pause 버튼)
- `backend/app/agent/langgraph/enhanced_workflow.py` (Pause 상태 처리)

### Phase 3: 통합 채팅 + HITL UI

**목표**: HITL 요청을 채팅 메시지로 표시하여 대화 흐름 유지

**작업 항목**:
1. ✅ 새로운 메시지 타입 `hitl_request` 정의
2. ✅ InlineHITLRequest 컴포넌트 구현
3. ✅ ChatMessage 컴포넌트 확장
4. ✅ HITL 응답을 채팅 입력창으로 제출하는 로직
5. ✅ 기존 HITLModal과 병행 사용 (옵션으로 전환 가능)

**예상 기간**: 3-4일

**핵심 파일**:
- `frontend/src/types/api.ts` (타입 정의)
- `frontend/src/components/ChatMessage.tsx` (확장)
- `frontend/src/components/InlineHITLRequest.tsx` (신규)
- `frontend/src/components/WorkflowInterface.tsx` (통합)

### Phase 4: 스마트 체크포인트 설정

**목표**: 사용자가 자동/수동 HITL 모드를 선택하고 체크포인트 규칙 커스터마이징

**작업 항목**:
1. ✅ HITL 설정 UI (Settings 패널)
2. ✅ 자동/수동 모드 선택
3. ✅ 체크포인트 규칙 정의 (프로젝트 이름, 파일 삭제, 외부 API 등)
4. ✅ 설정을 백엔드로 전달하여 워크플로우 동작 조정

**예상 기간**: 2일

**핵심 파일**:
- `frontend/src/components/HITLSettings.tsx` (신규)
- `backend/app/core/hitl_config.py` (신규)

---

## 5. 기술적 고려사항

### 5.1 Reasoning 중 HITL 요청 감지 방법

**옵션 1: 구조화된 출력 파싱** (선택)
- Agent 출력에서 `**HITL_REQUEST:**` 마커 탐지
- Markdown 파싱으로 요청 정보 추출
- 장점: 간단, 빠름
- 단점: LLM이 정확한 형식을 따라야 함

**옵션 2: Function Calling**
- LLM에게 `request_human_input()` 함수 제공
- LLM이 함수 호출로 HITL 요청
- 장점: 구조화, 정확
- 단점: DeepSeek-R1 등 일부 모델은 function calling 미지원

**결정**: **옵션 1**을 우선 구현 (현재 시스템 호환성)

### 5.2 Pause 시 워크플로우 상태 저장

LangGraph의 **Checkpointing** 기능 활용:
- 현재 상태를 메모리에 저장
- Resume 시 정확히 이어서 실행
- `backend/app/agent/langgraph/nodes/persistence.py` 활용

### 5.3 WebSocket vs SSE

현재 시스템:
- WebSocket: HITL 이벤트 브로드캐스팅
- SSE: 워크플로우 스트리밍 업데이트

**개선 제안**:
- HITL 요청도 SSE로 스트리밍 (통합)
- WebSocket은 양방향 통신이 필요한 경우만 사용

### 5.4 동시성 처리

**문제**: 사용자가 Pause 버튼을 누르는 동시에 Agent가 HITL 요청 생성 시 충돌 가능

**해결책**:
- Workflow 상태에 Lock 적용
- 먼저 도착한 HITL 요청 우선 처리
- 중복 요청은 무시

---

## 6. 사용자 시나리오 예시

### 시나리오 1: AI-Driven HITL (프로젝트 이름)

```
User: "Create a REST API for user management"

Supervisor (reasoning):
  - User wants REST API
  - Need to know project name for directory structure
  - **HITL_REQUEST:**
    - Type: question
    - Title: Project Name
    - Question: What should I name this project?
    - Context: This will create a folder like `user-api/` or `user_management/`

[Workflow pauses, HITL request shown in chat]

User (in chat): "user-management-api"

Supervisor: "Got it! Creating project 'user-management-api'..."

[Workflow continues]
```

### 시나리오 2: User-Driven Pause

```
User: "Implement authentication with JWT"

[Workflow starts: Supervisor → Architect → Coder]

[User sees Architect designing the system]

User (clicks Pause button)

System: "Workflow paused. What would you like to adjust?"

User (in chat): "Use refresh tokens with Redis instead of just access tokens"

Architect: "Understood. Revising architecture to include refresh tokens with Redis..."

[Workflow resumes with updated requirements]
```

### 시나리오 3: 스마트 체크포인트 (파일 삭제)

```
User Settings:
  - Auto HITL: Enabled
  - Checkpoints: [Project Name, File Deletion, External API]

User: "Clean up old migration files"

Coder (detects file deletion):
  - About to delete 5 migration files
  - **HITL_REQUEST:**
    - Type: confirm
    - Title: Confirm File Deletion
    - Action: Delete 5 migration files
    - Risks: ["Cannot be undone", "May break database history"]

[HITL request shown in chat]

User: "Approve"

Coder: "Files deleted successfully."
```

---

## 7. 성공 지표

1. **동적 HITL 요청 생성률**
   - Agent가 자동으로 HITL 요청 생성한 비율
   - 목표: 복잡한 요청의 30% 이상

2. **사용자 인터럽트 사용률**
   - 사용자가 Pause 버튼을 사용한 세션 비율
   - 목표: 20% 이상

3. **대화 흐름 만족도**
   - 채팅 기반 HITL vs 모달 기반 HITL 선호도
   - 목표: 채팅 기반 70% 이상 선호

4. **워크플로우 성공률 향상**
   - HITL을 통한 요구사항 명확화로 재작업 감소
   - 목표: 첫 실행 성공률 20% 향상

---

## 8. 위험 요소 및 완화 전략

### 위험 1: LLM이 HITL 형식을 정확히 따르지 않음

**완화 전략**:
- 프롬프트에 명확한 예시 포함
- Few-shot learning 적용
- 파싱 실패 시 일반 출력으로 fallback

### 위험 2: Pause가 너무 자주 사용되어 생산성 저하

**완화 전략**:
- Pause는 현재 노드 완료 후 동작 (graceful pause)
- 사용자에게 "Pause 후 재개 시 컨텍스트 유지됨" 명확히 안내
- Pause 횟수 제한 (세션당 5회 등)

### 위험 3: 채팅 기반 HITL이 복잡한 요청에는 부적합

**완화 전략**:
- 복잡한 HITL 요청 (코드 리뷰, 다중 선택)은 여전히 모달 사용
- 사용자 설정에서 "Always use modal" 옵션 제공

---

## 9. 다음 단계

1. **요구사항 검토 및 승인** (사용자 확인)
2. **Phase 1 구현 시작** (AI-Driven HITL)
3. **프로토타입 테스트** (간단한 시나리오로 검증)
4. **사용자 피드백 수집**
5. **Phase 2-4 순차 구현**

---

## 10. 결론

현재 시스템은 이미 강력한 HITL 인프라를 보유하고 있으므로, **기존 시스템을 확장**하는 방식으로 진행하는 것이 효율적입니다.

핵심은:
1. **Agent가 스스로 HITL 요청 생성** (프롬프트 강화)
2. **사용자가 언제든지 Pause 가능** (실시간 인터럽트)
3. **채팅 기반 HITL UI** (대화 흐름 유지)

이를 통해 **진정한 Human-In-The-Loop 워크플로우**를 구현하여, AI와 인간이 자연스럽게 협업하는 시스템을 완성합니다.

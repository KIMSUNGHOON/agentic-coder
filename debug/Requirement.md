# Todos
~~* 현재 프로젝트가 Environment에도 호환이 잘 되도록 코드를 수정하고, Frontend UI/UX에도 잘 반영 될 수 있도록 해라.~~
~~* Frontend 경로 호환성 개선~~
~~* 메모리/리소스 최적화~~
~~* UI/UX 개선 적용~~

# Issues
1. 또 model type이 바뀌면 다시 문제가 생기는건 아니죠?
2. Workflow 내에 agent 들이 현재 무슨 일을 하고 있는지 conversations에는 전혀 알 수가 없네요. 단순히 "실행 중..." 이라는 정보만
  사용자에게 보여주네요. 이런 conversations ui는 사용자에게 지루함을 느끼게 하거나, 진행 상황을 알 수가 없습니다. Conversations UI/UX를
  개선 할 필요가 있습니다. 당신이 생각했을때 개발자에게 도움이 되는 내용들을 streaming으로 UI에 rendering하는 방법 등 좋은 방법으로 개선
  해주기를 바랍니다.
3. 아래 Conversations 내용을 살펴보십시오. 
   - 코드를 생성했으나, workspace디렉토리에는 아무런 파일이 저장이 되지 않았음.
   - Conversations UI에서는 심지어 artifact 조차 markdown의 code block을 보여주지도 않음. 
   - 각 agent들의 결과에 대해서도 언급이 없음. 정보가 너무 없음.

"
$
I want to create a calculator in Python. Could you help me with the plan?

✓ 완료
복사
모든 처리가 완료되었습니다.

✓ 완료
복사
Workflow completed

$
Now, please implement the code.

✓ 완료
복사
모든 처리가 완료되었습니다.

$ workflow execute --stream
✓
[감독자]
분석 완료: code_generation

✓
[감독자]
Task identified as: code_generation

✓
[planning]
PlanningAgent

✓
[coding]
Successfully created 23 files using parallel execution (up to 23 concurrent)

✓
[orchestrator]
Parallel execution completed with 23 concurrent agents. Generated 23 files.

✓
[review]
Review completed: 23 files reviewed in parallel, 41 total issues found

✓
[orchestrator]
Parallel review completed with 4 concurrent agents. Reviewed 23 files, found 41 issues.

✓
[fixcode]
FixCodeAgent

✓
[review]
ReviewAgent

✓
[fixcode]
FixCodeAgent

✓
[review]
ReviewAgent

✓
[orchestrator]
Code review passed. Generated 1 file(s).

✓
[codegenerationhandler]
코드 생성이 완료되었습니다.

✓
[unifiedagentmanager]
모든 처리가 완료되었습니다.

✓ 워크플로우 완료
"
4. 1,2 번이 모두 수행되면 모든 문서에 update하고, git commit & push 하십시오.

# Reference
* backend log는 (@debug\\*.log) 를 뒤질 것
* frontend log는 (@debug\\*.log) 를 뒤질 것
* conversations log는 (@debug\\*.log) 를 뒤질 것

# 중요
* 반드시 작업 내역을 해당 파일에 업데이트 할 것
* 수정 사항이 많은 경우 반드시 Planning을 하고 진행 할 것
* 항상 프로젝트 문서를 먼저 확인 할 것 (문서: @docs\*.md, @README.md) 
* 항상 새로운 기능 구현시에는 기존 기능들과 호환성이 유지 되어야 합니다.
* 항상 Linux/MacOS/Windows 크로스 플랫폼을 지원하고 호환성이 유지 되어야 합니다.
* 항상 파일시스템은 Linux/MacOS/Windows 의 shell 환경에 따라 instruction이 달라지므로 환경에 따라 파일시스템 기능을 제공해야 합니다.
* Computing Resource가 뭐냐에 따라 적응형 최적화가 기본입니다. 물론 GPU에 따른 Model설정은 서버 관리자의 몫입니다.
* 항상 기능 추가 및 수정에는 반드시 최종 로직 테스트 코드로 확인이 되어야합니다. (예: API 변경 또는 구현시에 동작 테스트 필수)
* DeepSeek-R1, Qwen3, gpt-oss 이 세가지 모델을 서버 관리자가 사용할텐데, 항상 모델 설정에 따른 프롬프트 엔지니어링 전략, 시스템 프롬프트는 각 모델의 Guide를 참고 하도록 하시오.
* 기능을 추가하거나, 수정한다음에 반드시 git commit을 하고 push를 하십시오. 

# Environment
* Nvidia RTX 3090 24GB Single Card
* Windows Powershell 환경
* ollama serve deepseek-r1:14B 단일 모델 서빙

# 작업 내역 (2026-01-06)

## 완료된 수정 사항

### 1. List Import 에러 수정
- **파일**: `backend/app/agent/unified_agent_manager.py`
- **문제**: `name 'List' is not defined` 에러 (500 Internal Server Error)
- **해결**: `List`를 typing imports에 추가

### 2. FastAPI Deprecation Warning 수정
- **파일**: `backend/app/api/main_routes.py`
- **문제**: `regex` 파라미터가 deprecated, `pattern` 사용 권장
- **해결**: 3곳에서 `regex=` → `pattern=` 변경 (lines 422, 1957, 2392)

### 3. Windows 경로 호환성 개선
- **문제**: `/home/user/workspace` 하드코딩 경로가 Windows에서 작동하지 않음
- **해결**: OS에 따른 동적 경로 설정 구현

#### 수정된 파일:
1. **config.py**: `get_default_workspace()` 함수 추가
   - Windows: `C:\Users\<username>\workspace`
   - Linux/Mac: `/home/user/workspace`

2. **main_routes.py**: 6곳에서 하드코딩 경로를 `settings.default_workspace`로 변경

3. **session_store.py**: 2곳에서 하드코딩 경로를 `settings.default_workspace`로 변경

4. **deepagent_workflow.py**: 2곳에서 하드코딩 경로를 `settings.default_workspace`로 변경

5. **workflow_service.py**: 1곳에서 하드코딩 경로 변경 및 cross-platform 경로 체크 개선

### 4. LangGraphWorkflowManager.get_workflow 에러 수정
- **파일**: `backend/app/agent/langchain/workflow_manager.py`
- **문제**: `'LangGraphWorkflowManager' object has no attribute 'get_workflow'`
- **해결**: `async get_workflow()` 메서드 추가 (Line 2395-2411)

### 5. RTX 3090 + Ollama 병렬 실행 최적화
- **문제**: H100 기준 `max_parallel_agents=25`로 설정되어 Ollama 순차 처리 환경에서 병목
- **해결**:
  - `config.py`: `max_parallel_agents`, `enable_parallel_coding` 설정 추가
  - `workflow_manager.py`: config에서 설정값 로드
  - `.env`: RTX 3090 최적화 설정 (`MAX_PARALLEL_AGENTS=2`)

### 6. Config 환경 변수 로깅 추가
- **파일**: `backend/app/core/config.py`
- **해결**: Backend 시작 시 `.env` 경로 및 모든 설정값 콘솔 출력

### 7. create_conversation idempotent 패턴 적용
- **파일**: `backend/app/api/main_routes.py`
- **문제**: 동일 session_id로 conversation 재생성 시 `400 Bad Request`
- **해결**: 이미 존재하면 기존 conversation 반환 (get_or_create 패턴)

### 8. review_result NoneType 에러 수정
- **파일**: `backend/app/agent/langchain/workflow_manager.py`
- **문제**: 병렬 리뷰 모드에서 `review_result` 미정의 → `object of type 'NoneType' has no len()`
- **해결**:
  - while 루프 전 `review_result` 기본값 초기화 (Line 1220)
  - 병렬 리뷰 완료 시 `review_result` 구성 (Line 1259-1279)

### 9. review_result None 덮어쓰기 문제 수정 (2026-01-07)
- **파일**: `backend/app/agent/langchain/workflow_manager.py`
- **문제**: Line 1248에서 `review_result = None` 설정이 Line 1220의 초기화를 덮어씀
  - 병렬 리뷰 중 예외 발생 시 review_result가 None으로 남아 `len(review_result['issues'])` 호출 시 에러
- **해결**: `review_result = None` 할당 제거, Line 1220의 기본값 유지

### 10. Streaming UI 개선 (2026-01-07)
- **파일들**:
  - `frontend/src/components/WorkflowInterface.tsx`
  - `frontend/src/components/TerminalOutput.tsx`
- **문제**: 스트리밍 진행 상황 업데이트가 각각 새 줄로 표시되어 UI가 지저분함
  - 예: `[planninghandler] 계획 작성 중... (2107 자)` 가 수십 줄로 표시
- **해결**:
  - WorkflowInterface.tsx: 유의미한 업데이트만 `setUpdates`에 추가 (line 666-677)
    - 'completed', 'error', 'artifact', 'analysis', 'decision' 등만 표시
    - 'thinking', 'progress' 등 스트리밍 노이즈 필터링
  - TerminalOutput.tsx: 필터링 로직 및 토글 버튼 추가 (line 120-136)
    - 숨겨진 업데이트 개수 표시
    - "모든 진행 상황 보기" 토글로 상세 로그 확인 가능

### 11. Frontend 경로 호환성 개선 (2026-01-07)
- **새 유틸리티 파일**: `frontend/src/utils/workspace.ts`
  - `isWindows()`: 브라우저에서 Windows 플랫폼 감지
  - `getDefaultWorkspacePlaceholder()`: OS별 기본 경로 (Windows: `C:\Users\username\workspace`, Linux/Mac: `/home/user/workspace`)
  - `getDefaultWorkspace()`: localStorage 우선, 폴백으로 OS 기본 경로
  - `getBasename()`: `/` 와 `\` 모두 지원하는 파일명 추출
- **수정된 파일들**:
  - `App.tsx`: 하드코딩 경로 → `getDefaultWorkspace()` 사용
  - `WorkflowInterface.tsx`: 하드코딩 경로 → `getDefaultWorkspace()`, `getDefaultWorkspacePlaceholder()` 사용
  - `client.ts`: `listProjects()` 기본값 → `getDefaultWorkspace()`
  - `ProjectSelector.tsx`: 기본값 → `getDefaultWorkspace()`
  - `WorkspaceProjectSelector.tsx`: placeholder → `getDefaultWorkspacePlaceholder()`
  - `PlanFileViewer.tsx`: `split('/').pop()` → `getBasename()` (Windows 경로 호환)

### 12. Workflow Status 연동 수정 (2026-01-07)
- **파일**: `frontend/src/components/WorkflowInterface.tsx`
- **문제**: Backend에서 보내는 node 이름과 Frontend agent 이름이 불일치
  - Backend: `planninghandler`, `codegenerationhandler`, `orchestrator`, `workspaceexplorer` 등
  - Frontend: `supervisor`, `architect`, `coder`, `reviewer` 등
  - 이름 불일치로 status panel이 업데이트 되지 않음
- **해결**: `mapNodeToAgent()` 함수 추가 (line 258-315)
  - Backend node 이름을 Frontend agent 이름으로 매핑
  - Direct mapping 테이블 + Pattern matching 폴백
  - 예: `planninghandler` → `architect`, `codegenerationhandler` → `coder`

### 13. Supervisor Response Type 버그 수정 (2026-01-07)
- **파일**: `backend/core/supervisor.py`
- **문제**: 연산자 우선순위 버그로 "code"를 포함한 모든 요청이 CODE_REVIEW로 분류됨
  - Line 497: `if any(p in ...) and "코드" in ... or "code" in ...`
  - 연산자 우선순위: `(any(...) and "코드") or ("code")` → "code"만 있어도 True
  - "Now, please implement the code." → CODE_REVIEW로 잘못 분류
- **해결**: 괄호 추가로 올바른 우선순위 적용
  - `if any(p in ...) and ("코드" in ... or "code" in ...):`

### 14. Workflow Status 실시간 동기화 수정 (2026-01-07)
- **파일**: `frontend/src/components/WorkflowInterface.tsx`
- **문제**: Status indicator가 실시간으로 업데이트되지 않고 workflow 완료 후 한번에 done으로 변경
  - `workflowUpdate` 객체에 `node` 속성이 누락되어 `updateAgentProgress()` 매핑 실패
- **해결**: `workflowUpdate` 객체에 `node: update.agent` 속성 추가 (line 660)

### 15. Conversation Markdown 코드 블록 구문 강조 (2026-01-07)
- **파일**: `frontend/src/components/WorkflowInterface.tsx`
- **문제**: 대화 히스토리에서 코드 블록이 일반 텍스트로 표시됨
- **해결**:
  - `react-syntax-highlighter` import 추가 (Prism + oneDark 테마)
  - User/Assistant 메시지의 `ReactMarkdown`에 커스텀 `code` 컴포넌트 추가
  - 코드 블록 자동 언어 감지 및 구문 강조 적용

### 16. TerminalOutput Markdown 렌더링 (2026-01-07)
- **파일**: `frontend/src/components/TerminalOutput.tsx`
- **문제**: Workflow output이 raw markdown 텍스트로 표시됨 (`##`, `**` 등이 렌더링되지 않음)
- **해결**:
  - `ReactMarkdown`, `remarkGfm` import 추가
  - `update.message` 및 `update.streaming_content`에 ReactMarkdown 적용
  - 코드 블록 구문 강조 (SyntaxHighlighter) 적용
  - 터미널 스타일에 맞는 prose 클래스 설정

### 17. Workflow Indicator 동적 Agent 표시 (2026-01-07)
- **파일**: `frontend/src/components/WorkflowInterface.tsx`
- **문제**: 상단 workflow bar와 오른쪽 패널이 실제 사용되는 agent와 관계없이 고정된 10개 agent 표시
- **해결**:
  - `agentProgress` 초기값을 빈 배열(`[]`)로 변경
  - `getAgentInfo()` 함수 추가 - agent 이름에서 title/description 자동 생성
  - `updateAgentProgress()` 수정 - 새로운 agent 동적 추가
  - 실제 workflow에서 사용되는 agent만 표시됨
  - agent 이름 매핑 추가: unifiedagentmanager, planninghandler, codegenerationhandler 등

### 18. TypeScript 타입 정의 업데이트 (2026-01-07)
- **파일**: `frontend/src/types/api.ts`
- **변경 사항**:
  - `WorkflowUpdate.type`: `progress`, `analysis`, `approved`, `done` 타입 추가
  - `WorkflowUpdate`: `agent_title`, `node`, `timestamp` 필드 추가
  - `TaskAnalysis`: `response_type`, `complexity` 필드 추가

### 19. CodeGenerationHandler NoneType 에러 수정 (2026-01-07)
- **파일**: `backend/app/agent/handlers/code_generation.py`
- **문제**: `_format_code_response()` 메서드에서 `artifact.get('content')`가 `None`일 때 `len(content)` 호출 시 에러
- **해결**:
  - `content = artifact.get('content') or ''` 로 None 처리
  - `if content and len(content) > 2000:` 조건 추가

### 20. Streaming Content UI 카드 스타일 개선 (2026-01-07)
- **파일**: `frontend/src/components/TerminalOutput.tsx`
- **문제**: Streaming output이 다른 텍스트와 시각적으로 구분이 안됨
- **해결**:
  - Output 카드 컨테이너 추가 (`bg-gray-800/60`, `border`, `rounded-lg`)
  - 헤더 섹션 추가 (`📄 Output` 라벨, agent 이름, 복사 버튼)
  - Markdown 스타일링 개선 (h2 시안 색상, border-bottom 등)
  - 코드 블록 테두리 및 스타일 향상

## 완료된 작업 요약
모든 작업이 완료되었습니다:
1. Backend 에러 수정 (List import, regex deprecation, NoneType errors)
2. Windows 경로 호환성 (Backend + Frontend)
3. RTX 3090 + Ollama 최적화 설정
4. Streaming UI 개선 (노이즈 필터링)
5. Workflow Status 연동 수정
6. Supervisor Response Type 버그 수정 (연산자 우선순위)
7. Workflow Status 실시간 동기화 수정 (node 속성 추가)
8. Conversation Markdown 코드 블록 구문 강조
9. TerminalOutput Markdown 렌더링
10. Workflow Indicator 동적 Agent 표시
11. TypeScript 타입 정의 업데이트
12. CodeGenerationHandler NoneType 에러 수정
13. Streaming Content UI 카드 스타일 개선

## 참고 사항: Path Traversal Security Warning
Backend 로그에 표시되는 Security Warning은 정상 동작입니다:
- `.env`의 `DEFAULT_WORKSPACE=C:\Users\kingm\PycharmProjects\workspace`가 기준 경로
- 이 경로 외부의 workspace 설정 시 보안 경고 발생
- **해결책**: `.env`에서 `DEFAULT_WORKSPACE` 값을 프로젝트 경로로 변경하거나, 기준 경로 내에서 작업

## 남은 작업
- 없음 (테스트 후 추가 이슈 발생 시 업데이트)

# 작업 내역 (2026-01-07)

## 완료된 수정 사항

### 21. Workflow 코드 생성 0 Artifact 문제 해결
- **문제**: 사용자가 "Now, please implement the code."라고 요청하면 0개 artifact 생성
- **원인 분석**:
  1. `CodeGenerationHandler`가 `user_message`만 workflow에 전달 (대화 컨텍스트 없음)
  2. PlanningAgent가 "Now, please implement the code."만 받아서 무엇을 구현해야 할지 알 수 없음
  3. `parse_checklist()`가 deepseek-r1의 `<think>` 태그 포함 출력을 제대로 파싱 못함
  4. 빈 checklist → 코드 생성 skip → 빈 code_text로 Review 호출

#### 수정 1: CodeGenerationHandler에 대화 컨텍스트 전달 추가
- **파일**: `backend/app/agent/handlers/code_generation.py`
- **변경사항**:
  - `_build_enriched_message()` 메서드 추가 (lines 290-338)
  - 이전 대화 히스토리를 포함한 enriched user message 생성
  - `execute()`와 `execute_stream()` 모두에서 사용

```python
def _build_enriched_message(self, user_message: str, context: Any) -> str:
    """대화 컨텍스트를 포함한 확장 메시지 생성"""
    # 최근 10개 메시지로 대화 히스토리 구성
    # ## Previous Conversation Context
    # ## Current User Request
    # ## Instructions
```

#### 수정 2: deepseek-r1 `<think>` 태그 처리 추가
- **파일**: `backend/app/agent/langchain/workflow_manager.py`
- **변경된 함수들**:
  - `parse_checklist()` - lines 161-222
  - `parse_code_blocks()` - lines 225-294
  - `parse_review()` - lines 298-424
  - `parse_task_type()` - lines 427-464

- **변경사항**: 모든 파싱 함수에 `<think>` 태그 제거 로직 추가
```python
# Remove <think> tags and their content first (deepseek-r1 reasoning)
clean_text = re.sub(r'<think>.*?</think>', '', text, flags=re.DOTALL | re.IGNORECASE)
clean_text = re.sub(r'</?think>', '', clean_text, flags=re.IGNORECASE)
```

- `parse_checklist()` 추가 개선:
  - `<output_format>` 섹션 우선 파싱
  - Fallback: 템플릿 placeholder와 markdown 헤더 필터링
  - 최후 수단: 길이 10자 이상인 모든 텍스트 라인을 task로 인식

## 테스트 결과
```
[OK] workflow_manager parsing functions import OK
[OK] parse_checklist test: found 3 items
  - Create the project structure with main.py
  - Implement the calculator module
  - Add unit tests for the calculator
[OK] parse_code_blocks test: found 1 code blocks
  - calculator.py (python)
```

## 완료된 작업 요약 (업데이트)
1-13: (기존 작업들)
14. CodeGenerationHandler 대화 컨텍스트 전달 로직 추가
15. deepseek-r1 `<think>` 태그 처리 (parse_checklist, parse_code_blocks, parse_review, parse_task_type)

### 22. Issue 2 해결: Conversations UI 진행 상황 개선 (2026-01-07)
- **문제**: "실행 중..." 메시지만 표시되고 각 Agent가 무슨 작업을 하는지 보이지 않음
- **원인**: `streaming_content`가 StreamUpdate에서 전달되지 않음
- **해결**:

#### Backend 수정:
1. **`backend/core/response_aggregator.py`** (Line 86-87)
   - `StreamUpdate` 클래스에 `streaming_content: Optional[str] = None` 필드 추가
   - `to_dict()` 메서드에 `streaming_content` 포함

2. **`backend/app/agent/handlers/base.py`** (Line 53)
   - `StreamUpdate` 클래스에 `streaming_content` 필드 추가 (동기화)
   - `to_dict()` 메서드 업데이트

3. **`backend/app/agent/handlers/code_generation.py`** (Lines 165-172, 189)
   - `execute_stream()`에서 workflow update의 `streaming_content` 직접 전달
   - `streaming_content` 추출 로직 개선: `update.get("streaming_content") or update.get("content") or update.get("partial_output")`

4. **`backend/app/agent/handlers/planning.py`** (Lines 183-184, 220-226, 245)
   - LLM 스트리밍 중 `streaming_content` 추가
   - 실시간 계획 내용 미리보기 전달

#### Frontend 수정:
1. **`frontend/src/types/api.ts`** (Line 107)
   - `UnifiedStreamUpdate`에 `streaming_content?: string` 필드 추가
   - `update_type`에 `'streaming'` 타입 추가

2. **`frontend/src/components/WorkflowInterface.tsx`** (Lines 332-333, 543-546, 729-731)
   - `updateAgentProgress()`에서 `streaming_content` 직접 확인 추가
   - `liveOutputs` 업데이트 시 직접 streaming_content 사용
   - `executeUnifiedWorkflow()`에서 `'streaming'` 타입 처리

3. **`frontend/src/components/TerminalOutput.tsx`** (Lines 107-114, 121-173, 296)
   - 핸들러 한글 이름 매핑 추가 (planninghandler, codegenerationhandler 등)
   - `getAgentStatusMessage()` 함수 추가 - 에이전트별 상세 상태 메시지
   - 라이브 출력 표시에 상세 상태 메시지 적용

### 23. Issue 3 해결: Artifact 저장 및 표시 개선 (2026-01-07)
- **문제**: `/chat/unified/stream`에서 artifact가 디스크에 저장되지 않음, UI에 code block 없음
- **원인**: `unified_agent_manager.py`에 artifact 저장 로직 없음
- **해결**:

#### Backend 수정:
1. **`backend/app/agent/unified_agent_manager.py`** (Lines 10-11, 277-339, 216-226, 254-275)
   - `import aiofiles` 및 `from pathlib import Path` 추가
   - `_save_artifact_to_workspace()` 메서드 추가:
     - 경로 보안 처리 (path traversal 방지)
     - 부모 디렉토리 자동 생성
     - aiofiles로 비동기 파일 저장
     - 저장 결과 반환 (saved, saved_path, saved_at, error)
   - `_stream_response()`에서 artifact 저장 호출
   - 저장된 파일 목록 및 개수 포함한 완료 메시지 생성

#### Frontend 수정:
1. **`frontend/src/components/WorkflowInterface.tsx`** (Lines 714-722)
   - artifact 추출 시 `saved`, `saved_at`, `error`, `action` 필드 포함
   - `savedFiles` 상태에 저장 상태 정보 추가

### 예상 결과

#### Before (개선 전)
```
[CodeGenerationHandler] 실행 중...
모든 처리가 완료되었습니다.
```

#### After (개선 후)
```
[감독자] 요청을 분석하고 최적의 처리 방법을 결정하고 있습니다...
[계획 수립] 개발 계획을 수립하고 있습니다...
  ## 구현 계획
  1. 프로젝트 구조 생성...
[코드 생성] 코드를 생성하고 있습니다...
  ✓ calculator.py (저장됨: C:\workspace\calculator.py)
  ✓ test_calculator.py (저장됨: C:\workspace\test_calculator.py)
모든 처리가 완료되었습니다. (2개 파일 생성)
```

## 수정 파일 목록 (Issue 2 & 3)

| 순서 | 파일 | 변경 내용 |
|-----|------|---------|
| 1 | `backend/core/response_aggregator.py` | StreamUpdate에 streaming_content 추가 |
| 2 | `backend/app/agent/handlers/base.py` | StreamUpdate 동기화 |
| 3 | `backend/app/agent/handlers/code_generation.py` | streaming_content 전달 |
| 4 | `backend/app/agent/handlers/planning.py` | streaming_content 전달 |
| 5 | `backend/app/agent/unified_agent_manager.py` | artifact 저장 로직 추가 |
| 6 | `frontend/src/types/api.ts` | 타입 확장 |
| 7 | `frontend/src/components/WorkflowInterface.tsx` | streaming_content 처리 |
| 8 | `frontend/src/components/TerminalOutput.tsx` | 에이전트별 상태 메시지, artifact 표시 |

### 24. Artifact 동일 이름 덮어쓰기 문제 해결 (2026-01-07)
- **문제**: 동일한 파일명으로 artifact 저장 시 기존 파일이 덮어쓰기됨 (데이터 손실 위험)
- **원인**: `_save_artifact_to_workspace()`에서 `'w'` 모드로 파일을 열어 무조건 덮어씀
- **해결**: 버전닝 및 중복 체크 로직 추가

#### Backend 수정:
1. **`backend/app/agent/unified_agent_manager.py`**
   - `_save_artifact_to_workspace()` 메서드 개선:
     - 파일 존재 시 내용 비교
     - 동일 내용: 저장 건너뛰기 (`action: "skipped_duplicate"`)
     - 다른 내용: 버전 번호 추가 (`file_v2.py`, `file_v3.py` 등)
   - `_get_versioned_path()` 헬퍼 메서드 추가:
     - 크로스 플랫폼 호환 (Windows/Linux/MacOS)
     - 기존 버전 번호 인식 (`file_v2.py` → `file_v3.py`)
     - 최대 100개 버전 후 타임스탬프 fallback

2. **`backend/app/api/main_routes.py`**
   - `write_artifact_to_workspace()` 함수 동일 로직 적용
   - `get_versioned_path()` 헬퍼 함수 추가

#### 로직 동작:
```
1. 파일 존재 여부 확인
2. 존재 시 → 기존 내용과 비교
   - 동일: skip (action: "skipped_duplicate")
   - 다름: 버전 번호 추가 (action: "created_new_version")
3. 존재하지 않음 → 새 파일 생성 (action: "created")
```

#### 테스트 결과:
```
✓ /tmp/code.py -> /tmp/code_v2.py
✓ /tmp/code_v2.py -> /tmp/code_v3.py
✓ /tmp/app.tsx -> /tmp/app_v2.tsx
✓ /tmp/test_v5.js -> /tmp/test_v6.js
```

### 25. Streaming UI 실시간 업데이트 문제 해결 (2026-01-07)
- **문제**: Conversations UI에서 "실행 중..." 만 표시되고 streaming 내용이 보이지 않음
- **원인 1**: `workflowUpdate` 객체 생성 시 `streaming_content`가 포함되지 않음
- **원인 2**: `liveOutputs` 업데이트가 `agentProgress`에 agent가 있을 때만 동작

#### Frontend 수정:
1. **`frontend/src/components/WorkflowInterface.tsx`**
   - 초기 `workflowUpdate` 객체에 `streaming_content` 필드 추가 (Line 701-702)
   - `updateAgentProgress()`에서 `agentInfo` 존재 여부와 무관하게 `liveOutputs` 업데이트 (Lines 537-562)
   - `getAgentInfo()` 폴백으로 agent title 자동 생성

#### 수정 내용:
```typescript
// Before
const workflowUpdate: WorkflowUpdate = {
  agent: update.agent,
  // ... streaming_content 없음
};

// After
const workflowUpdate: WorkflowUpdate = {
  agent: update.agent,
  streaming_content: update.streaming_content || undefined,
  // ...
};
```

```typescript
// Before - agentInfo 있을 때만 업데이트
const agentInfo = agentProgress.find(a => a.name === nodeName);
if (agentInfo) {
  setLiveOutputs(...);
}

// After - 항상 업데이트 (폴백 title 사용)
const agentInfo = agentProgress.find(a => a.name === nodeName);
const { title: agentTitle } = getAgentInfo(nodeName);  // Fallback
setLiveOutputs(...);  // 조건 없이 항상 실행
```

## 수정 파일 목록 (Issue 24 & 25)

| 순서 | 파일 | 변경 내용 |
|-----|------|---------|
| 1 | `backend/app/agent/unified_agent_manager.py` | 버전닝 로직, _get_versioned_path() 추가 |
| 2 | `backend/app/api/main_routes.py` | 버전닝 로직, get_versioned_path() 추가 |
| 3 | `frontend/src/components/WorkflowInterface.tsx` | streaming_content 전달, liveOutputs 업데이트 개선 |

### 26. TypeScript agentTitle 중복 선언 에러 수정 (2026-01-07)
- **문제**: `Identifier 'agentTitle' has already been declared. (538:19)`
- **원인**: Line 330에서 `const agentTitle = event.agent_title;` 선언 후, Line 538에서 다시 `const { title: agentTitle }` 선언
- **해결**: Line 538의 변수명을 `fallbackTitle`로 변경

```typescript
// Before (에러)
const { title: agentTitle } = getAgentInfo(nodeName);

// After (수정)
const fallbackTitle = getAgentInfo(nodeName).title;
```

### 27. config.py 하드코딩 경로 제거 (2026-01-07)
- **문제**: `get_default_workspace()` 함수에서 Linux/Mac 경로가 `/home/user/workspace`로 하드코딩됨
- **해결**: 환경 변수 우선 참조 + `Path.home()` 사용으로 크로스 플랫폼 호환

```python
# Before (하드코딩)
else:
    return "/home/user/workspace"

# After (크로스 플랫폼)
env_workspace = os.environ.get("DEFAULT_WORKSPACE")
if env_workspace:
    return env_workspace
return str(Path.home() / "workspace")
```

**우선순위**:
1. 환경 변수 `DEFAULT_WORKSPACE` (설정된 경우)
2. 사용자 홈 디렉토리 + `/workspace`

## 수정 파일 목록 (Issue 26 & 27)

| 순서 | 파일 | 변경 내용 |
|-----|------|---------|
| 1 | `frontend/src/components/WorkflowInterface.tsx` | agentTitle → fallbackTitle 변수명 변경 |
| 2 | `backend/app/core/config.py` | get_default_workspace() 하드코딩 제거, 환경변수 우선 |
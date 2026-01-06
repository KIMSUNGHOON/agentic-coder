# Todos
~~* 현재 프로젝트가 Environment에도 호환이 잘 되도록 코드를 수정하고, Frontend UI/UX에도 잘 반영 될 수 있도록 해라.~~
* Frontend 경로 호환성 개선
* 메모리/리소스 최적화
* UI/UX 개선 적용

# Issues
* @debug\s1.png 에 보면은 좀 conversations UI가 너무 비효율적이야... Stream방식이면 실시간으로 token이 생성되는것이 streaming으로 되야
  하는데. 저게 뭔지.. 모르겠네. streaming을 제대로 UI에서 표현 못하는거 같은데. Todos의 UI/UX 개선 적용에 해당 문제를 반영 하도록 해.
* @debug\conversations.log 확인해 보면 실제 대화 내용을 복사 해서 붙혀 넣었는데. 이거 Workflow status나 indicator와 전혀 연동이 되지 않네? 이게 의도 된건지? @debug\backend.log 도 제대로 의도 되로 된건지.. 확인이 필요해 보이네.

# Reference
* backend log는 (@debug\\*.log) 를 뒤질 것
* frontend log는 (@debug\\*.log) 를 뒤질 것

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
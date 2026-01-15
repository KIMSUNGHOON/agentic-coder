# Agentic 2.0 Implementation Plan (Updated 2026-01-15)

## 프로젝트 개요

**목표**: On-premise 로컬 서버 환경에서 실행되는 프로덕션급 Agentic AI 시스템

**핵심 특징**:
- ✅ vLLM + GPT-OSS-120B 사용
- ✅ 로컬 전용 데이터 저장 (외부 유출 차단)
- ✅ OpenAI Cookbook 프롬프팅 기법 적용
- ✅ Chain-of-Thought 추론 지원
- ✅ Structured Outputs (JSON Schema)

---

## 완료된 Phase (Phase 0-4)

### Phase 0: Foundation ✅
- **LLM Client**: vLLM OpenAI-compatible endpoint 지원
  - API Key 불필요 (`api_key="not-needed"`)
  - Dual-endpoint failover
  - Health tracking
- **Router**: Workflow domain classification
- **Tools**: 10+ tools with safety checks
- **Safety**: Tool restrictions, rate limiting

### Phase 1: Workflow Orchestration ✅
- **CodingWorkflow**: Plan → Implement → Test → Review
- **ResearchWorkflow**: Query → Gather → Analyze → Synthesize
- **DataWorkflow**: Load → Analyze → Visualize → Report
- **GeneralWorkflow**: Flexible execution

### Phase 2: Sub-Agent Spawning ✅
- **12 Agent Types**: Code, Research, Data, General
- **Task Decomposer**: Complexity analysis, subtask breakdown
- **Parallel Executor**: Asyncio concurrent execution
- **Result Aggregator**: 4 strategies

### Phase 3: Optimization, Persistence, Observability ✅

**3-1: Optimization**
- LRU Cache with TTL
- LLM Response Cache
- State Optimizer
- Performance Monitor

**3-2: Persistence**
- Session Manager
- Checkpointer Manager (SQLite/PostgreSQL 로컬)
- State Recovery

**3-3: Observability**
- Structured Logger (JSONL, 로컬 파일만)
- Decision Tracker
- Tool Logger
- Metrics Collector (로컬 저장)

### Phase 4: Production Readiness ✅

**4-1: Performance**
- EndpointSelector: Health-based routing
- ContextFilter: Token budget management
- ParallelToolExecutor: Concurrent execution

**4-2: Error Handling**
- ErrorHandler: 8 categories, 4 severity levels
- ErrorRecovery: Exponential backoff
- GracefulDegradation: 4 strategies
- HealthChecker: Component monitoring

**4-3: Documentation**
- USER_GUIDE.md (380 lines)
- API_REFERENCE.md (800 lines)
- CONFIGURATION.md (550 lines)
- TROUBLESHOOTING.md (650 lines)
- DEPLOYMENT.md (700 lines)
- SECURITY.md (NEW - 보안 가이드)

**4-4: Deployment Packaging**
- Dockerfile (로컬 전용)
- docker-compose.yml (로컬 서비스만)
- install.sh
- Kubernetes manifests (로컬 클러스터용)

### 프롬프트 최적화 ✅
- **core/prompts.py** (540 lines)
  - OpenAI Cookbook 기법 적용
  - Few-shot examples
  - Chain-of-Thought with <think> tags
  - Structured outputs (JSON Schema)
  - GPT-OSS-120B 최적화

---

## 현재 진행: Phase 5 - User Interface

### Phase 5-1: CLI 인터페이스 (현재 작업) 🎯

**목표**: Textual 기반 대화형 CLI

**기술 스택**:
- **Textual**: TUI 프레임워크 (60 FPS 인터랙티브)
- **Rich**: 터미널 포맷팅 (프로그레스 바, 테이블)
- **Click**: 명령줄 파싱
- **Prompt Toolkit**: 자동완성, 히스토리

**주요 기능**:

1. **대화형 REPL**
   ```
   agentic> Create a Python function to calculate fibonacci

   [Agent] 🤔 Analyzing task...
   [Agent] 📋 Creating execution plan...
   [Agent] ⚙️  Implementing solution...

   <think>
   Step 1: Define function signature
   Step 2: Implement recursive approach
   Step 3: Add memoization for optimization
   Step 4: Write test cases
   </think>

   [Progress] ████████████████░░░░ 80% - Testing code

   [Result] ✅ Created fibonacci.py with tests
   ```

2. **명령 시스템**
   ```bash
   # 직접 실행
   agentic run "Build REST API"

   # 대화형 모드
   agentic chat

   # 워크플로우 선택
   agentic --workflow coding "Write unit tests"

   # 상태 확인
   agentic status
   agentic history
   agentic health
   ```

3. **실시간 피드백**
   - LLM 호출 상태 (with <think> 프로세스)
   - 도구 실행 진행 상황
   - 서브에이전트 병렬 실행 시각화
   - 체크포인트 자동 저장 알림

4. **시각화 요소**
   - Rich 프로그레스 바
   - 파일 변경사항 트리 뷰
   - 실시간 로그 스크롤러
   - 시스템 상태 표시 (헬스체크)
   - Chain-of-Thought 추론 과정 (옵션)

**보안 고려사항**:
- ✅ 모든 입력/출력 로컬 저장만
- ✅ 세션 데이터 로컬 DB에만 기록
- ✅ 네트워크 통신: vLLM 서버만 허용
- ✅ 민감 정보 마스킹 (필요시)

**파일 구조**:
```
cli/
├── __init__.py
├── app.py              # Textual 메인 앱
├── commands.py         # Click 명령 정의
├── repl.py            # 대화형 REPL
├── components/        # Textual 위젯
│   ├── __init__.py
│   ├── chat_panel.py      # 대화 패널
│   ├── progress_bar.py    # 진행 상황 표시
│   ├── log_viewer.py      # 로그 뷰어
│   ├── status_bar.py      # 상태바
│   ├── cot_viewer.py      # Chain-of-Thought 뷰어
│   └── file_tree.py       # 파일 트리
├── utils/
│   ├── formatter.py    # Rich 포맷팅
│   ├── history.py      # 명령 히스토리 (로컬 파일)
│   └── security.py     # 보안 체크 (외부 통신 차단)
└── config/
    └── cli_config.py   # CLI 설정
```

**구현 단계**:

1. **Step 1: 기본 구조** (1-2일)
   - Click 기반 명령 파싱
   - Textual 기본 레이아웃
   - Rich 포맷팅 유틸리티
   - 보안 설정 검증

2. **Step 2: 대화형 REPL** (2-3일)
   - 프롬프트 입력/출력
   - 세션 관리 (로컬 저장)
   - 명령 히스토리
   - 자동완성

3. **Step 3: 워크플로우 통합** (2-3일)
   - 기존 백엔드 연결
   - 진행 상황 실시간 표시
   - CoT 추론 과정 시각화
   - 에러 처리 및 표시

4. **Step 4: 고급 기능** (3-4일)
   - 서브에이전트 병렬 실행 시각화
   - 체크포인트/복구 UI
   - 커스텀 명령
   - 헬스체크 대시보드
   - 설정 관리 UI

5. **Step 5: 테스트 및 문서화** (1-2일)
   - CLI 테스트
   - 사용자 가이드 업데이트
   - 예제 시나리오
   - 보안 검증

### Phase 5-2: Web UI (선택적)

**기술 스택**:
- **Backend**: FastAPI + WebSocket (로컬만)
- **Frontend**: React + TypeScript
- **State**: Redux Toolkit
- **UI**: Material-UI 또는 Ant Design

**주요 화면**:
1. 대시보드 (워크플로우 상태)
2. 채팅 인터페이스
3. 파일 브라우저
4. 로그 뷰어
5. 메트릭 모니터링 (로컬 Prometheus)
6. CoT 추론 시각화

**보안**:
- HTTPS 로컬 인증서
- localhost 바인딩만
- CORS 로컬 도메인만 허용
- 세션 토큰 로컬 저장

### Phase 5-3: VS Code Extension (선택적)

**기능**:
- 사이드바 패널
- 인라인 diff
- 컨텍스트 메뉴
- 상태바 통합
- CoT 추론 팝업

---

## 기술적 세부사항

### GPT-OSS-120B 프롬프팅 전략

**Chain-of-Thought 활용**:
```python
messages = [
    {
        "role": "system",
        "content": """You are an expert software engineer.

Use <think> tags to show your reasoning process.
Follow this structure:
1. Analyze the requirements
2. Plan your approach
3. Execute the solution
4. Verify the result
"""
    },
    {
        "role": "user",
        "content": "Create a REST API endpoint for user registration"
    }
]

# Response includes:
# <think>
# Step 1: Need User model with email, password fields
# Step 2: Hash password with bcrypt
# Step 3: Validate email format
# Step 4: Create POST /register endpoint
# </think>
#
# Here's the implementation:
# ...
```

**Structured Outputs**:
```python
response = await llm_client.chat_completion(
    messages=messages,
    temperature=0.3,
    response_format={
        "type": "json_schema",
        "json_schema": {
            "name": "code_plan",
            "strict": True,  # GPT-OSS strict mode
            "schema": {
                "type": "object",
                "properties": {
                    "reasoning": {"type": "string"},
                    "steps": {"type": "array", "items": {"type": "string"}},
                    "files": {"type": "array", "items": {"type": "string"}}
                },
                "required": ["reasoning", "steps", "files"]
            }
        }
    }
)
```

### 보안 아키텍처

**데이터 흐름**:
```
User Input (CLI)
    ↓
Local Storage (/data, /logs)
    ↓
Agentic Core (localhost)
    ↓
vLLM Server (local network only)
    ↓
Response Storage (local only)
    ↓
User Output (CLI)

❌ No external network communication
✅ All data stays on local server
```

**네트워크 격리**:
```python
# security/network_policy.py
class NetworkPolicy:
    ALLOWED_HOSTS = [
        "localhost",
        "127.0.0.1",
        os.getenv("VLLM_SERVER_IP")  # 로컬 vLLM 서버만
    ]

    @staticmethod
    def validate_endpoint(url: str) -> bool:
        """외부 통신 차단"""
        parsed = urlparse(url)
        if parsed.hostname not in NetworkPolicy.ALLOWED_HOSTS:
            raise SecurityError(
                f"External communication blocked: {url}"
            )
        return True
```

### 성능 최적화

**vLLM 서버 설정** (참고):
```bash
# vLLM 서버 실행 (별도 서버)
python -m vllm.entrypoints.openai.api_server \
    --model gpt-oss-120b \
    --host 0.0.0.0 \
    --port 8000 \
    --tensor-parallel-size 2 \
    --max-num-seqs 32
```

**Agentic 클라이언트 설정**:
```yaml
llm:
  model_name: "gpt-oss-120b"

  # CoT 설정
  chain_of_thought:
    enabled: true
    reasoning_effort: "medium"  # low/medium/high
    show_thinking: false  # 사용자에게 <think> 숨김

  # Endpoints (로컬 vLLM만)
  endpoints:
    - url: "http://<vLLM-server-IP>:8000/v1"
      name: "local-vllm"
      api_key: "not-needed"
      timeout: 120
```

---

## 마일스톤

### 완료 (2026-01-14)
- ✅ Phase 0-4: Backend core system
- ✅ Prompt optimization for GPT-OSS-120B
- ✅ Security documentation

### 진행 중 (2026-01-15)
- 🎯 Phase 5-1: CLI interface (Step 1-5)

### 예정 (2026-01-16~)
- 📅 Phase 5-2: Web UI (optional)
- 📅 Phase 5-3: VS Code extension (optional)

---

## 참고 자료

### 프롬프팅
- [OpenAI Cookbook](https://cookbook.openai.com/)
- [Structured Outputs](https://cookbook.openai.com/examples/structured_outputs_intro)
- [GPT-OSS GitHub](https://github.com/openai/gpt-oss)
- [Few-shot Learning](https://cookbook.openai.com/examples/gpt-5/gpt-5_prompting_guide)

### 보안
- [OWASP Top 10](https://owasp.org/www-project-top-ten/)
- [GDPR Compliance](https://gdpr.eu/)
- [Data Privacy Best Practices](https://www.nist.gov/privacy-framework)

### CLI Development
- [Textual Documentation](https://textual.textualize.io/)
- [Rich Documentation](https://rich.readthedocs.io/)
- [Click Documentation](https://click.palletsprojects.com/)

---

## 연락처 및 지원

- **프로젝트**: Agentic 2.0
- **환경**: On-premise, Local Server Only
- **보안**: Local data storage, No external transmission
- **LLM**: vLLM + GPT-OSS-120B

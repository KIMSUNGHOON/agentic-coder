# 세션 연속 가이드 (Session Continuation Guide)

이 문서는 새로운 Claude Code 세션에서 Agentic 2.0 프로젝트 작업을 이어서 진행하기 위한 가이드입니다.

---

## 빠른 시작 (Quick Start)

### 1. 프로젝트 상태 확인
```bash
cd /home/user/agentic-coder

# 최신 상태 문서 읽기
cat PROJECT_STATUS.md
```

### 2. Git 브랜치 확인
```bash
git branch --show-current
# 결과: claude/fix-hardcoded-config-QyiND

git log --oneline -5
# 최근 커밋 확인
```

### 3. 테스트 실행
```bash
# 통합 테스트
python3 test_cli_integration.py

# 결과: ✅ Passed: 2/2
```

### 4. CLI 실행 (선택)
```bash
cd agentic-ai
python -m cli.commands chat
```

---

## 현재 프로젝트 상태

### Phase 완료 상황
- ✅ **Phase 0**: Foundation (핵심 인프라)
- ✅ **Phase 1**: Workflows (워크플로)
- ✅ **Phase 2**: Sub-Agents (서브 에이전트)
- ✅ **Phase 3**: Tools (도구)
- ✅ **Phase 4**: Optimization & Production (최적화 및 프로덕션)
- ✅ **Phase 5-1**: CLI Interface (CLI 인터페이스)
- ⏳ **Phase 5-2**: Web UI (선택사항, 미착수)
- ⏳ **Phase 5-3**: VS Code Extension (선택사항, 미착수)

### 최근 작업 (2026-01-15)
1. **Phase 5-1 CLI 인터페이스 완료**
   - Textual 기반 대화형 TUI
   - 백엔드 완전 통합
   - 7개 CLI 명령어
   - 18개 파일, ~2,681 lines

2. **버그 수정**
   - ✅ `IntentClassification.to_dict()` 메서드 추가
   - ✅ YAML config fork bomb 파싱 오류 수정
   - ✅ 모든 테스트 통과

3. **문서 업데이트**
   - ✅ PROJECT_STATUS.md 생성
   - ✅ PHASE_5-1_COMPLETION.md 업데이트
   - ✅ IMPLEMENTATION_PLAN.md 업데이트

### 코드 통계
- **총 파일**: 82개
- **총 코드**: ~24,333 lines
- **테스트**: 100% passing
- **문서**: ~6,000+ lines

---

## 중요 파일 위치

### 핵심 코드
```
agentic-ai/
├── core/               # 핵심 시스템 (~2,890 lines)
│   ├── llm_client.py       # vLLM 통신
│   ├── router.py           # 워크플로 라우팅 (to_dict 추가됨)
│   ├── tool_safety.py      # 보안 관리
│   ├── config_loader.py    # 설정 로드
│   └── state.py            # 상태 관리
│
├── workflows/          # 워크플로 (~1,746 lines)
│   ├── orchestrator.py     # 전체 조율
│   ├── coding_workflow.py
│   ├── research_workflow.py
│   ├── data_workflow.py
│   └── general_workflow.py
│
├── agents/             # 서브에이전트 (~1,769 lines)
│   ├── task_decomposer.py
│   ├── sub_agent.py
│   ├── sub_agent_manager.py
│   └── parallel_executor.py
│
├── cli/                # CLI 인터페이스 (~2,681 lines)
│   ├── app.py              # Textual 앱
│   ├── backend_bridge.py   # 백엔드 통합
│   ├── commands.py         # Click 명령어
│   ├── components/         # UI 컴포넌트 (5개)
│   └── utils/              # 유틸리티 (3개)
│
└── config/
    └── config.yaml         # 메인 설정 (수정됨)
```

### 문서
```
agentic-ai/docs/
├── IMPLEMENTATION_PLAN.md     # 전체 구현 계획
├── SECURITY.md                # 보안 가이드
├── USER_GUIDE.md              # 사용자 가이드
├── API_REFERENCE.md           # API 레퍼런스
├── CONFIGURATION.md           # 설정 가이드
├── DEPLOYMENT.md              # 배포 가이드
└── TROUBLESHOOTING.md         # 문제 해결

최상위 문서:
├── PROJECT_STATUS.md          # 프로젝트 전체 상황 (NEW)
├── PHASE_5-1_COMPLETION.md    # Phase 5-1 완료 문서
└── SESSION_CONTINUATION_GUIDE.md  # 이 문서
```

### 테스트
```
test_cli_integration.py        # CLI 통합 테스트 (2/2 passing)
agentic-ai/examples/           # 예제 테스트 7개
agentic-ai/tests/              # 유닛 테스트 2개
```

---

## 환경 설정 확인

### 1. Python 의존성
```bash
pip list | grep -E "(textual|click|rich|openai|langgraph)"

# 필수 패키지:
# - textual>=0.47.0
# - prompt-toolkit>=3.0.43
# - click>=8.0.0
# - rich>=13.0.0
# - openai>=1.0.0
# - langgraph (LangGraph)
```

### 2. vLLM 서버 (필수)
```bash
# Primary endpoint
curl http://localhost:8001/v1/models

# Secondary endpoint
curl http://localhost:8002/v1/models

# 둘 다 응답하지 않으면 vLLM 서버 시작 필요
```

### 3. 설정 파일
```bash
ls -la agentic-ai/config/config.yaml
# 파일이 존재해야 함
```

---

## 일반적인 작업 시나리오

### 시나리오 1: 새 기능 추가
```bash
# 1. 최신 상태 확인
git pull origin claude/fix-hardcoded-config-QyiND

# 2. PROJECT_STATUS.md 읽고 현재 상태 파악

# 3. 새 브랜치 생성 (또는 기존 브랜치 사용)
git checkout -b claude/new-feature-<SESSION_ID>

# 4. 코드 작성

# 5. 테스트
python3 test_cli_integration.py

# 6. 커밋 및 푸시
git add -A
git commit -m "feat: Add new feature"
git push -u origin claude/new-feature-<SESSION_ID>
```

### 시나리오 2: 버그 수정
```bash
# 1. 버그 재현
python3 -c "from cli.backend_bridge import get_bridge; ..."

# 2. 코드 수정

# 3. 테스트로 검증
python3 test_cli_integration.py

# 4. PROJECT_STATUS.md 업데이트 (버그 수정 내역 추가)

# 5. 커밋
git add -A
git commit -m "fix: Fix bug description

Problem: ...
Solution: ...
Testing: ...
Status: ✅ Fixed and verified"
```

### 시나리오 3: Phase 5-2 (Web UI) 시작
```bash
# 1. 현재 상태 확인
cat PROJECT_STATUS.md | grep "Phase 5-2"

# 2. Phase 5-2 계획 읽기
cat agentic-ai/docs/IMPLEMENTATION_PLAN.md | grep -A 20 "Phase 5-2"

# 3. 새 브랜치
git checkout -b claude/phase5-2-webui-<SESSION_ID>

# 4. 디렉토리 구조 생성
mkdir -p agentic-ai/web/{api,frontend}

# 5. FastAPI 백엔드 구현
# 6. React 프론트엔드 구현
# 7. WebSocket 통합
```

---

## 컨텍스트 정보 (새 세션용)

### 프로젝트 목적
On-premise 환경에서 GPT-OSS-120B를 사용하는 AI 코딩 어시스턴트 시스템

### 핵심 제약사항
1. **로컬 전용**: 모든 데이터는 로컬 저장, 외부 전송 금지
2. **vLLM**: OpenAI-compatible API 사용, API key 불필요
3. **GPT-OSS-120B**: Chain-of-Thought with `<think>` tags 지원
4. **보안**: 입력 검증, 명령어 안전성, 파일 보호

### 아키텍처 개요
```
CLI (Textual) → BackendBridge → WorkflowOrchestrator
                                        ↓
                                 IntentRouter (분류)
                                        ↓
                              Workflow 선택 및 실행
                              (Coding/Research/Data/General)
                                        ↓
                              SubAgentManager (복잡한 작업)
                                        ↓
                              Tools 실행 (Git/FileSystem/Process/Search)
                                        ↓
                              Result Aggregation → UI Update
```

### 기술 스택
- **Language**: Python 3.10+
- **LLM**: GPT-OSS-120B via vLLM
- **Framework**: LangGraph (워크플로)
- **CLI**: Textual + Click + Rich
- **Storage**: SQLite/PostgreSQL (로컬)
- **Config**: YAML

---

## 문제 해결 체크리스트

### 테스트 실패 시
```bash
# 1. 의존성 확인
pip install -r agentic-ai/requirements.txt

# 2. 설정 파일 확인
cat agentic-ai/config/config.yaml | grep "model_name"

# 3. vLLM 서버 확인
curl http://localhost:8001/v1/models

# 4. Python path 확인
python3 -c "import sys; print('\n'.join(sys.path))"

# 5. 로그 확인
ls -la logs/
tail -n 50 logs/agentic.log
```

### Import 에러 시
```bash
# 1. 작업 디렉토리 확인
pwd
# 결과: /home/user/agentic-coder

# 2. Python path 추가
export PYTHONPATH="/home/user/agentic-coder/agentic-ai:$PYTHONPATH"

# 3. 재테스트
python3 test_cli_integration.py
```

### Git 이슈 시
```bash
# 1. 현재 브랜치 확인
git branch --show-current

# 2. 원격 브랜치 확인
git branch -r

# 3. 변경사항 확인
git status

# 4. 최신 상태로 업데이트
git pull origin claude/fix-hardcoded-config-QyiND
```

---

## 다음 단계 옵션

### 옵션 A: Phase 5-2 Web UI (권장)
**예상 시간**: 2-3주

**주요 작업**:
1. FastAPI REST API 구현
2. React 프론트엔드
3. WebSocket 실시간 통신
4. Web 기반 CoT 뷰어
5. 사용자 인증 (로컬)

**시작 명령**:
```bash
cat agentic-ai/docs/IMPLEMENTATION_PLAN.md | grep -A 50 "Phase 5-2"
```

### 옵션 B: Phase 5-3 VS Code Extension
**예상 시간**: 3-4주

**주요 작업**:
1. VS Code Extension 스캐폴딩
2. Language Server Protocol 통합
3. 인라인 제안 기능
4. 사이드바 채팅 패널
5. Command palette 명령어

**시작 명령**:
```bash
cat agentic-ai/docs/IMPLEMENTATION_PLAN.md | grep -A 50 "Phase 5-3"
```

### 옵션 C: 추가 개선
- Few-shot examples 추가 (OpenAI Cookbook)
- 더 많은 도구 추가
- 성능 최적화
- 추가 워크플로
- 문서 개선

---

## 유용한 명령어 모음

### 프로젝트 탐색
```bash
# 코드 통계
find agentic-ai -name "*.py" | xargs wc -l | tail -1

# 파일 목록
tree agentic-ai -L 2 -I "__pycache__|*.pyc"

# 최근 변경 파일
git log --name-only --oneline -5
```

### 개발
```bash
# 문법 체크
python3 -m py_compile agentic-ai/cli/app.py

# Import 테스트
python3 -c "from cli.backend_bridge import get_bridge; print('OK')"

# 타입 체크 (optional)
mypy agentic-ai/cli/app.py
```

### 테스트
```bash
# CLI 통합 테스트
python3 test_cli_integration.py

# 특정 예제 실행
cd agentic-ai
python3 examples/test_router.py

# 모든 pytest 실행
pytest agentic-ai/tests/
```

### Git
```bash
# 변경사항 요약
git diff --stat

# 특정 파일 변경 이력
git log --oneline --follow agentic-ai/core/router.py

# 브랜치 비교
git diff main..claude/fix-hardcoded-config-QyiND --stat
```

---

## 참고 문서 링크

### 필수 문서
- [PROJECT_STATUS.md](PROJECT_STATUS.md) - 전체 프로젝트 상황
- [PHASE_5-1_COMPLETION.md](PHASE_5-1_COMPLETION.md) - Phase 5-1 완료 내역
- [agentic-ai/docs/IMPLEMENTATION_PLAN.md](agentic-ai/docs/IMPLEMENTATION_PLAN.md) - 구현 계획

### 사용자 가이드
- [agentic-ai/docs/USER_GUIDE.md](agentic-ai/docs/USER_GUIDE.md)
- [agentic-ai/cli/README.md](agentic-ai/cli/README.md)

### 개발 가이드
- [agentic-ai/docs/API_REFERENCE.md](agentic-ai/docs/API_REFERENCE.md)
- [agentic-ai/docs/CONFIGURATION.md](agentic-ai/docs/CONFIGURATION.md)

### 보안
- [agentic-ai/docs/SECURITY.md](agentic-ai/docs/SECURITY.md)

### 문제 해결
- [agentic-ai/docs/TROUBLESHOOTING.md](agentic-ai/docs/TROUBLESHOOTING.md)

---

## 버그 이력

### 수정된 버그
1. **IntentClassification.to_dict() 누락** (2026-01-15)
   - 위치: `core/router.py`
   - 해결: to_dict() 메서드 추가
   - 상태: ✅ 수정 완료

2. **YAML config fork bomb 파싱** (2026-01-15)
   - 위치: `config/config.yaml`
   - 해결: 따옴표로 문자열 감싸기
   - 상태: ✅ 수정 완료

3. **LangGraph Recursion Limit 초과** (2026-01-15)
   - 위치: `workflows/base_workflow.py`
   - 증상: "Recursion limit of 25 reached"
   - 해결: ainvoke() 호출 시 recursion_limit=100 설정
   - 설정: `config/config.yaml`에 recursion_limit 추가
   - 상태: ✅ 수정 완료

### 현재 알려진 이슈
- 없음 (모든 테스트 통과, 모든 버그 수정됨)

**참고**: 자세한 버그 수정 내역은 [BUG_FIX_LOG.md](BUG_FIX_LOG.md) 참조

---

## 연락처

- **Repository**: KIMSUNGHOON/agentic-coder
- **Branch**: claude/fix-hardcoded-config-QyiND
- **Latest Commit**: 13b5c48 (버그 수정 및 문서 업데이트)

---

**최종 업데이트**: 2026-01-15
**작성자**: Claude (Agentic 2.0 Development Assistant)
**상태**: ✅ Phase 5-1 완료, 프로덕션 준비 완료

---

## 새 세션 시작 체크리스트

- [ ] `cd /home/user/agentic-coder`
- [ ] `cat PROJECT_STATUS.md` 읽기
- [ ] `git status` 확인
- [ ] `python3 test_cli_integration.py` 실행
- [ ] vLLM 서버 확인 (`curl localhost:8001/v1/models`)
- [ ] 다음 작업 결정 (Phase 5-2, 5-3, 또는 개선)
- [ ] 필요 시 새 브랜치 생성

준비 완료! 🚀

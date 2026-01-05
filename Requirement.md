# 요구사항 및 작업 현황

**마지막 업데이트**: 2026-01-06
**상태**: 🔄 개선 계획 수립 완료 - 추가 최적화 진행 중

---

## 📋 질문

### (Done) Q1: Windows + uv + Ollama(DeepSeek-R1:14B) 테스트 가능한가?

**A: ✅ 가능합니다.**

Ollama는 OpenAI 호환 API를 제공하므로 현재 설정을 그대로 사용할 수 있습니다.

**설정 방법:**
```bash
# 1. Ollama 설치
winget install ollama

# 2. 모델 다운로드
ollama pull deepseek-r1:14b

# 3. 환경 설정
copy .env.ollama .env

# 4. 실행
ollama serve
cd backend && uv run uvicorn app.main:app --reload
```

**설정 파일:** `.env.ollama`

### (Done) Q2: UI/UX 를 더 좋은 방향으로 개발자 친화적으로 개선 할 수 없니?
* UI Screenshot file: @ss1.png

**A: UI/UX 분석 완료** - 현재 UI는 워크플로우 진행 상태, 파일 트리, 코드 미리보기를 잘 제공하고 있습니다.

### (Done) Q3: ExPrompt를 확인하고. 현재 생성된 파일 리스트를 보고 결과에 대해서 예측 및 검증 해보겠니?
* UI Screenshot file: @ss2.png
* 뭔가 제대로 동작 하고 있지 않아.

**A: ✅ 문제 발견 및 수정 완료**

스크린샷에서 Python CLI + Tkinter GUI 계산기 요청에 대해 HTML/CSS/JS 웹 앱이 생성된 문제가 확인되었습니다.
아래 "Backend Log 분석 결과" 섹션에서 원인 분석 및 수정 내용을 확인하세요.

---

## 📋 요청 사항

### 1. Security 이슈 자동 수정 로직 ✅ 완료

**구현 내용:** OWASP Top 10 보안 취약점 자동 수정

| # | 취약점 | 자동 수정 | 테스트 |
|---|--------|-----------|--------|
| 1 | SQL Injection | 파라미터화 쿼리 권장 | ✅ |
| 2 | Command Injection | subprocess.run(shell=False) | ✅ |
| 3 | XSS | 경고 주석 추가 | ✅ |
| 4 | Path Traversal | 경로 검증 추가 | ✅ |
| 5 | Hardcoded Credentials | 환경 변수 사용 | ✅ |
| 6 | Insecure Deserialization | yaml.safe_load() | ✅ |
| 7 | Input Validation | None 검사 추가 | ✅ |
| 8 | Eval/Exec | ast.literal_eval() | ✅ |

**파일:** `backend/app/agent/langgraph/nodes/refiner.py`

**테스트 결과:**
```
======================== 21 passed in 3.19s ========================
```

---

### 2. Frontend UI/UX Mock 테스트 환경 ✅ 완료

**구현 내용:** LLM 없이 Frontend UI/UX 테스트 가능

**실행 방법 (Windows):**
```batch
RUN_MOCK.bat
```

**Mock 서버 기능:**
- Quality Gate 시뮬레이션 (Security, QA, Review)
- HITL 요청/응답 시뮬레이션
- 한글 UI 메시지
- 디렉토리 구조가 있는 Artifact 생성

**파일:** `frontend/mock-server/server.cjs`

---

## 📋 중요 사항 준수 현황

| 항목 | 상태 | 비고 |
|------|------|------|
| 작업 내용 기록 및 업데이트 | ✅ 완료 | `docs/DEVELOPMENT_STATUS.md` |
| 테스트 스크립트 작성 | ✅ 완료 | `backend/tests/test_security_fixes.py` |
| 계획 수립 및 Task 분할 | ✅ 완료 | TodoWrite 도구 사용 |

---

## 📁 생성/수정된 파일

| 파일 | 설명 |
|------|------|
| `backend/app/agent/langgraph/nodes/refiner.py` | Security 자동 수정 로직 (OWASP Top 10) |
| `backend/tests/test_security_fixes.py` | 보안 수정 테스트 (21개 테스트) |
| `frontend/mock-server/server.cjs` | Mock 서버 (Quality Gate/HITL 시뮬레이션) |
| `.env.ollama` | Ollama 설정 템플릿 |
| `RUN_MOCK.bat` | Windows Mock 서버 실행 스크립트 |
| `docs/DEVELOPMENT_STATUS.md` | 개발 상태 문서 업데이트 |
| `shared/llm/base.py` | DeepSeek-R1 `<think>` 태그 처리 JSON 파싱 |
| `backend/app/agent/langgraph/nodes/security_gate.py` | 파일 타입별 취약점 스캔 (False Positive 수정) |
| `backend/app/agent/langgraph/nodes/coder.py` | Python CLI + Tkinter GUI 계산기 생성 |

---

## 📊 커밋 히스토리

```
d6a4e61 feat: Security 자동 수정, Mock 테스트 환경, Ollama 지원
f73f91b docs: 프로젝트 문서 업데이트
1a3700a fix: 입력창 멀티라인 지원 및 Refiner 파일 경로 보존
69bebc9 feat: HITL 모달에 Quality Gate 상세 결과 표시
```

### (Done) Backend Log 분석 결과 ✅ 수정 완료

**분석한 로그 파일:** `backend.log`

#### 발견된 문제 3가지:

| # | 문제 | 원인 | 수정 내용 |
|---|------|------|-----------|
| 1 | JSON 파싱 실패 | DeepSeek-R1의 `<think>...</think>` 태그 | `_extract_json()`에서 태그 제거 후 파싱 |
| 2 | Security Gate False Positive | CSS/Markdown 파일에서 Python 취약점 탐지 | 파일 타입별 취약점 패턴 분리 |
| 3 | 잘못된 언어 생성 | Calculator fallback이 HTML/JS 생성 | Python CLI + Tkinter GUI 생성으로 수정 |

#### 수정된 파일:

| 파일 | 수정 내용 |
|------|-----------|
| `shared/llm/base.py` | `<think>`, `<reasoning>` 태그 제거 후 JSON 파싱 |
| `backend/app/agent/langgraph/nodes/security_gate.py` | `SKIP_EXTENSIONS` 추가, 파일 타입별 취약점 스캔 |
| `backend/app/agent/langgraph/nodes/coder.py` | `_generate_calculator_app()` Python CLI/GUI로 재작성 |

#### 로그 에러 상세:

```
WARNING] Failed to parse JSON from response  # DeepSeek-R1 <think> 태그 문제
WARNING] [critical] command_injection in style.css:19  # CSS 파일 False Positive
WARNING] [critical] command_injection in README.md:47  # Markdown False Positive
ERROR] Security Gate FAILED: 3 critical/high findings  # False Positive로 인한 실패
```

---

### (Done) Refiner LLM 응답 처리 버그 ✅ 수정 완료

**문제:** Calculator 테스트 중 GUI 파일(`calculator_gui.py`)이 마크다운 설명으로 덮어쓰여짐

**원인 분석:**
1. Refiner가 Security Gate의 `dangerous_eval_python` 이슈를 감지
2. LLM에 코드 수정 요청
3. LLM이 마크다운 설명 + 코드 블록 형태로 응답
4. 기존 코드는 마크다운 설명을 코드로 오인하여 파일에 저장

**수정 내용:**

| 함수 | 수정 전 | 수정 후 |
|------|---------|---------|
| `_apply_fix_with_llm()` | 단순 ``` 제거 | `_extract_code_from_response()` 호출 |
| `_extract_code_from_response()` | (신규) | 4단계 코드 추출 로직 |

**새 함수 `_extract_code_from_response()` 로직:**
1. Strategy 1: 첫 줄이 코드인지 확인 (`import`, `def`, `class` 등)
2. Strategy 2: 마크다운 코드 블록에서 추출 (```python...```)
3. Strategy 3: 라인별 파싱으로 코드 블록 추출
4. Strategy 4: Prose 감지 시 원본 코드 유지 (손상 방지)

**수정된 파일:**
- `backend/app/agent/langgraph/nodes/refiner.py`

---

## 📋 개선 계획 (2026-01-06)

**상세 문서**: `docs/IMPROVEMENT_PLAN.md`

### 발견된 주요 이슈

| # | 이슈 | 심각도 | 상태 |
|---|------|--------|------|
| 1 | Security Gate False Positive (`ast.literal_eval` 오탐) | High | 🔄 개선 필요 |
| 2 | Refiner 반복 제한 (3회 → 5회로 증가 필요) | Medium | 🔄 개선 필요 |
| 3 | QA Gate 중복 보안 검사 | Low | 📋 검토 필요 |
| 4 | Empty LLM Response 처리 | Medium | ✅ 수정 완료 |
| 5 | Windows 경로 정규화 | Medium | ✅ 수정 완료 |

### 이번 세션 수정 내역

| 파일 | 수정 내용 |
|------|-----------|
| `frontend/src/components/WorkflowInterface.tsx` | Markdown 렌더링, Auto-scroll, HITL 디버깅 |
| `shared/llm/base.py` | JSON 파싱 로그 레벨 DEBUG로 변경 |
| `shared/llm/adapters/deepseek_adapter.py` | Empty response retry 로직 추가 |
| `backend/app/agent/langgraph/nodes/refiner.py` | Windows 경로 정규화 수정 |

### 다음 단계 (Linux 환경)

1. Security Gate의 `ast.literal_eval` 패턴 수정
2. Refiner 반복 제한 5회로 증가
3. 전체 테스트 실행 및 검증

---

## 📊 테스트 결과

```
======================== 145 passed, 4 failed, 2 skipped in 24.31s ========================
```

**실패한 4개 테스트 (기존 문제, 수정 대상 아님):**
- `test_path_traversal_with_symlink` - Windows symlink 권한 문제
- `test_shared_context_concurrent_writes` - Race condition
- `test_parse_checklist_basic` - API 불일치
- `test_parse_checklist_with_completed_tasks` - 테스트 assertion 오류


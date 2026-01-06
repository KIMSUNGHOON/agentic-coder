# Agent Prompt Engineering 호환성 감사 보고서

**작성일**: 2026-01-06
**버전**: 1.0
**목적**: DeepSeek-R1, Qwen3, GPT-OSS 모델 간 에이전트 프롬프트 호환성 분석 및 개선 계획

---

## 1. 개요

이 문서는 TestCodeAgent의 모든 에이전트 노드에 대한 프롬프트 엔지니어링 호환성 전수 조사 결과입니다. 각 모델별 특성과 에이전트 구현 상태를 분석하고, 개선이 필요한 부분을 식별합니다.

### 1.1 지원 모델 목록
| 모델 | 특징 | 프롬프트 형식 |
|------|------|---------------|
| **DeepSeek-R1** | 추론 모델, `<think></think>` 태그 필수 | Chain-of-Thought with think tags |
| **Qwen3** | 범용 코딩 모델 | Standard prompts (no special tags) |
| **GPT-OSS** | OpenAI Harmony 포맷, 내부 채널 사용 | Structured reasoning (no think tags) |

### 1.2 핵심 차이점
```
DeepSeek-R1: <think>reasoning</think> → final answer
Qwen3:       Direct response (no special tags)
GPT-OSS:     Internal Harmony channels → final response
```

---

## 2. 에이전트 노드 호환성 분석

### 2.1 호환성 상태 요약

| 노드 | 파일 경로 | 모델 인식 | 상태 | 우선순위 |
|------|-----------|-----------|------|----------|
| Coder | `nodes/coder.py` | ✅ | 양호 | - |
| Refiner | `nodes/refiner.py` | ✅ | 양호 | - |
| Reviewer | `nodes/reviewer.py` | ⚠️ | 부분적 | Medium |
| Architect | `nodes/architect.py` | ❌ | 미구현 | High |
| RCA Analyzer | `nodes/rca_analyzer.py` | ❌ | 문제있음 | **Critical** |
| Security Gate | `nodes/security_gate.py` | N/A | 불필요 | - |
| QA Gate | `nodes/qa_gate.py` | N/A | 불필요 | - |
| Aggregator | `nodes/aggregator.py` | N/A | 불필요 | - |
| Persistence | `nodes/persistence.py` | N/A | 불필요 | - |
| Human Approval | `nodes/human_approval.py` | N/A | 불필요 | - |
| Supervisor | `nodes/supervisor.py` | ✅ | 양호 | - |

### 2.2 상세 분석

#### ✅ 양호 (Model-Aware)

**1. Coder Node** (`backend/app/agent/langgraph/nodes/coder.py`)
- **구현 방식**: `_get_code_generation_prompt()` 함수로 모델별 프롬프트 분기
- **지원 모델**: Qwen, DeepSeek, Generic (GPT-OSS 포함)
- **코드 위치**: Line 33-116

```python
def _get_code_generation_prompt(user_request: str, task_type: str) -> tuple:
    model_type = settings.get_coding_model_type
    if model_type == "qwen":
        # Qwen specific prompt
    elif model_type == "deepseek":
        # DeepSeek with <think> tags
    else:
        # Generic/GPT-OSS prompt
```

**2. Refiner Node** (`backend/app/agent/langgraph/nodes/refiner.py`)
- **구현 방식**: `get_refiner_analysis_prompt()` 함수로 모델별 프롬프트 분기
- **지원 모델**: DeepSeek, GPT-OSS, Generic/Qwen
- **코드 위치**: Line 81-181

```python
def get_refiner_analysis_prompt(model_type: str, issues: list, ...):
    if model_type == "deepseek":
        return """<think>...</think>"""
    elif model_type in ("gpt-oss", "gpt"):
        return """## Issues to Fix..."""
    else:
        return """Fix the following code issues..."""
```

**3. Supervisor** (`backend/core/supervisor.py`)
- **구현 방식**: `settings.get_reasoning_model_type`으로 모델 감지 후 프롬프트 선택
- **지원 모델**: DeepSeek, GPT-OSS, Generic
- **수정 이력**: 2026-01-06 세션에서 GPT-OSS 프롬프트 분리 완료

---

#### ⚠️ 부분적 호환 (Needs Improvement)

**1. Reviewer Node** (`backend/app/agent/langgraph/nodes/reviewer.py`)

**현재 상태**:
- LLMProviderFactory 사용 시: 모델 어댑터가 자동으로 프롬프트 처리
- 직접 HTTP 호출 시: Generic 프롬프트만 사용 (Line 196-209)

**문제점**:
```python
# Line 196-209: Direct HTTP call uses generic prompt only
prompt = f"""You are an expert code reviewer..."""
# No model-specific adaptation
```

**개선 방안**:
```python
def _get_review_prompt(model_type: str, review_context: str) -> str:
    if model_type == "deepseek":
        return f"""<think>
1. Analyze code correctness
2. Check security issues
3. Evaluate performance
</think>
{review_context}"""
    elif model_type == "gpt-oss":
        return f"""## Code Review Task
{review_context}
Return in JSON format..."""
    else:
        return f"""Review the following code...\n{review_context}"""
```

---

#### ❌ 문제 있음 (Critical Issues)

**1. RCA Analyzer Node** (`backend/app/agent/langgraph/nodes/rca_analyzer.py`)

**심각도**: 🔴 Critical

**현재 상태**:
- DeepSeek-R1 전용 프롬프트 하드코딩 (Line 17)
- 모든 모델에 `<think>` 태그 출력 (Line 80-97)

```python
# Line 17: Hardcoded import
from shared.prompts.deepseek_r1 import DEEPSEEK_R1_LOOP_ANALYSIS_PROMPT

# Line 80-97: Always generates <think> tags
rca_analysis = f"""<think>
1. Pattern Analysis: Reviewing {len(issues)} issues...
...
</think>"""
```

**문제점**:
- GPT-OSS, Qwen 사용 시에도 `<think>` 태그가 출력됨
- 모델 타입 감지 로직 없음
- 응답 파싱 시 `<think>` 태그가 UI에 노출될 수 있음

**개선 필요 작업**:
1. 모델 타입 감지 로직 추가
2. 모델별 프롬프트 분기 구현
3. 응답에서 `<think>` 태그 조건부 생성

---

**2. Architect Node** (`backend/app/agent/langgraph/nodes/architect.py`)

**심각도**: 🟡 High

**현재 상태**:
- LLM 통합 미완료 (Line 188-189)
- Rule-based 폴백만 사용 중

```python
# Line 188-189: TODO comment indicating incomplete integration
# TODO: Integrate with DeepSeek-R1 for intelligent design
architecture = _generate_architecture(user_request, workspace_root, supervisor_analysis)
```

**문제점**:
- 프롬프트는 정의되어 있으나 (Line 25-120) 실제 LLM 호출 없음
- `_generate_architecture()` 함수가 키워드 매칭 기반 규칙만 사용
- 복잡한 프로젝트 구조 설계 시 품질 저하

**개선 필요 작업**:
1. LLM 통합 구현 (coder.py 패턴 참조)
2. 모델별 시스템 프롬프트 분기
3. 폴백 로직 유지하되 LLM 우선 시도

---

## 3. LLM Provider 아키텍처 분석

### 3.1 파일 구조
```
shared/llm/
├── __init__.py
├── base.py                    # BaseLLMProvider 추상 클래스
└── adapters/
    ├── __init__.py
    ├── deepseek_adapter.py    # DeepSeek-R1 어댑터
    ├── gpt_oss_adapter.py     # GPT-OSS 어댑터
    ├── qwen_adapter.py        # Qwen 어댑터
    └── generic_adapter.py     # 범용 어댑터
```

### 3.2 어댑터 구현 상태

| 어댑터 | 프롬프트 포맷팅 | 응답 파싱 | Think 태그 처리 |
|--------|-----------------|-----------|-----------------|
| DeepSeek | ✅ | ✅ | ✅ 추출 및 분리 |
| GPT-OSS | ✅ | ✅ | N/A (Harmony 채널) |
| Qwen | ✅ | ✅ | N/A |
| Generic | ✅ | ✅ | ✅ 폴백 처리 |

### 3.3 응답 파싱 로직 (`base.py:_extract_json`)
```python
def _extract_json(self, text: str) -> Optional[Dict]:
    # Step 1: Remove <think>...</think> tags
    cleaned_text = re.sub(r'<think>.*?</think>', '', text, flags=re.DOTALL)

    # Step 2: Remove other wrapper tags
    cleaned_text = re.sub(r'<reasoning>.*?</reasoning>', '', cleaned_text, flags=re.DOTALL)

    # Step 3-6: JSON extraction logic
    ...
```

**결론**: LLM Provider 레이어는 잘 설계되어 있으며, 대부분의 모델 호환성 문제는 Provider를 통하지 않는 직접 호출에서 발생

---

## 4. 프롬프트 파일 분석

### 4.1 파일 목록
```
shared/prompts/
├── __init__.py
├── deepseek_r1.py    # DeepSeek-R1 전용 (DEEPSEEK_R1_SYSTEM_PROMPT, etc.)
├── gpt_oss.py        # GPT-OSS 전용 (GPT_OSS_SYSTEM_PROMPT, etc.)
├── qwen_coder.py     # Qwen Coder 전용
└── generic.py        # 범용 프롬프트
```

### 4.2 프롬프트 호환성 매트릭스

| 프롬프트 | DeepSeek | GPT-OSS | Qwen | 용도 |
|----------|----------|---------|------|------|
| DEEPSEEK_R1_SYSTEM_PROMPT | ✅ | ❌ | ❌ | Supervisor 추론 |
| GPT_OSS_SYSTEM_PROMPT | ❌ | ✅ | ⚠️ | Supervisor 추론 |
| QWEN_CODER_SYSTEM_PROMPT | ❌ | ❌ | ✅ | 코드 생성 |
| GENERIC_CODE_GENERATION_PROMPT | ⚠️ | ⚠️ | ⚠️ | 범용 코드 생성 |

---

## 5. 개선 계획

### 5.1 우선순위 매트릭스

| 우선순위 | 작업 | 난이도 | 영향도 | 예상 작업량 |
|----------|------|--------|--------|-------------|
| 🔴 P0 | RCA Analyzer 모델 호환성 수정 | Medium | Critical | 2-3시간 |
| 🟡 P1 | Architect Node LLM 통합 | High | High | 4-6시간 |
| 🟡 P1 | Reviewer Node 프롬프트 분기 | Low | Medium | 1-2시간 |
| 🟢 P2 | 전체 노드 LLMProvider 표준화 | Medium | High | 8시간+ |

### 5.2 P0: RCA Analyzer 수정

**파일**: `backend/app/agent/langgraph/nodes/rca_analyzer.py`

**변경 사항**:
1. 모델 타입 감지 추가
2. 모델별 프롬프트 분기 구현
3. `<think>` 태그 조건부 생성

**구현 예시**:
```python
from app.core.config import settings

# Import model-specific prompts
from shared.prompts.deepseek_r1 import DEEPSEEK_R1_LOOP_ANALYSIS_PROMPT
from shared.prompts.gpt_oss import GPT_OSS_SUPERVISOR_PROMPT  # New

def _get_rca_prompt(model_type: str, context: dict) -> str:
    if model_type == "deepseek":
        return DEEPSEEK_R1_LOOP_ANALYSIS_PROMPT.format(**context)
    elif model_type == "gpt-oss":
        return f"""## Root Cause Analysis
Analyze the refinement loop issue:
- Max iterations: {context['max_iterations']}
- Current iteration: {context['current_iteration']}

Provide analysis in JSON format..."""
    else:
        return f"""Analyze the following issue..."""

def rca_analyzer_node(state: QualityGateState) -> Dict:
    model_type = settings.get_reasoning_model_type

    # Generate model-appropriate analysis
    if model_type == "deepseek":
        rca_analysis = f"""<think>
1. Pattern Analysis...
</think>

Analysis: ..."""
    else:
        rca_analysis = f"""## Refinement Analysis
**Issues Analyzed:** {len(issues)} problems found
..."""
```

### 5.3 P1: Architect Node LLM 통합

**파일**: `backend/app/agent/langgraph/nodes/architect.py`

**변경 사항**:
1. vLLM 엔드포인트 호출 추가
2. 모델별 프롬프트 분기
3. JSON 응답 파싱
4. 폴백 로직 유지

**구현 패턴** (coder.py 참조):
```python
def _generate_architecture_with_llm(user_request: str, ...) -> Dict:
    endpoint = settings.get_reasoning_endpoint
    model = settings.get_reasoning_model
    model_type = settings.get_reasoning_model_type

    prompt = _get_architect_prompt(model_type, user_request)

    try:
        response = httpx.post(f"{endpoint}/chat/completions", ...)
        return _parse_architecture_response(response.json())
    except:
        return _generate_architecture(...)  # Fallback
```

### 5.4 P2: LLMProvider 표준화

**목표**: 모든 노드에서 직접 HTTP 호출 대신 `LLMProviderFactory` 사용

**장점**:
- 자동 모델 감지 및 프롬프트 적용
- 응답 파싱 표준화
- retry/backoff 로직 재사용
- Think 태그 자동 처리

**대상 노드**:
- reviewer.py (직접 HTTP 호출 부분)
- architect.py (LLM 통합 시)
- rca_analyzer.py (수정 시)

---

## 6. 개발 연속성을 위한 참조 정보

### 6.1 핵심 설정 위치
```
backend/app/core/config.py:
  - get_reasoning_model_type: 추론 모델 타입 반환
  - get_coding_model_type: 코딩 모델 타입 반환
  - get_reasoning_endpoint: 추론 엔드포인트
  - get_coding_endpoint: 코딩 엔드포인트
```

### 6.2 모델 타입 감지 로직
```python
@property
def get_reasoning_model_type(self) -> str:
    model_name = self.get_reasoning_model.lower()
    if "deepseek" in model_name:
        return "deepseek"
    elif "gpt-oss" in model_name or "gptoss" in model_name:
        return "gpt-oss"
    elif "qwen" in model_name:
        return "qwen"
    else:
        return "generic"
```

### 6.3 프롬프트 작성 가이드라인

**DeepSeek-R1**:
```
<think>
1. Step-by-step reasoning
2. Multiple approaches
3. Final decision
</think>

[Structured final answer]
```

**GPT-OSS**:
```
## Section Header
Clear structured content without special tags.
JSON output when specified.
```

**Qwen/Generic**:
```
Direct instructions without special formatting.
Clear, concise prompts.
```

---

## 7. 테스트 체크리스트

### 7.1 변경 후 검증 항목
- [ ] DeepSeek-R1으로 Planning 모드 테스트 (`<think>` 태그 정상 출력)
- [ ] GPT-OSS로 Planning 모드 테스트 (`<think>` 태그 미출력 확인)
- [ ] Qwen으로 코드 생성 테스트
- [ ] RCA Analyzer 모델별 출력 확인
- [ ] Reviewer 피드백 형식 확인
- [ ] Architect LLM 통합 후 구조 설계 품질 확인

### 7.2 회귀 테스트
- [ ] 기존 워크플로우 정상 동작
- [ ] 에러 핸들링 및 폴백 로직
- [ ] 토큰 사용량 추적

---

## 8. 결론

### 8.1 현재 상태 요약
- **양호**: Coder, Refiner, Supervisor - 모델별 프롬프트 분기 구현됨
- **개선 필요**: Reviewer - 부분적 지원
- **긴급 수정**: RCA Analyzer - DeepSeek 하드코딩, `<think>` 태그 강제 출력
- **구현 필요**: Architect - LLM 통합 미완료

### 8.2 권장 작업 순서
1. **즉시**: RCA Analyzer 모델 호환성 수정
2. **단기**: Architect LLM 통합
3. **중기**: LLMProvider 표준화

### 8.3 참고 문서
- `shared/llm/base.py` - LLM Provider 인터페이스
- `shared/prompts/*.py` - 모델별 프롬프트 템플릿
- `backend/core/supervisor.py` - 모델 감지 패턴 참조

---

*이 문서는 다른 세션에서 프로젝트를 이어갈 수 있도록 상세히 기록되었습니다.*

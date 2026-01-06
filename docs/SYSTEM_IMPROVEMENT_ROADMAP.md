# TestCodeAgent 시스템 개선 로드맵

**작성일**: 2026-01-06
**버전**: 1.0
**관련 문서**: [AGENT_COMPATIBILITY_AUDIT.md](./AGENT_COMPATIBILITY_AUDIT.md)

---

## 1. 사용자 관점 분석 (Developer Experience)

개발자로서 이 시스템을 사용한다면 다음과 같은 개선점이 필요합니다:

### 1.1 현재 Pain Points

| 문제 | 영향 | 심각도 |
|------|------|--------|
| 모델 전환 시 `<think>` 태그 노출 | UI에 불필요한 텍스트 표시 | High |
| 대화 컨텍스트 단절 | 연속 개발 시 이전 맥락 손실 | High |
| 계획서 파일 저장 부재 | 개발 계획 추적 어려움 | Medium |
| 아키텍트 노드 LLM 미통합 | 프로젝트 구조 설계 품질 저하 | Medium |
| 파일 읽기 API 부재 | 기존 파일 참조 불가 | Medium |

### 1.2 사용자 시나리오별 개선

#### 시나리오 1: "새 프로젝트 시작"
```
현재: 키워드 기반 템플릿만 제공
개선: LLM 기반 맞춤형 아키텍처 설계
```

#### 시나리오 2: "연속 개발 세션"
```
현재: 대화 컨텍스트 손실
개선: ✅ 완료 - conversation_history 파라미터 추가
```

#### 시나리오 3: "개발 계획 저장"
```
현재: 계획이 채팅 히스토리에만 존재
개선: ✅ 완료 - plan_YYYYMMDD_HHMMSS.md 자동 저장
```

---

## 2. 시스템 아키텍처 개선 제안

### 2.1 현재 아키텍처 문제점

```
                    ┌─────────────────┐
                    │   Frontend      │
                    │ (React/TS)      │
                    └────────┬────────┘
                             │
                    ┌────────▼────────┐
                    │   API Routes    │
                    │ (FastAPI)       │
                    └────────┬────────┘
                             │
         ┌───────────────────┼───────────────────┐
         │                   │                   │
    ┌────▼────┐        ┌─────▼─────┐       ┌─────▼─────┐
    │Supervisor│        │Coder Node │       │ Reviewer  │
    │(GPT-OSS) │        │(Qwen)     │       │ Node      │
    └────┬────┘        └─────┬─────┘       └─────┬─────┘
         │                   │                   │
         │    ❌ 직접 HTTP   │    ✅ Provider    │  ⚠️ 혼합
         │                   │                   │
    ┌────▼────┐        ┌─────▼─────┐       ┌─────▼─────┐
    │  vLLM   │        │LLMProvider │       │직접 호출/ │
    │Endpoint │        │(어댑터)    │       │Provider   │
    └─────────┘        └───────────┘       └───────────┘
```

### 2.2 권장 아키텍처

```
                    ┌─────────────────┐
                    │   Frontend      │
                    │ (React/TS)      │
                    └────────┬────────┘
                             │
                    ┌────────▼────────┐
                    │   API Routes    │
                    │ (FastAPI)       │
                    └────────┬────────┘
                             │
         ┌───────────────────┼───────────────────┐
         │                   │                   │
    ┌────▼────┐        ┌─────▼─────┐       ┌─────▼─────┐
    │Supervisor│        │Coder Node │       │ Reviewer  │
    │          │        │           │       │ Node      │
    └────┬────┘        └─────┬─────┘       └─────┬─────┘
         │                   │                   │
         │    ✅ Provider    │    ✅ Provider    │  ✅ Provider
         │                   │                   │
    ┌────▼───────────────────▼───────────────────▼────┐
    │                 LLMProviderFactory               │
    │  ┌──────────┐ ┌──────────┐ ┌──────────────────┐ │
    │  │DeepSeek  │ │GPT-OSS   │ │ Qwen/Generic     │ │
    │  │Adapter   │ │Adapter   │ │ Adapter          │ │
    │  └────┬─────┘ └────┬─────┘ └────────┬─────────┘ │
    └───────┼────────────┼────────────────┼───────────┘
            │            │                │
    ┌───────▼────────────▼────────────────▼───────────┐
    │                 vLLM Endpoints                   │
    │  (자동 모델 감지, 프롬프트 변환, 응답 정규화)      │
    └─────────────────────────────────────────────────┘
```

---

## 3. 기능 개선 로드맵

### Phase 1: 긴급 수정 (1-2일)

#### 3.1.1 RCA Analyzer 모델 호환성 (P0)
```
파일: backend/app/agent/langgraph/nodes/rca_analyzer.py
작업:
  1. settings.get_reasoning_model_type 사용하여 모델 감지
  2. 모델별 프롬프트 분기 구현
  3. <think> 태그 조건부 생성
테스트:
  - DeepSeek-R1: <think> 태그 포함 출력
  - GPT-OSS: <think> 태그 없이 구조화된 분석
  - Qwen: 일반 텍스트 분석
```

#### 3.1.2 응답 정규화 레이어 추가
```
파일: backend/app/agent/langgraph/utils/response_normalizer.py (신규)
기능:
  - strip_think_tags(text, model_type)
  - extract_json_safely(text)
  - normalize_response(text, model_type, task_type)
```

### Phase 2: 핵심 개선 (3-5일)

#### 3.2.1 Architect Node LLM 통합 (P1)
```
파일: backend/app/agent/langgraph/nodes/architect.py
작업:
  1. LLMProviderFactory 사용 구현
  2. 모델별 아키텍처 설계 프롬프트
  3. JSON 응답 파싱 및 검증
  4. 폴백 로직 유지
예상 효과: 프로젝트 구조 설계 품질 50%+ 향상
```

#### 3.2.2 Reviewer Node 프롬프트 표준화 (P1)
```
파일: backend/app/agent/langgraph/nodes/reviewer.py
작업:
  1. _get_review_prompt() 함수 추가
  2. 직접 HTTP 호출 부분에 모델별 프롬프트 적용
  3. LLMProvider 우선 사용으로 변경
```

### Phase 3: 사용성 개선 (1주+)

#### 3.3.1 컨텍스트 관리 강화
```
기능:
  - 자동 대화 요약 (긴 대화 압축)
  - 프로젝트 컨텍스트 자동 로드 (.ai_context.json)
  - 세션 간 컨텍스트 연속성
```

#### 3.3.2 워크플로우 시각화
```
기능:
  - 현재 실행 중인 노드 표시
  - 에이전트 간 데이터 흐름 시각화
  - 품질 게이트 결과 대시보드
```

#### 3.3.3 개발 계획 관리
```
기능:
  - 계획서 템플릿 커스터마이징
  - 계획서 기반 자동 태스크 생성
  - 진행률 추적
```

---

## 4. 코드 품질 개선

### 4.1 현재 코드 스타일 이슈

```python
# 문제: 직접 HTTP 호출이 여러 노드에 중복
# coder.py, reviewer.py, refiner.py에 유사한 패턴

with httpx.Client(timeout=120) as client:
    response = client.post(
        f"{endpoint}/chat/completions",
        json={...}
    )
```

### 4.2 권장 리팩토링

```python
# 해결: LLMProviderFactory 사용으로 통일
from shared.llm import LLMProviderFactory, TaskType

provider = LLMProviderFactory.create(
    model_type=settings.get_reasoning_model_type,
    endpoint=endpoint,
    model=model
)
response = provider.generate_sync(prompt, TaskType.REVIEW)
```

### 4.3 타입 힌트 개선

```python
# 현재: Dict 반환 타입이 불명확
def architect_node(state: QualityGateState) -> Dict:
    ...

# 개선: TypedDict 사용
class ArchitectNodeOutput(TypedDict):
    current_node: str
    architecture_design: Dict[str, Any]
    files_to_create: List[FileSpec]
    ...
```

---

## 5. 테스트 전략

### 5.1 단위 테스트 추가 필요

```python
# tests/test_model_compatibility.py

class TestModelCompatibility:
    def test_deepseek_think_tags(self):
        """DeepSeek 응답에 <think> 태그가 정상 처리되는지"""

    def test_gpt_oss_no_think_tags(self):
        """GPT-OSS 응답에 <think> 태그가 없는지"""

    def test_qwen_generic_response(self):
        """Qwen 응답이 정상 파싱되는지"""

    def test_json_extraction_robustness(self):
        """다양한 형식의 JSON 응답 추출"""
```

### 5.2 통합 테스트

```python
# tests/integration/test_workflow.py

class TestWorkflowModelSwitching:
    async def test_full_workflow_deepseek(self):
        """DeepSeek 모델로 전체 워크플로우 실행"""

    async def test_full_workflow_gpt_oss(self):
        """GPT-OSS 모델로 전체 워크플로우 실행"""

    async def test_model_switch_mid_workflow(self):
        """워크플로우 중 모델 변경 시 호환성"""
```

---

## 6. 모니터링 및 관찰성

### 6.1 로깅 개선

```python
# 현재: 기본 로깅
logger.info("Starting code generation...")

# 개선: 구조화된 로깅
logger.info(
    "llm_request_started",
    extra={
        "model_type": model_type,
        "task_type": task_type.value,
        "prompt_tokens": estimated_tokens,
        "node": "coder",
    }
)
```

### 6.2 메트릭 수집

```yaml
# 수집할 메트릭
- llm_request_duration_seconds
- llm_request_tokens_total (prompt/completion)
- workflow_node_duration_seconds
- quality_gate_pass_rate
- refinement_iterations_count
```

---

## 7. 문서화 개선

### 7.1 API 문서화

```
docs/
├── api/
│   ├── langgraph_routes.md      # API 엔드포인트 문서
│   ├── workflow_interface.md     # 프론트엔드 인터페이스
│   └── websocket_events.md       # SSE/WebSocket 이벤트
├── architecture/
│   ├── system_overview.md        # 시스템 아키텍처
│   ├── agent_nodes.md            # 에이전트 노드 설명
│   └── llm_providers.md          # LLM 제공자 구조
└── guides/
    ├── adding_new_model.md       # 새 모델 추가 가이드
    ├── prompt_engineering.md     # 프롬프트 작성 가이드
    └── debugging_workflows.md    # 워크플로우 디버깅
```

---

## 8. 향후 기능 제안

### 8.1 단기 (1개월)
- [ ] 멀티파일 편집 지원 (여러 파일 동시 수정)
- [ ] Git 통합 (자동 커밋, 브랜치 관리)
- [ ] 코드 실행 샌드박스

### 8.2 중기 (3개월)
- [ ] 에이전트 플러그인 시스템
- [ ] 사용자 정의 워크플로우 템플릿
- [ ] 팀 협업 기능 (공유 세션)

### 8.3 장기 (6개월+)
- [ ] 자체 학습 (사용자 피드백 기반)
- [ ] 프로젝트 간 지식 전이
- [ ] 자동 문서 생성

---

## 9. 결론

### 9.1 즉시 실행 항목
1. ✅ GPT-OSS 프롬프트 분리 (Supervisor) - 완료
2. ✅ 대화 컨텍스트 연속성 - 완료
3. ✅ 계획서 파일 저장 - 완료
4. 🔄 RCA Analyzer 모델 호환성 - 대기
5. 🔄 Architect LLM 통합 - 대기

### 9.2 이 문서 사용법
1. 새 세션 시작 시 이 문서와 `AGENT_COMPATIBILITY_AUDIT.md` 참조
2. 개선 작업 시 해당 섹션의 코드 예시 활용
3. 완료된 항목은 체크박스 업데이트

### 9.3 연락처
- 프로젝트 저장소: TestCodeAgent
- 관련 파일: `docs/AGENT_COMPATIBILITY_AUDIT.md`

---

*이 문서는 시스템 개선 로드맵을 제공하며, 다른 세션에서 프로젝트를 이어갈 때 참조용으로 사용됩니다.*

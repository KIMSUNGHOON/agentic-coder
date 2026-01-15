# 버그 수정 로그 (Bug Fix Log)

## Issue #4: Comprehensive Workflow Termination Fix (2026-01-15)

### 문제 (Problem)
**유저 피드백**:
- recursion_limit을 1000으로 설정해도 여전히 동일한 에러 발생
- 단순히 "hello"라고 입력했을 뿐인데 recursion limit 에러 발생

**에러 메시지**:
```
System: Error: Recursion limit of 1000 reached without hitting a stop condition.
```

### 원인 (Root Cause)
1. **Config 미적용**: BaseWorkflow에서 recursion_limit이 하드코딩(100)되어 config 값이 무시됨
2. **Workflow 종료 로직 부재**: "hello" 같은 간단한 입력도 복잡한 workflow를 trigger하여 LLM이 "COMPLETE" 액션을 반환해야만 종료됨
3. **LLM 서버 오류 처리 미흡**: LLM 호출 실패 시 무한 루프 발생
4. **JSON 파싱 실패 처리 미흡**: LLM 응답을 JSON으로 파싱 실패 시 계속 재시도

### 해결 방법 (Solution)

#### 1. GeneralWorkflow - Greeting 감지 및 즉시 완료
**파일**: `workflows/general_workflow.py:46-55`

```python
# Handle simple greetings and conversational inputs
greeting_keywords = ['hello', 'hi', 'hey', 'greetings', '안녕', '하이']
if any(keyword in task_lower for keyword in greeting_keywords) and len(task_lower) < 20:
    logger.info("👋 Detected simple greeting, completing immediately")
    state["task_status"] = TaskStatus.COMPLETED.value
    state["task_result"] = f"Hello! I'm Agentic 2.0. How can I help you today?"
    state["should_continue"] = False
    return state
```

#### 2. Conversational Task Type 추가
**파일**: `workflows/general_workflow.py:70`
- Planning prompt에 "conversational" task type 추가
- LLM이 대화형 입력을 인식하고 즉시 완료 가능

#### 3. JSON Parse 실패 제한
**파일**: `workflows/general_workflow.py:208-214`

```python
except json.JSONDecodeError as e:
    logger.warning(f"Failed to parse action: {e}")
    # If JSON parsing fails multiple times, give up
    if state["iteration"] >= 2:
        logger.error("Multiple JSON parse failures, completing task")
        state["task_status"] = TaskStatus.FAILED.value
        state["task_error"] = "Unable to parse LLM response as JSON"
        state["should_continue"] = False
        return state
```

#### 4. LLM 실패 시 Graceful Degradation
**파일**: `workflows/general_workflow.py:120-122`

```python
except Exception as e:
    logger.error(f"Planning error: {e}")
    # If planning fails (e.g., LLM server not available), fail gracefully
    state["task_status"] = TaskStatus.FAILED.value
    state["task_error"] = f"Planning failed: {e}. Is the LLM server running?"
    state["should_continue"] = False
```

#### 5. Config Recursion Limit 적용
**파일**: `workflows/base_workflow.py:313-318`

```python
# Determine recursion_limit from state or use default
recursion_limit = state.get("recursion_limit", 100)
logger.info(f"🔧 Using recursion_limit: {recursion_limit}, max_iterations: {state.get('max_iterations', 10)}")

final_state = await self.graph.ainvoke(
    state,
    config={"recursion_limit": recursion_limit}
)
```

#### 6. End-to-End Config Propagation
- `config/config.yaml` → `Config.load()`
- → `BackendBridge.initialize()`
- → `WorkflowOrchestrator.__init__()`
- → `create_initial_state(recursion_limit=...)`
- → `BaseWorkflow.run()` reads from state

### 테스트 (Testing)
```bash
cd agentic-ai && python -m pytest tests/ -v
✅ 35 passed, 1 skipped
```

### 영향 범위 (Impact)
- ✅ "hello", "hi" 등 간단한 인사는 즉시 완료
- ✅ Config의 recursion_limit 값이 올바르게 적용됨
- ✅ LLM 서버 장애 시 무한 루프 방지
- ✅ JSON 파싱 실패 시 2회 재시도 후 종료
- ✅ 모든 에러 경로에서 task_status와 should_continue 적절히 설정

### 상태 (Status)
✅ **Fixed and Verified** (2026-01-15)

**Commit**: c627f75

---

## Issue #3: LangGraph Recursion Limit Exceeded (2026-01-15)

### 문제 (Problem)
**에러 메시지**:
```
System: Error: Recursion limit of 25 reached without hitting a stop condition.
You can increase the limit by setting the 'recursion_limit' config key.
```

### 원인 (Root Cause)
LangGraph의 기본 `recursion_limit`이 25로 설정되어 있어, 복잡한 workflow 실행 시 재귀 제한을 초과함.

**상세 분석**:
- LangGraph workflow는 각 노드(plan → execute → reflect)를 거칠 때마다 재귀 호출 카운트 증가
- `max_iterations`이 3으로 설정되어 있어도, 각 iteration마다 여러 노드를 거치면서 재귀 깊이 누적
- 특히 sub-agent를 사용하거나 복잡한 작업의 경우 더 많은 재귀 호출 필요
- 예시: 3 iterations × 3 nodes × 추가 조건부 로직 = 25+ recursion calls

### 해결 방법 (Solution)

#### 1. BaseWorkflow.run() 수정
**파일**: `workflows/base_workflow.py:316-319`

**변경 전**:
```python
with monitor.measure("workflow_execution"):
    final_state = await self.graph.ainvoke(state)
```

**변경 후**:
```python
with monitor.measure("workflow_execution"):
    final_state = await self.graph.ainvoke(
        state,
        config={"recursion_limit": 100}  # Increase limit for complex workflows
    )
```

#### 2. config.yaml에 설정 추가
**파일**: `config/config.yaml:44`

```yaml
workflows:
  max_iterations: 3
  timeout_seconds: 600
  recursion_limit: 100  # LangGraph recursion limit (default: 25)
```

### 테스트 (Testing)
```bash
# 통합 테스트 통과
python3 test_cli_integration.py
✅ Passed: 2/2
```

### 영향 범위 (Impact)
- ✅ 모든 workflow (Coding, Research, Data, General)에 적용
- ✅ Sub-agent 실행 시 recursion limit 문제 해결
- ✅ 복잡한 작업도 정상 실행 가능

### 권장 설정 (Recommendations)
- **간단한 작업**: recursion_limit: 50
- **일반 작업**: recursion_limit: 100 (현재 기본값)
- **복잡한 작업**: recursion_limit: 150-200
- **Sub-agent 사용 시**: recursion_limit: 200+

### 참고 (References)
- [LangGraph Error Docs](http://docs.langchain.com/oss/python/langgraph/errors/GRAPH_RECURSION_LIMIT)
- LangGraph config options: `{"recursion_limit": int}`

### 상태 (Status)
✅ **Fixed and Verified** (2026-01-15)

---

## 이전 버그 수정 내역

### Issue #1: Missing to_dict() Method (2026-01-15)
**Status**: ✅ Fixed
**File**: `core/router.py`
**Details**: Added `to_dict()` method to `IntentClassification` dataclass

### Issue #2: YAML Config Parsing Error (2026-01-15)
**Status**: ✅ Fixed
**File**: `config/config.yaml`
**Details**: Quoted fork bomb pattern to prevent YAML parsing as dictionary

---

**최종 업데이트**: 2026-01-15
**총 버그 수정**: 4개
**현재 알려진 이슈**: 0개

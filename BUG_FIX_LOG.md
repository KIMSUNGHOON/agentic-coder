# 버그 수정 로그 (Bug Fix Log)

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
**총 버그 수정**: 3개
**현재 알려진 이슈**: 0개

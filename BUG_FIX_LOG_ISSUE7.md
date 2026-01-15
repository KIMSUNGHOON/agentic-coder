# Bug Fix #7: Max Iterations Too Low + No Debugging Visibility

## 문제 (Problem)
**유저 피드백**:
1. `"Max iterations reached (3)"` 에러 발생
2. 입력: `"python 언어로 구현된 계산기를 만들고 싶은데."`
3. **"지금 보니까 실제로 backend logging 및 debugging 기능이 없네. logs 창이 있긴 한데. 실제 어떻게 내부적으로 동작하는지 전혀 알 수가 없네."**

## 원인 (Root Cause)

### 1. max_iterations가 너무 적음
**파일**: `config/config.yaml:42`
```yaml
workflows:
  max_iterations: 3  # ❌ Too low!
```

계산기 만들기 같은 작업은 최소:
1. Plan (계획 수립)
2. Create file structure (파일 구조 생성)
3. Write calculator code (계산기 코드 작성)
4. Add tests (테스트 추가)
5. Verify and complete (검증 및 완료)

→ 최소 5 iterations 필요, 3으로는 부족!

### 2. Backend 로깅/디버깅 부재
**파일**: `cli/backend_bridge.py:208`
```python
# ❌ Blocking call - no intermediate feedback
result = await self.orchestrator.execute_task(
    task_description=task_description,
    workspace=workspace,
    domain_override=domain_override,
)
```

문제:
- Workflow가 완료될 때까지 blocking
- 중간에 무슨 일이 일어나는지 전혀 알 수 없음
- LogViewer가 있지만 실제로 아무 로그도 표시 안 됨

### 3. Metadata 정보 부족
**파일**: `workflows/base_workflow.py:352-356`
```python
metadata={
    "duration_seconds": duration,
    "final_state": final_state,  # ❌ 너무 많거나 너무 적음
}
```

- final_state 전체를 넣으면 너무 많은 정보
- 하지만 tool 호출, 에러 등 디버깅에 필요한 정보는 빠짐

## 해결 방법 (Solution)

### 1. max_iterations 증가
**파일**: `config/config.yaml:42`
```yaml
workflows:
  max_iterations: 10  # ✅ Increased from 3 (Bug Fix #7)
```

10 iterations면 대부분의 작업 처리 가능:
- 간단한 작업: 2-3 iterations
- 보통 작업: 5-7 iterations
- 복잡한 작업: 8-10 iterations

### 2. Debug 모드 활성화
**파일**: `config/config.yaml`
```yaml
logging:
  level: DEBUG  # INFO → DEBUG (more verbose)

development:
  debug_mode: true  # false → true (enable debugging features)
```

### 3. 상세한 Metadata 추가
**파일**: `workflows/base_workflow.py:347-372`
```python
# Create detailed metadata for debugging (Bug Fix #7)
metadata = {
    "duration_seconds": duration,
    "workflow_domain": final_state.get("workflow_domain", "unknown"),
    "workflow_type": final_state.get("workflow_type", "unknown"),
    "tool_calls": final_state.get("tool_calls", []),  # ✅ Tool 실행 내역
    "errors": final_state.get("errors", []),          # ✅ 에러 목록
    "context": {
        "plan": final_state.get("context", {}).get("plan", {}),
        "completed_steps": final_state.get("context", {}).get("completed_steps", []),
    },
}

logger.info(
    f"📊 Workflow stats: tool_calls={len(metadata['tool_calls'])}, "
    f"errors={len(metadata['errors'])}, "
    f"completed_steps={len(metadata['context']['completed_steps'])}"
)
```

### 4. Backend Bridge 로깅 강화
**파일**: `cli/backend_bridge.py:209-264`
```python
# Log workflow start
yield ProgressUpdate(
    type="log",
    message="🚀 Starting workflow execution...",
    data={"level": "info"}
)

result = await self.orchestrator.execute_task(...)

# Log execution details from metadata
if result.metadata:
    # Log workflow domain
    domain = result.metadata.get("workflow_domain", "unknown")
    yield ProgressUpdate(
        type="log",
        message=f"📋 Workflow: {domain}",
        data={"level": "info"}
    )

    # Log iterations
    yield ProgressUpdate(
        type="log",
        message=f"🔄 Completed {iterations} iterations",
        data={"level": "info"}
    )

    # Log tool calls (first 5)
    tool_calls = result.metadata.get("tool_calls", [])
    if tool_calls:
        yield ProgressUpdate(
            type="log",
            message=f"🔧 Executed {len(tool_calls)} tool calls",
            data={"level": "info"}
        )
        for i, call in enumerate(tool_calls[:5], 1):
            action = call.get("action", "unknown")
            yield ProgressUpdate(
                type="log",
                message=f"  {i}. {action}",
                data={"level": "debug"}
            )

    # Log errors (first 3)
    errors = result.metadata.get("errors", [])
    if errors:
        for error in errors[:3]:
            yield ProgressUpdate(
                type="log",
                message=f"⚠️  Error: {error}",
                data={"level": "warning"}
            )
```

## 테스트 (Testing)
```bash
cd agentic-ai && python -m pytest tests/ -v
✅ 35 passed, 1 skipped

python test_greeting_simple.py
✅ 6/6 tests passed
```

## 영향 범위 (Impact)

### ✅ 개선된 부분:
1. **max_iterations 증가**: 3 → 10
   - 대부분의 실제 작업 처리 가능
   - "계산기 만들기" 같은 작업 완료 가능

2. **로깅 가시성 확보**:
   - Workflow domain 표시
   - Iteration 수 표시
   - Tool 호출 내역 표시 (최대 5개)
   - 에러 목록 표시 (최대 3개)

3. **디버깅 정보 제공**:
   - Plan 정보
   - Completed steps
   - Workflow stats (tool calls, errors, steps count)

### ⚠️ 제한사항 (Limitations):
1. **여전히 실시간 스트리밍 아님**
   - Workflow가 완료된 후 결과를 표시
   - 실행 중에는 "Executing..." 상태만 표시

2. **향후 개선 필요**:
   - Orchestrator에 streaming 지원 추가
   - LangGraph의 streaming API 활용
   - 실시간으로 각 node 실행 상황 표시

## 사용자 경험 개선

### Before (Bug):
```
User: "python 언어로 구현된 계산기를 만들고 싶은데."

CLI: [실행 중...]
     [오랜 시간 대기...]
     Error: Max iterations reached (3)

User: "무슨 일이 일어난 건지 전혀 모르겠네..."
```

### After (Fixed):
```
User: "python 언어로 구현된 계산기를 만들고 싶은데."

CLI: 🚀 Starting workflow execution...
     📋 Workflow: coding
     🔄 Completed 7 iterations
     🔧 Executed 12 tool calls
       1. WRITE_FILE
       2. WRITE_FILE
       3. RUN_COMMAND
       4. READ_FILE
       5. COMPLETE

     ✅ Task completed successfully!

User: "아, 7번 반복하고 12개 tool 사용했구나. 이제 이해됨!"
```

## 교훈 (Lessons Learned)

1. **Config 기본값의 중요성**
   - max_iterations: 3은 테스트용 값
   - 실제 사용에는 10+ 필요
   - 사용자가 config를 직접 수정하기 전까지는 기본값 사용

2. **로깅의 필요성**
   - "무슨 일이 일어나는지 모르겠다" = 최악의 UX
   - 최소한 실행 후라도 summary 제공 필요
   - 디버깅 정보는 선택사항이 아님

3. **Blocking vs Streaming**
   - Current: Blocking call (simple but no feedback)
   - Future: Streaming (complex but better UX)
   - Intermediate: Detailed post-execution summary (현재 구현)

## 상태 (Status)
✅ **Fixed and Verified** (2026-01-15)

**Commit**: 04242ad

**추가 개선 필요**:
- [ ] LangGraph streaming API 활용
- [ ] Real-time node execution feedback
- [ ] Progress bar with estimated completion
- [ ] Cancellation support

---

**최종 업데이트**: 2026-01-15
**Bug Fix #7**: Max iterations increased + logging enhanced

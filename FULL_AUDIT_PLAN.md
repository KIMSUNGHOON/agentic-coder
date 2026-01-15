# Agentic 2.0 전수 조사 및 근본적 개선 계획

## 🔴 현재 문제 인식

### 발견된 치명적 버그들
1. ✅ **프롬프트-코드 불일치**: action 이름 대소문자 (complete vs COMPLETE)
2. ✅ **Parameter 접근 오류**: `action.get("file_path")` instead of `params.get("file_path")`
3. ✅ **JSON 파싱 실패 silent fail**: 에러 발생 시 tracking 안 됨
4. ✅ **무한 반복**: max_iterations(50) 체크가 smart logic보다 먼저 실행
5. ❓ **알려지지 않은 버그들**: 전수 조사 필요

### UI/UX 근본적 부족
- ❌ Claude Code CLI 수준이 아님
- ❌ Real-time streaming 부족
- ❌ File diffs 표시 없음
- ❌ Interactive confirmation 없음
- ❌ Tool execution 상세 표시 부족

---

## 📊 Phase 1: 전수 조사 (Full Audit)

### 1.1 Prompt 검증
**목표**: 모든 프롬프트가 코드와 일치하는지 확인

**파일**:
- [ ] `core/prompts.py` - CodingPrompts, ResearchPrompts, DataPrompts, AgentPrompts
- [ ] 각 workflow의 프롬프트 사용 방식

**검증 항목**:
- [ ] Action 이름 일치 (대소문자 포함)
- [ ] Parameter 구조 일치 (`{"action": "X", "parameters": {...}}`)
- [ ] 필수/선택 파라미터 명시
- [ ] Few-shot examples 정확성
- [ ] COMPLETE action 사용 시점 명확성

**방법**:
```python
# 자동 검증 스크립트 작성
# tests/audit/test_prompt_code_consistency.py
```

### 1.2 Workflow 검증
**목표**: 모든 workflow가 올바르게 작동하는지 확인

**파일**:
- [ ] `workflows/coding_workflow.py`
- [ ] `workflows/general_workflow.py`
- [ ] `workflows/research_workflow.py`
- [ ] `workflows/data_workflow.py`
- [ ] `workflows/base_workflow.py`

**검증 항목**:
- [ ] `_execute_action` parameter 추출 방식 통일
- [ ] Tool 실행 성공/실패 로깅
- [ ] State 업데이트 일관성
- [ ] Error handling 완전성
- [ ] Iteration limits 로직 정확성
- [ ] Early completion 조건 검증

**테스트**:
- [ ] 각 workflow마다 end-to-end 테스트 작성
- [ ] "Python 계산기" (simple coding)
- [ ] "Flask API 만들기" (moderate coding)
- [ ] "시스템 리팩토링" (complex coding)
- [ ] "주식 시장 조사" (research)
- [ ] "데이터 분석" (data)

### 1.3 Tool 검증
**목표**: 모든 tool이 올바르게 작동하는지 확인

**파일**:
- [ ] `core/tools/filesystem.py`
- [ ] `core/tools/search.py`
- [ ] `core/tools/process.py`
- [ ] `core/tools/git.py`

**검증 항목**:
- [ ] 모든 tool이 실제로 작동하는가
- [ ] Error 발생 시 명확한 메시지
- [ ] Safety checks 적용
- [ ] Return value 구조 일관성 (`{"success": bool, "output": ..., "error": ...}`)

**테스트**:
```python
# tests/audit/test_tool_execution.py
async def test_write_file_real():
    """실제 파일 쓰기 테스트"""
    result = await fs_tools.write_file("/tmp/test.py", "print('hello')")
    assert result.success == True
    assert os.path.exists("/tmp/test.py")
    with open("/tmp/test.py") as f:
        assert f.read() == "print('hello')"
```

### 1.4 State Management 검증
**목표**: State가 일관되게 관리되는지 확인

**파일**:
- [ ] `core/state.py`

**검증 항목**:
- [ ] AgenticState TypedDict 필드 정확성
- [ ] 모든 workflow에서 state 사용 일관성
- [ ] Context 저장/조회 안전성
- [ ] Tool calls tracking 완전성

### 1.5 LLM Client 검증
**목표**: LLM 호출이 안정적인지 확인

**파일**:
- [ ] `core/llm_client.py`

**검증 항목**:
- [ ] Failover 작동 확인
- [ ] Timeout handling
- [ ] Error messages 명확성
- [ ] Retry logic
- [ ] Streaming 지원 확인

### 1.6 Backend Bridge 검증
**목표**: UI-Backend 통신이 올바른지 확인

**파일**:
- [ ] `cli/backend_bridge.py`

**검증 항목**:
- [ ] 모든 event type 전달 확인
- [ ] Event data 구조 일관성
- [ ] Streaming 누락 없음
- [ ] Error propagation

---

## 🎨 Phase 2: Claude Code CLI 수준 UI/UX 설계

### 2.1 Claude Code CLI 분석
**참고 자료**:
- Claude Code CLI GitHub: https://github.com/anthropics/claude-code
- Cursor IDE
- GitHub Copilot CLI
- Aider

**핵심 기능**:
1. **Real-time Streaming**
   - LLM 응답을 token-by-token 표시
   - Tool execution 진행 상황 실시간 표시

2. **File Operations Display**
   - File diffs (before/after)
   - Syntax highlighting
   - Line numbers
   - Clear file paths

3. **Interactive Confirmations**
   - "Apply this change? (y/n)"
   - "Run this command? (y/n)"
   - Safety prompts

4. **Progress Indicators**
   - Spinner for long operations
   - Progress bars for multi-step tasks
   - ETA estimation

5. **Beautiful Formatting**
   - Colors and emoji
   - Panels and borders
   - Hierarchical display
   - Clear visual hierarchy

### 2.2 현재 Agentic 2.0 UI 문제점

**현재 구조**:
```
┌─ Header ─────────────────────────────────┐
│ Agentic AI Coding Assistant              │
└──────────────────────────────────────────┘
┌─ Chat ────────┬─ CoT ───────┬─ Logs ────┐
│ User: ...     │ Thinking... │ INFO ...  │
│ Asst: ...     │             │           │
└───────────────┴─────────────┴───────────┘
┌─ Input ───────────────────────────────────┐
│ > _                                       │
└──────────────────────────────────────────┘
┌─ Status ──────────────────────────────────┐
│ Ready | Healthy | Session: xxx | Local   │
└──────────────────────────────────────────┘
```

**문제점**:
- ❌ Chat에 tool execution 상세 정보 부족
- ❌ File contents가 preview만 표시
- ❌ Diff 표시 없음
- ❌ Interactive confirmation 없음
- ❌ Progress indicator가 단순함
- ❌ CoT 창이 비어있음

### 2.3 개선된 UI/UX 설계

**Claude Code CLI 스타일 적용**:

```
┌─ Agentic AI v2.0 ────────────────────────────────────────────────┐
│ 🤖 Local GPT-OSS-120B | Session: abc123 | ✅ Healthy             │
└──────────────────────────────────────────────────────────────────┘

You: Python 계산기 만들기

🤔 Planning...
┌─ Plan ────────────────────────────────────────────────────────────┐
│ Task: Python 계산기 만들기                                           │
│ Approach: Create calculator.py with arithmetic functions           │
│ Steps:                                                             │
│   1. Create calculator.py file                                     │
│   2. Implement add, subtract, multiply, divide functions           │
│ Estimated iterations: 2-3                                          │
└────────────────────────────────────────────────────────────────────┘

⚙️  Step 1/2: Creating calculator.py...

📝 Writing file: calculator.py
┌─ calculator.py (NEW) ──────────────────────────────────────────────┐
│  1 | def add(a, b):                                                │
│  2 |     return a + b                                              │
│  3 |                                                               │
│  4 | def subtract(a, b):                                           │
│  5 |     return a - b                                              │
│  6 |                                                               │
│  7 | def multiply(a, b):                                           │
│  8 |     return a * b                                              │
│  9 |                                                               │
│ 10 | def divide(a, b):                                             │
│ 11 |     if b == 0:                                                │
│ 12 |         raise ValueError('Cannot divide by zero')             │
│ 13 |     return a / b                                              │
└────────────────────────────────────────────────────────────────────┘
✅ File created: calculator.py (200 bytes)

⚙️  Step 2/2: Completing task...

✅ Task completed in 2 iterations

┌─ Summary ──────────────────────────────────────────────────────────┐
│ Created calculator.py with 4 arithmetic functions:                 │
│   • add(a, b) - Addition                                           │
│   • subtract(a, b) - Subtraction                                   │
│   • multiply(a, b) - Multiplication                                │
│   • divide(a, b) - Division with zero check                        │
│                                                                    │
│ 📁 Files created: 1                                                │
│ 🔧 Tools executed: 1 (WRITE_FILE)                                  │
│ ⏱️  Duration: 3.2s                                                 │
└────────────────────────────────────────────────────────────────────┘
```

**핵심 개선사항**:
1. **단계별 명확한 표시** (Planning, Step 1/N, Completing)
2. **파일 내용 전체 표시** (line numbers, syntax highlighting)
3. **파일 크기 표시** (200 bytes)
4. **작업 요약** (Summary box)
5. **통계 표시** (files, tools, duration)

### 2.4 UI 컴포넌트 개선 목록

#### Chat Panel 개선
**파일**: `cli/components/chat_panel.py`

**현재 문제**:
- Message 형식이 단순함
- File content가 preview만 표시
- No line numbers
- No syntax highlighting for Python/JS/etc

**개선 사항**:
```python
# Before
chat.add_status(f"🔧 Tool [1]: WRITE_FILE(calculator.py) ✅")

# After - 상세한 표시
chat.add_tool_execution(
    tool="WRITE_FILE",
    params={"file_path": "calculator.py", "content": "..."},
    success=True,
    display_mode="full"  # or "preview" or "hidden"
)
```

**새 메서드 필요**:
- `add_file_content(file_path, content, display_mode)` - Full file display with line numbers
- `add_file_diff(file_path, old_content, new_content)` - Show before/after diff
- `add_step_header(step_num, total_steps, description)` - Step progress
- `add_plan_summary(plan)` - Display plan in box
- `add_task_summary(stats)` - Display completion summary
- `add_confirmation_prompt(message, default)` - Interactive confirmation

#### Progress Display 개선
**파일**: `cli/components/progress_display.py`

**개선 사항**:
- 현재 step/total steps 표시
- ETA estimation
- Spinner for long operations
- Multi-level progress (overall + current step)

#### CoT Viewer 개선
**파일**: `cli/components/cot_viewer.py`

**현재 문제**:
- CoT가 제대로 표시되지 않음
- LLM reasoning이 안 보임

**개선 사항**:
- LLM의 reasoning 단계별 표시
- Collapsible sections
- Token-by-token streaming

---

## 🚀 Phase 3: 구현 우선순위

### Priority 1: 치명적 버그 수정 (완료)
- ✅ Parameter extraction 수정
- ✅ Prompt-code 불일치 수정
- ✅ JSON parsing error handling

### Priority 2: 전수 조사 실행 (다음 단계)
**순서**:
1. Tool 검증 (가장 critical) - 3시간
   - 모든 tool 실제 작동 확인
   - Integration tests 작성

2. Workflow 검증 - 4시간
   - End-to-end tests 작성
   - 각 workflow 시나리오 테스트

3. Prompt 검증 - 2시간
   - 자동 검증 스크립트
   - Prompt-code consistency check

4. State/LLM/Bridge 검증 - 2시간
   - Unit tests 보강
   - Error scenarios 테스트

**Output**:
- `AUDIT_REPORT.md` - 발견된 모든 버그 목록
- `tests/audit/` - 검증 테스트 suite

### Priority 3: UI/UX 근본적 개선 (이후 단계)
**순서**:
1. Chat Panel 개선 - 6시간
   - File display with line numbers
   - Syntax highlighting
   - Diff display

2. Interactive Confirmations - 3시간
   - Confirmation prompts
   - User input handling

3. Progress Indicators - 2시간
   - Step-by-step display
   - ETA estimation

4. Layout Redesign - 4시간
   - Claude Code CLI 스타일 적용
   - Component 재배치

**Output**:
- 완전히 새로운 UI/UX
- Claude Code CLI 수준의 사용자 경험

---

## 📋 체크리스트

### Phase 1: 전수 조사
- [ ] Tool 검증 완료
- [ ] Workflow 검증 완료
- [ ] Prompt 검증 완료
- [ ] State/LLM/Bridge 검증 완료
- [ ] AUDIT_REPORT.md 작성

### Phase 2: UI/UX 설계
- [ ] Claude Code CLI 분석 완료
- [ ] UI 컴포넌트 개선 설계
- [ ] Interactive 기능 설계
- [ ] Layout 재설계

### Phase 3: 구현
- [ ] Chat Panel 개선
- [ ] Interactive Confirmations
- [ ] Progress Indicators
- [ ] Layout Redesign
- [ ] End-to-end 테스트

---

## 🎯 최종 목표

**"Claude Code CLI와 동등한 수준의 UI/UX와 안정성"**

### 성공 기준:
1. ✅ 모든 tool이 검증되고 작동함
2. ✅ 모든 workflow가 올바르게 작동함
3. ✅ UI가 Claude Code CLI 수준
4. ✅ File operations이 명확하게 표시됨
5. ✅ Interactive confirmation 지원
6. ✅ Real-time streaming
7. ✅ 사용자가 "택도 없다"고 느끼지 않음

### 예상 소요 시간:
- Phase 1 (전수 조사): 11시간
- Phase 2 (UI/UX 설계): 4시간
- Phase 3 (구현): 15시간
- **Total: ~30시간 (4-5일)**

---

## 📝 다음 단계

1. **즉시**: Tool 검증 시작
   ```bash
   cd tests/audit
   pytest test_tool_execution.py -v
   ```

2. **오늘 안**: Workflow 검증 완료

3. **내일**: Prompt 검증 + AUDIT_REPORT.md

4. **그 다음**: UI/UX 개선 시작
# UI/UX 개선 계획 (Improvement Plan)

**작성일**: 2026-01-15
**우선순위**: 🔥 CRITICAL

## 🔍 현재 문제점 분석

### 1. ❌ 항상 "Max iterations reached" 에러 발생

**증상**:
```
Error | Task failed: Max iterations reached
```
- 모든 작업이 50 iterations까지 실행됨
- COMPLETE 액션을 감지하지 못함

**원인 분석**:
```python
# workflows/general_workflow.py:227-230
if action.get("action") == "COMPLETE":
    state["task_status"] = TaskStatus.COMPLETED.value
    state["task_result"] = action.get("summary", "Task completed")
    state["should_continue"] = False  # ✅ 여기서 False로 설정

# workflows/general_workflow.py:332
state["should_continue"] = True  # ❌ reflect_node에서 무조건 True로 덮어씀!
```

**근본 원인**:
- `execute_node`에서 COMPLETE 감지하고 `should_continue=False` 설정
- 하지만 `reflect_node`가 나중에 실행되면서 `should_continue=True`로 덮어씀
- LangGraph 실행 순서: execute → reflect → should_continue 확인
- reflect가 execute의 결과를 무시하고 있음!

### 2. ❌ 매번 "No session" 상태

**증상**:
```
Status Bar: No session
```
- 세션이 생성되지 않음
- 대화 컨텍스트가 유지되지 않음

**원인 분석**:
```python
# cli/app.py:166-167
status = self.query_one("#status-bar", StatusBar)
status.update_status("Ready", "healthy")
# ❌ 세션 ID 설정 코드 없음!

# backend_bridge.py에서 세션을 생성하지만
# UI에 반영하지 않음
```

**근본 원인**:
- Backend에서 세션을 생성하지만 UI에 전달하지 않음
- `status.set_session(session_id)` 호출 누락

### 3. ❌ Chat 윈도우에 실시간 스트리밍 없음

**증상**:
- 프롬프트 입력 후 → 긴 대기 → 최종 결과만 표시
- LLM이 생성하는 토큰이 실시간으로 보이지 않음
- 진행 상황을 전혀 알 수 없음

**현재 동작**:
```python
# cli/app.py:241-246
elif update.type == "result":
    # ❌ 최종 결과만 표시
    if update.data["success"]:
        output = update.data.get("output", "")
        chat.add_message("assistant", str(output))
```

**문제점**:
- `update.type == "status"` → Progress bar에만 표시, Chat에는 없음
- LLM 응답이 완료될 때까지 Chat 영역 업데이트 없음
- 사용자는 "멈춘 것인가?"라고 생각함

**필요한 것**:
```python
# 원하는 동작:
elif update.type == "llm_token":
    # 토큰 단위로 실시간 표시
    chat.append_streaming(update.message)

elif update.type == "node_start":
    # 노드 시작 표시
    chat.add_status("계획 수립 중...")

elif update.type == "action_executing":
    # 액션 실행 표시
    chat.add_status("🔧 Executing: READ_FILE")
```

### 4. ❌ Markdown/코드 렌더링 없음

**증상**:
- Planning 결과가 plain text로만 표시
- 코드 블록이 포맷팅 없이 표시
- TypeScript, Python 등 syntax highlighting 없음

**현재 코드**:
```python
# cli/components/chat_panel.py:63
text.append(content, style="white")  # ❌ 단순 텍스트만
```

**문제점**:
- Rich의 `Markdown` 기능 미사용
- Rich의 `Syntax` 기능 미사용
- 코드와 일반 텍스트 구분 안 됨

**예시**:
```
# 현재 표시:
Assistant: Here is the plan: 1. Read file 2. Analyze code ```typescript const x = 1; ```

# 원하는 표시:
Assistant: Here is the plan:
1. Read file
2. Analyze code

┌─ TypeScript ────┐
│ const x = 1;    │
└─────────────────┘
```

### 5. ❌ 프롬프트 입력 후 피드백 없음

**증상**:
- 메시지 입력 → Enter → ... (아무 반응 없음) → 1분 후 결과
- "처리 중인가? 멈춘 건가?" 알 수 없음

**현재 동작**:
```
1. 사용자 메시지 입력
2. Progress bar만 업데이트 (하단)
3. Chat 영역은 변화 없음 ← 문제!
4. 오랜 시간 후 결과 표시
```

**필요한 동작**:
```
1. 사용자 메시지 입력
2. Chat에 즉시 "Processing..." 표시 ← 추가 필요!
3. 각 단계별로 Chat에 상태 표시:
   - "📋 Planning..."
   - "🤔 Analyzing complexity..."
   - "🔧 Executing tools..."
   - "💭 Reflecting on results..."
4. LLM 응답 실시간 스트리밍
5. 최종 결과 표시
```

---

## ✅ 개선 목록 (Improvement List)

### Priority 1: 🔥 CRITICAL (즉시 수정 필요)

#### 1.1. Fix: reflect_node가 should_continue를 덮어쓰는 문제

**파일**: `agentic-ai/workflows/general_workflow.py`

**문제**:
```python
# Line 332: reflect_node
state["should_continue"] = True  # ❌ 무조건 True
```

**해결**:
```python
# reflect_node 수정
async def reflect_node(self, state: AgenticState) -> AgenticState:
    # Check if ALREADY completed in execute_node
    if state.get("task_status") == TaskStatus.COMPLETED.value:
        logger.info("✅ Task is COMPLETED (from execute_node), stopping")
        state["should_continue"] = False  # ✅ 유지!
        return state

    # ... rest of reflect logic
```

**영향**: Max iterations 문제 해결

#### 1.2. Add: 세션 ID 생성 및 UI 표시

**파일**: `agentic-ai/cli/app.py`

**추가 위치**: `process_message()` 시작 부분

**코드**:
```python
async def process_message(self, message: str) -> None:
    # Generate session ID if not exists
    if not hasattr(self, 'session_id') or not self.session_id:
        import uuid
        self.session_id = str(uuid.uuid4())

        # Update status bar
        status = self.query_one("#status-bar", StatusBar)
        status.set_session(self.session_id)

        logger.info(f"📝 Created session: {self.session_id}")
```

**영향**: "No session" 문제 해결

#### 1.3. Add: Chat에 실시간 진행 상황 표시

**파일**: `agentic-ai/cli/app.py` → `process_message()`

**현재**:
```python
if update.type == "status":
    progress.update_progress(...)  # Progress bar만
    log.add_log(...)               # Log만
```

**개선**:
```python
if update.type == "status":
    progress.update_progress(...)
    log.add_log(...)
    chat.add_status(update.message)  # ✅ Chat에도 표시!

elif update.type == "node_start":
    # 노드 시작 알림
    chat.add_status(f"🔄 {update.message}")

elif update.type == "llm_streaming":
    # LLM 토큰 스트리밍
    chat.append_streaming(update.message)
```

**영향**: 사용자가 진행 상황을 실시간으로 볼 수 있음

### Priority 2: ⭐ HIGH (UX 개선)

#### 2.1. Add: ChatPanel에 Markdown 렌더링

**파일**: `agentic-ai/cli/components/chat_panel.py`

**현재**:
```python
def add_message(self, role: str, content: str) -> None:
    # Plain text만 표시
    text.append(content, style="white")
```

**개선**:
```python
from rich.markdown import Markdown
from rich.syntax import Syntax

def add_message(self, role: str, content: str, format: str = "text") -> None:
    """Add a message with optional formatting

    Args:
        role: user, assistant, system
        content: Message content
        format: "text", "markdown", "code"
    """
    if format == "markdown":
        # Render as Markdown
        md = Markdown(content)
        self.write(Panel(md, border_style="green", ...))

    elif format == "code":
        # Detect language and syntax highlight
        language = self._detect_language(content)
        syntax = Syntax(content, language, theme="monokai")
        self.write(Panel(syntax, border_style="blue", ...))

    else:
        # Plain text (current behavior)
        ...
```

**영향**: Planning, 코드 등이 보기 좋게 표시됨

#### 2.2. Add: 실시간 스트리밍 메시지

**파일**: `agentic-ai/cli/components/chat_panel.py`

**추가 메서드**:
```python
def add_streaming_message(self, role: str, content: str) -> str:
    """Start a streaming message (returns message_id)"""
    message_id = f"msg_{self.message_count}"
    # Create panel with initial content
    # Return ID for updating
    return message_id

def update_streaming_message(self, message_id: str, content: str) -> None:
    """Update streaming message with new content"""
    # Update the panel with accumulated content
    pass

def finalize_streaming_message(self, message_id: str) -> None:
    """Finalize streaming message"""
    # Mark as complete, apply final formatting
    pass
```

**사용 예시**:
```python
# Start streaming
msg_id = chat.add_streaming_message("assistant", "")

# Update as tokens arrive
async for token in llm_stream():
    chat.update_streaming_message(msg_id, accumulated_text)

# Finalize
chat.finalize_streaming_message(msg_id)
```

**영향**: LLM 응답이 실시간으로 보임

#### 2.3. Add: 상태 메시지 표시 (임시 메시지)

**파일**: `agentic-ai/cli/components/chat_panel.py`

**추가 메서드**:
```python
def add_status(self, message: str, style: str = "dim") -> str:
    """Add temporary status message

    Returns:
        status_id: ID for removing later
    """
    status_id = f"status_{int(time.time())}"

    text = Text()
    text.append("● ", style="yellow")
    text.append(message, style=style)

    self.write(text)

    return status_id

def remove_status(self, status_id: str) -> None:
    """Remove temporary status message"""
    # Remove the status line
    pass
```

**사용 예시**:
```python
# Show status
status_id = chat.add_status("계획 수립 중...")

# ... processing ...

# Remove when done
chat.remove_status(status_id)

# Show result
chat.add_message("assistant", "Here's the plan...")
```

**영향**: 사용자가 현재 무슨 일이 일어나는지 알 수 있음

### Priority 3: ⭐ MEDIUM (편의성 개선)

#### 3.1. Add: 코드 블록 자동 감지 및 Syntax Highlighting

**파일**: `agentic-ai/cli/components/chat_panel.py`

**로직**:
```python
def _detect_format(self, content: str) -> tuple[str, str]:
    """Detect content format and language

    Returns:
        (format, language):
            format: "text", "markdown", "code"
            language: "python", "typescript", "bash", etc.
    """
    # Check for code blocks
    if "```" in content:
        # Extract language from ```language
        match = re.match(r"```(\w+)", content)
        if match:
            return ("code", match.group(1))
        return ("code", "text")

    # Check for markdown indicators
    markdown_patterns = ["# ", "## ", "* ", "- ", "1. ", "[", "]("]
    if any(pattern in content for pattern in markdown_patterns):
        return ("markdown", None)

    return ("text", None)

def add_message_smart(self, role: str, content: str) -> None:
    """Add message with automatic format detection"""
    format_type, language = self._detect_format(content)

    if format_type == "markdown":
        self.add_message(role, content, format="markdown")
    elif format_type == "code":
        self.add_message(role, content, format="code", language=language)
    else:
        self.add_message(role, content, format="text")
```

**영향**: 자동으로 예쁘게 표시됨

#### 3.2. Add: LLM 응답 스트리밍을 위한 Backend 수정

**파일**: `agentic-ai/core/llm_client.py`

**현재**: 전체 응답 대기 후 반환

**개선**:
```python
async def call_llm_stream(
    self,
    messages: List[Dict[str, str]],
    **kwargs
) -> AsyncIterator[str]:
    """Call LLM with streaming support

    Yields:
        str: Token chunks as they arrive
    """
    # Use OpenAI streaming API
    async with aiohttp.ClientSession() as session:
        async with session.post(
            f"{endpoint}/chat/completions",
            json={
                "messages": messages,
                "stream": True,  # ✅ Enable streaming
                **kwargs
            }
        ) as response:
            async for line in response.content:
                # Parse SSE format
                if line.startswith(b"data: "):
                    data = json.loads(line[6:])
                    if "choices" in data:
                        token = data["choices"][0]["delta"].get("content", "")
                        if token:
                            yield token
```

**사용**:
```python
# Workflow에서
accumulated = ""
async for token in self.llm_client.call_llm_stream(messages):
    accumulated += token
    # Yield to UI
    yield {
        "type": "llm_streaming",
        "message": token,
        "accumulated": accumulated
    }
```

**영향**: LLM 토큰이 실시간으로 UI에 표시됨

#### 3.3. Add: Execute node에서 액션 상태를 Chat에 표시

**파일**: `agentic-ai/cli/backend_bridge.py`

**추가 event type**:
```python
# Execute node에서 발생시킬 이벤트
{
    "type": "action_start",
    "data": {
        "action": "READ_FILE",
        "file_path": "README.md"
    }
}

{
    "type": "action_complete",
    "data": {
        "action": "READ_FILE",
        "success": True,
        "result": "..."
    }
}
```

**UI 처리**:
```python
# app.py
elif update.type == "action_start":
    action = update.data.get("action")
    chat.add_status(f"🔧 Executing: {action}")

elif update.type == "action_complete":
    if update.data.get("success"):
        chat.add_status(f"✅ {update.data['action']} completed")
    else:
        chat.add_status(f"⚠️ {update.data['action']} failed")
```

**영향**: 사용자가 어떤 도구가 실행되는지 알 수 있음

---

## 📋 구현 순서 (Implementation Order)

### Phase 1: Critical Fixes (1-2 hours)
1. ✅ Fix reflect_node overwriting should_continue
2. ✅ Add session ID generation and display
3. ✅ Add status messages to Chat panel

### Phase 2: Streaming Support (2-3 hours)
4. ✅ Add streaming methods to ChatPanel
5. ✅ Add LLM streaming support to llm_client
6. ✅ Wire up streaming from backend to UI

### Phase 3: Visual Improvements (1-2 hours)
7. ✅ Add Markdown rendering to ChatPanel
8. ✅ Add Syntax highlighting for code blocks
9. ✅ Add auto-detection of content format

### Phase 4: UX Polish (1 hour)
10. ✅ Add action execution feedback
11. ✅ Add temporary status messages
12. ✅ Test and refine

---

## 🎯 Expected Results

### Before (Current)
```
User: "Create a plan for..."
[Long wait with no feedback]
[Progress bar updates in small area]
Assistant: [Sudden appearance of full result]

Status: No session
Error: Task failed: Max iterations reached
```

### After (Improved)
```
User: "Create a plan for..."

● Processing your request...
● 📋 Planning task execution...
● 🤔 Analyzing complexity (0.6)...
● 🔧 Executing: LIST_DIRECTORY
  ✅ Found 15 files
● 🔧 Executing: READ_FILE (README.md)
  ✅ Read 250 lines
● 💭 Reflecting on progress (2/5 steps completed)
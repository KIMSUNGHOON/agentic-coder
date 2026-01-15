# Agentic 2.0 UI/UX 설계 문서

**작성일**: 2026-01-15
**Phase**: 2 - UI/UX Design
**목표**: Claude Code CLI 수준의 UI/UX 구현을 위한 상세 설계

---

## 📊 현재 상태 분석

### 현재 Agentic 2.0 UI 구조

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

### 문제점 분석

#### 1. Chat Panel의 문제
- ❌ **파일 내용 미표시**: WRITE_FILE 실행 시 "✅ 파일 생성됨"만 표시
- ❌ **Line numbers 없음**: 코드를 보여줘도 라인 번호가 없음
- ❌ **Syntax highlighting 없음**: 코드가 plain text로 표시
- ❌ **Diff 없음**: 파일 수정 시 before/after 비교 불가
- ❌ **File size 정보 없음**: 몇 바이트인지 알 수 없음
- ❌ **Tool execution 상세 부족**: 어떤 파라미터로 실행했는지 명확하지 않음

#### 2. Progress 표시 문제
- ❌ **Step 진행률 없음**: 전체 N 단계 중 몇 단계인지 불명확
- ❌ **Iteration 정보 불명확**: 몇 회 반복 중인지 사용자가 모름
- ❌ **ETA 없음**: 언제 끝날지 예측 불가

#### 3. CoT Viewer 문제
- ❌ **비어있음**: Chain-of-Thought가 제대로 표시 안 됨
- ❌ **Reasoning 안 보임**: LLM의 사고 과정이 숨겨짐

#### 4. Interactive 기능 부재
- ❌ **Confirmation 없음**: 위험한 작업도 자동 실행
- ❌ **사용자 선택 불가**: "이 파일을 수정할까요? (y/n)" 같은 프롬프트 없음
- ❌ **중단 불가**: 작업 중간에 멈출 수 없음

#### 5. Layout 문제
- ❌ **공간 비효율**: 3개 패널로 나뉘어 각각이 작음
- ❌ **정보 분산**: 중요한 정보가 여기저기 흩어짐
- ❌ **우선순위 불명확**: 무엇이 중요한지 시각적으로 구분 안 됨

---

## 🎯 Claude Code CLI 분석

### Claude Code CLI 핵심 UX 패턴

#### 1. **Progressive Disclosure** (점진적 정보 공개)
```
You: Python 계산기 만들기

🤔 Planning...
┌─ Plan ────────────────────────────────┐
│ Task: Python 계산기 만들기               │
│ Steps: 1. Create file  2. Complete   │
└───────────────────────────────────────┘

⚙️  Step 1/2: Creating calculator.py...
📝 Writing file: calculator.py

✅ File created: calculator.py (200 bytes)

⚙️  Step 2/2: Completing...
✅ Task completed in 2 iterations
```

**핵심 원칙**:
- 한 번에 하나의 작업만 강조
- 완료된 작업은 접기 (collapsible)
- 진행 중인 작업만 확장해서 표시
- 명확한 시각적 계층 (Planning → Executing → Completed)

#### 2. **File Content Display** (파일 내용 표시)
```
📝 Writing file: calculator.py
┌─ calculator.py (NEW) ─────────────────┐
│  1 | def add(a, b):                   │
│  2 |     return a + b                 │
│  3 |                                  │
│  4 | def subtract(a, b):              │
│  5 |     return a - b                 │
└──────────────────────────────────────┘
✅ File created: calculator.py (200 bytes)
```

**핵심 요소**:
- ✅ Line numbers (왼쪽 정렬)
- ✅ File name in header
- ✅ Status indicator (NEW/MODIFIED/DELETED)
- ✅ File size in footer
- ✅ Syntax highlighting (언어별)
- ✅ Box border로 구분

#### 3. **Diff Display** (변경 사항 표시)
```
📝 Modifying file: calculator.py
┌─ calculator.py (MODIFIED) ────────────┐
│  8 | def divide(a, b):                │
│  9 |     if b == 0:                   │
│ 10 |-        return None              │ ← 제거
│ 10 |+        raise ValueError(...)    │ ← 추가
│ 11 |     return a / b                 │
└──────────────────────────────────────┘
```

**핵심 요소**:
- ✅ Unified diff format
- ✅ - (빨간색) for deletions
- ✅ + (초록색) for additions
- ✅ Context lines (변경 전후 3줄)

#### 4. **Step Progress** (단계 진행 표시)
```
⚙️  Step 1/5: Reading codebase...
⚙️  Step 2/5: Analyzing structure...
⚙️  Step 3/5: Planning refactoring...
⚙️  Step 4/5: Applying changes...
⚙️  Step 5/5: Running tests...
```

**핵심 요소**:
- ✅ Current step / Total steps
- ✅ Descriptive step name
- ✅ Spinner for long operations
- ✅ ETA (optional)

#### 5. **Summary Box** (요약 상자)
```
✅ Task completed in 3 iterations

┌─ Summary ─────────────────────────────┐
│ Created 2 files, modified 1 file      │
│                                       │
│ 📁 Files created:                     │
│   • calculator.py (200 bytes)         │
│   • test_calculator.py (150 bytes)    │
│                                       │
│ 📝 Files modified:                    │
│   • main.py (+5 -2 lines)             │
│                                       │
│ 🔧 Tools executed: 4                  │
│   • WRITE_FILE: 2                     │
│   • READ_FILE: 1                      │
│   • RUN_TESTS: 1                      │
│                                       │
│ ⏱️  Duration: 3.2s                    │
└───────────────────────────────────────┘
```

**핵심 요소**:
- ✅ Clear categorization
- ✅ File stats with sizes
- ✅ Tool usage breakdown
- ✅ Duration info

#### 6. **Interactive Confirmation** (상호작용 확인)
```
⚠️  About to delete 3 files:
   • old_config.py
   • deprecated.py
   • temp.txt

Apply these changes? (y/n) [y]: _
```

**핵심 요소**:
- ✅ Warning indicator for destructive operations
- ✅ List what will be affected
- ✅ Clear yes/no choice
- ✅ Default value shown

---

## 🎨 Agentic 2.0 개선 설계

### 설계 원칙

1. **Progressive Disclosure**: 한 번에 하나씩만 강조
2. **Visual Hierarchy**: 중요한 것이 크고 명확하게
3. **Information Density**: 필요한 정보는 모두 표시하되 정리해서
4. **Feedback Loop**: 모든 작업에 명확한 피드백
5. **User Control**: 위험한 작업은 확인 받기

### 새로운 Layout 설계

```
┌─ Agentic AI v2.0 ────────────────────────────────┐
│ 🤖 GPT-OSS-120B | Session: abc123 | ✅ Healthy   │
└──────────────────────────────────────────────────┘

You: Python 계산기 만들기

🤔 Planning...
┌─ Plan ────────────────────────────────────────────┐
│ Task: Python 계산기 만들기                           │
│ Approach: Create calculator.py with 4 functions   │
│ Steps:                                             │
│   1. Create calculator.py file                     │
│   2. Complete task                                 │
│ Estimated iterations: 2-3                          │
└────────────────────────────────────────────────────┘

⚙️  Step 1/2: Creating calculator.py...

📝 Writing file: calculator.py
┌─ calculator.py (NEW) ──────────────────────────────┐
│  1 | def add(a, b):                                │
│  2 |     return a + b                              │
│  3 |                                               │
│  4 | def subtract(a, b):                           │
│  5 |     return a - b                              │
│  6 |                                               │
│  7 | def multiply(a, b):                           │
│  8 |     return a * b                              │
│  9 |                                               │
│ 10 | def divide(a, b):                             │
│ 11 |     if b == 0:                                │
│ 12 |         raise ValueError('Divide by zero')    │
│ 13 |     return a / b                              │
└────────────────────────────────────────────────────┘
✅ File created: calculator.py (245 bytes)

⚙️  Step 2/2: Completing task...

✅ Task completed in 2 iterations

┌─ Summary ──────────────────────────────────────────┐
│ Created calculator.py with 4 arithmetic functions: │
│   • add(a, b)                                      │
│   • subtract(a, b)                                 │
│   • multiply(a, b)                                 │
│   • divide(a, b)                                   │
│                                                    │
│ 📁 Files created: 1                                │
│ 🔧 Tools executed: 1 (WRITE_FILE)                  │
│ ⏱️  Duration: 3.2s                                 │
└────────────────────────────────────────────────────┘

>
```

### 주요 변경점

#### 1. Single Column Layout
- **변경 전**: 3개 패널 (Chat | CoT | Logs)
- **변경 후**: 단일 컬럼 (모든 정보가 시간순 배치)
- **이유**:
  - 정보가 분산되지 않음
  - 스크롤만으로 전체 흐름 파악 가능
  - 각 요소가 전체 너비 사용 가능

#### 2. Step-by-Step Display
- **추가**: `⚙️ Step X/N: [description]...` 헤더
- **목적**: 사용자가 현재 진행 상황을 명확히 파악

#### 3. Full File Content Display
- **추가**: Box with line numbers
- **추가**: Syntax highlighting (Python, JS, etc.)
- **추가**: File size in bytes
- **추가**: Status indicator (NEW/MODIFIED/DELETED)

#### 4. Collapsible Sections
- **추가**: Completed sections can be collapsed
- **구현**: Rich's Collapsible or custom implementation
- **예시**:
  ```
  ✅ Step 1/3: Created calculator.py [▼] (click to expand)
  ```

#### 5. Enhanced Status Bar
- **변경 전**: `Ready | Healthy | Session: xxx | Local`
- **변경 후**: `🤖 GPT-OSS-120B | Session: abc123 | ✅ Healthy`
- **추가**: Model name, clear status icons

---

## 🛠️ Component 설계

### 1. ChatPanel 개선

**파일**: `cli/components/chat_panel.py`

#### 새로운 메서드

```python
class ChatPanel:
    def add_file_content(
        self,
        file_path: str,
        content: str,
        status: Literal["NEW", "MODIFIED", "DELETED"],
        display_mode: Literal["full", "preview", "hidden"] = "full",
        language: Optional[str] = None,
    ):
        """Display file content with line numbers and syntax highlighting

        Args:
            file_path: Path to file
            content: File content
            status: NEW, MODIFIED, or DELETED
            display_mode: full (all lines), preview (first 10), hidden (none)
            language: Programming language for syntax highlighting

        Example:
            chat.add_file_content(
                "calculator.py",
                content="def add(a, b):\n    return a + b",
                status="NEW",
                display_mode="full",
                language="python"
            )
        """
        pass

    def add_file_diff(
        self,
        file_path: str,
        old_content: str,
        new_content: str,
        context_lines: int = 3,
    ):
        """Display unified diff for file changes

        Args:
            file_path: Path to file
            old_content: Original content
            new_content: New content
            context_lines: Number of context lines around changes

        Example:
            chat.add_file_diff(
                "calculator.py",
                old_content="...",
                new_content="...",
                context_lines=3
            )
        """
        pass

    def add_step_header(
        self,
        step_num: int,
        total_steps: int,
        description: str,
        status: Literal["pending", "in_progress", "completed", "failed"] = "in_progress",
    ):
        """Display step progress header

        Args:
            step_num: Current step number (1-indexed)
            total_steps: Total number of steps
            description: Step description
            status: Current status

        Example:
            chat.add_step_header(1, 5, "Creating calculator.py", "in_progress")
            # Output: ⚙️  Step 1/5: Creating calculator.py...
        """
        pass

    def add_plan_summary(
        self,
        task: str,
        approach: str,
        steps: List[str],
        estimated_iterations: Optional[int] = None,
    ):
        """Display plan in a box

        Args:
            task: Task description
            approach: High-level approach
            steps: List of steps
            estimated_iterations: Estimated iterations (optional)

        Example:
            chat.add_plan_summary(
                task="Python 계산기 만들기",
                approach="Create calculator.py with arithmetic functions",
                steps=["Create file", "Complete"],
                estimated_iterations=3
            )
        """
        pass

    def add_task_summary(
        self,
        duration: float,
        files_created: List[Tuple[str, int]],  # (path, size_bytes)
        files_modified: List[Tuple[str, int, int]],  # (path, lines_added, lines_removed)
        files_deleted: List[str],
        tool_usage: Dict[str, int],  # {tool_name: count}
        iterations: int,
    ):
        """Display task completion summary

        Args:
            duration: Task duration in seconds
            files_created: List of (path, size) tuples
            files_modified: List of (path, +lines, -lines) tuples
            files_deleted: List of deleted file paths
            tool_usage: Tool usage counts
            iterations: Total iterations used

        Example:
            chat.add_task_summary(
                duration=3.2,
                files_created=[("calculator.py", 245)],
                files_modified=[],
                files_deleted=[],
                tool_usage={"WRITE_FILE": 1},
                iterations=2
            )
        """
        pass

    def add_confirmation_prompt(
        self,
        message: str,
        items: Optional[List[str]] = None,
        warning: bool = False,
        default: bool = True,
    ) -> bool:
        """Display confirmation prompt and wait for user input

        Args:
            message: Confirmation message
            items: List of items to be affected (optional)
            warning: Show warning indicator
            default: Default value (True for yes, False for no)

        Returns:
            True if user confirms, False otherwise

        Example:
            if chat.add_confirmation_prompt(
                "About to delete files",
                items=["old.py", "temp.txt"],
                warning=True,
                default=False
            ):
                # proceed with deletion
        """
        pass
```

#### 구현 상세

##### File Content Display

```python
from rich.syntax import Syntax
from rich.panel import Panel
from rich.text import Text

def add_file_content(self, file_path, content, status, display_mode="full", language=None):
    # Determine language from file extension if not provided
    if language is None:
        ext = Path(file_path).suffix.lstrip('.')
        language = {
            'py': 'python',
            'js': 'javascript',
            'ts': 'typescript',
            'java': 'java',
            'cpp': 'cpp',
            'c': 'c',
            'go': 'go',
            'rs': 'rust',
            'md': 'markdown',
        }.get(ext, 'text')

    # Truncate if preview mode
    lines = content.split('\n')
    if display_mode == "preview" and len(lines) > 10:
        content = '\n'.join(lines[:10]) + '\n...'
    elif display_mode == "hidden":
        return  # Don't display

    # Create syntax-highlighted code
    syntax = Syntax(
        content,
        language,
        theme="monokai",
        line_numbers=True,
        word_wrap=False,
        indent_guides=False,
    )

    # Status indicator
    status_icon = {
        "NEW": "📄",
        "MODIFIED": "📝",
        "DELETED": "🗑️",
    }[status]

    # Create panel
    panel = Panel(
        syntax,
        title=f"{status_icon} {file_path} ({status})",
        border_style="green" if status == "NEW" else "yellow",
    )

    self.console.print(panel)
```

##### Diff Display

```python
import difflib

def add_file_diff(self, file_path, old_content, new_content, context_lines=3):
    old_lines = old_content.split('\n')
    new_lines = new_content.split('\n')

    # Generate unified diff
    diff = difflib.unified_diff(
        old_lines,
        new_lines,
        fromfile=f"{file_path} (before)",
        tofile=f"{file_path} (after)",
        lineterm='',
        n=context_lines
    )

    # Format diff with colors
    diff_text = Text()
    for line in diff:
        if line.startswith('+') and not line.startswith('+++'):
            diff_text.append(line + '\n', style="green")
        elif line.startswith('-') and not line.startswith('---'):
            diff_text.append(line + '\n', style="red")
        elif line.startswith('@@'):
            diff_text.append(line + '\n', style="cyan bold")
        else:
            diff_text.append(line + '\n')

    panel = Panel(
        diff_text,
        title=f"📝 {file_path} (MODIFIED)",
        border_style="yellow",
    )

    self.console.print(panel)
```

##### Step Header

```python
def add_step_header(self, step_num, total_steps, description, status="in_progress"):
    icons = {
        "pending": "⏳",
        "in_progress": "⚙️",
        "completed": "✅",
        "failed": "❌",
    }

    icon = icons[status]

    if status == "in_progress":
        text = f"{icon} Step {step_num}/{total_steps}: {description}..."
    else:
        text = f"{icon} Step {step_num}/{total_steps}: {description}"

    self.console.print(text, style="bold")
```

### 2. ProgressDisplay 개선

**파일**: `cli/components/progress_display.py`

#### 새로운 기능

```python
from rich.progress import Progress, SpinnerColumn, TextColumn, BarColumn, TimeRemainingColumn

class EnhancedProgressDisplay:
    def __init__(self):
        self.progress = Progress(
            SpinnerColumn(),
            TextColumn("[progress.description]{task.description}"),
            BarColumn(),
            TextColumn("[progress.percentage]{task.percentage:>3.0f}%"),
            TimeRemainingColumn(),
        )

    def show_iteration_progress(self, current: int, total: int, description: str):
        """Show iteration progress with ETA

        Example:
            progress.show_iteration_progress(3, 10, "Executing actions")
            # Output: [spinner] Executing actions |████████░░░░░░░░| 30% ETA 0:00:14
        """
        pass

    def show_step_progress(self, current_step: int, total_steps: int, step_name: str):
        """Show step progress

        Example:
            progress.show_step_progress(2, 5, "Analyzing codebase")
            # Output: Step 2/5: Analyzing codebase [spinner]
        """
        pass
```

### 3. CoTViewer 개선

**파일**: `cli/components/cot_viewer.py`

#### 새로운 기능

```python
class CoTViewer:
    def display_reasoning(
        self,
        reasoning_text: str,
        collapsed: bool = False,
    ):
        """Display LLM's chain-of-thought reasoning

        Args:
            reasoning_text: Reasoning content
            collapsed: Whether to show collapsed initially

        Example:
            cot.display_reasoning(
                "I need to create a calculator file...",
                collapsed=True
            )
        """
        pass

    def display_thinking_indicator(self):
        """Show animated thinking indicator

        Example:
            cot.display_thinking_indicator()
            # Output: 🤔 Thinking... [spinner]
        """
        pass
```

---

## 📋 구현 우선순위

### Priority 1: Core Display (6시간)
1. **File Content Display** (2시간)
   - Line numbers
   - Syntax highlighting (Python, JS, TS, Java, Go, Rust)
   - Status indicators (NEW/MODIFIED/DELETED)
   - File size display

2. **Diff Display** (2시간)
   - Unified diff format
   - Color coding (red/green)
   - Context lines

3. **Step Progress** (2시간)
   - Step X/N headers
   - Clear status indicators
   - Integration with workflow

### Priority 2: Enhanced Feedback (4시간)
4. **Plan Summary Box** (1시간)
   - Task description
   - Approach
   - Steps list
   - Estimated iterations

5. **Task Summary Box** (2시간)
   - Files created/modified/deleted
   - Tool usage breakdown
   - Duration and iteration count

6. **Progress Indicators** (1시간)
   - Spinner for long operations
   - Progress bars
   - ETA estimation

### Priority 3: Interactive Features (3시간)
7. **Confirmation Prompts** (2시간)
   - Yes/no prompts
   - Warning indicators
   - Default values

8. **Collapsible Sections** (1시간)
   - Expand/collapse completed steps
   - Memory-efficient display

### Priority 4: Layout & Polish (2시간)
9. **Single Column Layout** (1시간)
   - Remove 3-panel split
   - Full-width display
   - Better information flow

10. **Visual Polish** (1시간)
    - Consistent styling
    - Better borders and boxes
    - Emoji indicators

**Total**: 15시간

---

## ✅ 성공 기준

### 사용자 관점
1. ✅ 파일 내용을 **전부** 볼 수 있어야 함
2. ✅ 파일 수정 시 **변경사항**(diff)을 볼 수 있어야 함
3. ✅ 현재 **몇 단계** 중 **몇 번째**인지 알 수 있어야 함
4. ✅ 작업이 **언제 끝날지** 예측할 수 있어야 함
5. ✅ 위험한 작업 전에 **확인**받아야 함

### 개발자 관점
1. ✅ Rich library 활용 (Syntax, Panel, Progress)
2. ✅ 기존 코드와의 호환성 유지
3. ✅ 성능 저하 없음 (lazy rendering)
4. ✅ 테스트 가능한 구조
5. ✅ 확장 가능한 디자인

### 비교 기준
**Before** (현재):
```
🔧 Tool [1]: WRITE_FILE(calculator.py) ✅
```

**After** (개선 후):
```
📝 Writing file: calculator.py
┌─ calculator.py (NEW) ──────────────────┐
│  1 | def add(a, b):                    │
│  2 |     return a + b                  │
│  3 |                                   │
│  4 | def subtract(a, b):               │
│  5 |     return a - b                  │
└───────────────────────────────────────┘
✅ File created: calculator.py (200 bytes)
```

---

## 🎯 다음 단계

**Phase 2 완료 후**: Phase 3 (구현) 시작

**Phase 3 Roadmap**:
1. Chat Panel 개선 (6시간)
2. Progress Display 개선 (2시간)
3. CoT Viewer 개선 (1시간)
4. Interactive Confirmations (2시간)
5. Layout Redesign (2시간)
6. Integration & Testing (2시간)

**Total Phase 3**: 15시간 (약 2일)

---

## 📝 설계 완료 체크리스트

- [x] 현재 문제점 분석
- [x] Claude Code CLI 패턴 분석
- [x] 새로운 Layout 설계
- [x] Component별 상세 설계
- [x] 구현 우선순위 정의
- [x] 성공 기준 정의
- [ ] 사용자 승인 대기

**다음**: 사용자 승인 후 Phase 3 (구현) 시작

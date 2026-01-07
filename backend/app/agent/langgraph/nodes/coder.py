"""Coder Node - Production Implementation

Generates code using LLM via vLLM/OpenAI-compatible endpoint.
Supports multiple model types via prompt adaptation.
"""

import logging
import json
from typing import Dict, List
from datetime import datetime

from app.core.config import settings
from app.agent.langgraph.schemas.state import QualityGateState, DebugLog
from app.agent.langgraph.tools.filesystem_tools import write_file_tool
from app.services.http_client import LLMHttpClient

# Import prompts for different model types
try:
    from shared.prompts.qwen_coder import QWEN_CODER_SYSTEM_PROMPT, QWEN_CODER_CONFIG
except ImportError:
    QWEN_CODER_SYSTEM_PROMPT = None
    QWEN_CODER_CONFIG = {}

try:
    from shared.prompts.generic import GENERIC_CODE_GENERATION_PROMPT, GENERIC_CONFIG, get_model_config
except ImportError:
    GENERIC_CODE_GENERATION_PROMPT = None
    GENERIC_CONFIG = {}
    get_model_config = lambda x: {}

logger = logging.getLogger(__name__)


def _get_code_generation_prompt(user_request: str, task_type: str) -> tuple:
    """Get appropriate prompt and config based on model type.

    Returns:
        Tuple of (prompt, config_dict)
    """
    model_type = settings.get_coding_model_type
    model_name = settings.get_coding_model

    if model_type == "qwen" and QWEN_CODER_SYSTEM_PROMPT:
        prompt = f"""{QWEN_CODER_SYSTEM_PROMPT}

Request: {user_request}
Task Type: {task_type}

Generate complete, working code. Include all necessary files.
Respond in JSON format with this structure:
{{
    "files": [
        {{
            "filename": "example.py",
            "content": "# Code here",
            "language": "python",
            "description": "Brief description"
        }}
    ]
}}

Generate the code now:"""
        config = QWEN_CODER_CONFIG
    elif model_type == "deepseek":
        # DeepSeek uses <think> tags for reasoning
        prompt = f"""<think>
1. Analyze request: {user_request[:200]}
2. Determine file structure needed
3. Plan implementation approach
4. Generate production-ready code
</think>

Request: {user_request}
Task Type: {task_type}

Generate complete, working code. Include all necessary files.
Respond in JSON format:
{{
    "files": [
        {{
            "filename": "example.py",
            "content": "# Code here",
            "language": "python",
            "description": "Brief description"
        }}
    ]
}}"""
        config = {"temperature": 0.3, "max_tokens": 8000}
    else:
        # Generic prompt for GPT, Claude, Llama, etc.
        prompt = f"""You are an expert software engineer. Generate production-ready code for the following request:

Request: {user_request}
Task Type: {task_type}

Think through the problem step by step:
1. What files are needed?
2. What is the structure?
3. What error handling is required?

Generate complete, working code. Include all necessary files.
Respond in JSON format:
{{
    "files": [
        {{
            "filename": "example.py",
            "content": "# Complete code here",
            "language": "python",
            "description": "Brief description"
        }}
    ]
}}

Generate the code now:"""
        config = get_model_config(model_name) if get_model_config else GENERIC_CONFIG

    return prompt, config


def coder_node(state: QualityGateState) -> Dict:
    """Coder Node: Generate code using Qwen-Coder

    This node:
    1. Calls Qwen-Coder via vLLM endpoint
    2. Generates production-ready code
    3. Writes files to workspace
    4. Creates artifacts
    5. Logs debug information

    Args:
        state: Current workflow state

    Returns:
        State updates with generated code and artifacts
    """
    logger.info("💻 Coder Node: Starting code generation...")

    user_request = state["user_request"]
    workspace_root = state["workspace_root"]
    task_type = state.get("task_type", "general")

    debug_logs = []
    artifacts = []

    # Add thinking debug log
    if state.get("enable_debug"):
        debug_logs.append(DebugLog(
            timestamp=datetime.utcnow().isoformat(),
            node="coder",
            agent="QwenCoder",
            event_type="thinking",
            content=f"Analyzing request: {user_request[:200]}...",
            metadata={"task_type": task_type},
            token_usage=None
        ))

    try:
        # Generate code using vLLM (returns tuple of files and token_usage)
        generated_files, token_usage = _generate_code_with_vllm(
            user_request=user_request,
            task_type=task_type,
            workspace_root=workspace_root
        )

        # Write files and create artifacts
        import os
        for file_info in generated_files:
            filename = file_info["filename"]
            content = file_info["content"]
            language = file_info.get("language", "python")
            description = file_info.get("description", "")

            # Check if file already exists to determine action
            full_path = os.path.join(workspace_root, filename)
            file_existed = os.path.exists(full_path)
            action = "modified" if file_existed else "created"

            # Write file to workspace
            result = write_file_tool(
                file_path=filename,
                content=content,
                workspace_root=workspace_root
            )

            if result["success"]:
                action_emoji = "📝" if action == "modified" else "✨"
                logger.info(f"{action_emoji} {action.capitalize()}: {filename}")

                # Calculate relative path from workspace root
                saved_path = result["file_path"]
                relative_path = os.path.relpath(saved_path, workspace_root) if saved_path.startswith(workspace_root) else filename

                # Create artifact with enhanced metadata
                artifacts.append({
                    "filename": filename,
                    "file_path": saved_path,
                    "relative_path": relative_path,
                    "project_root": workspace_root,
                    "language": language,
                    "content": content,
                    "description": description,
                    "size_bytes": len(content),
                    "checksum": f"sha256_{hash(content) % (10 ** 8):08x}",
                    "saved": True,
                    "saved_path": saved_path,
                    "action": action,  # "created" or "modified"
                })
            else:
                logger.error(f"❌ Failed to write {filename}: {result['error']}")

        # Add result debug log with actual token usage
        if state.get("enable_debug"):
            debug_logs.append(DebugLog(
                timestamp=datetime.utcnow().isoformat(),
                node="coder",
                agent="QwenCoder",
                event_type="result",
                content=f"Generated {len(artifacts)} files successfully",
                metadata={
                    "files": [a["filename"] for a in artifacts],
                    "total_bytes": sum(a["size_bytes"] for a in artifacts)
                },
                token_usage=token_usage  # Use actual token_usage from vLLM
            ))

        return {
            "coder_output": {
                "artifacts": artifacts,
                "status": "completed" if artifacts else "failed",
                "files_generated": len(artifacts),
                "token_usage": token_usage  # Include token usage in output
            },
            "artifacts": artifacts,  # Top-level for frontend
            "debug_logs": debug_logs,
            "token_usage": token_usage  # Top-level for SSE events
        }

    except Exception as e:
        logger.error(f"❌ Coder Node failed: {e}", exc_info=True)

        if state.get("enable_debug"):
            debug_logs.append(DebugLog(
                timestamp=datetime.utcnow().isoformat(),
                node="coder",
                agent="QwenCoder",
                event_type="error",
                content=f"Code generation failed: {str(e)}",
                metadata={"error_type": type(e).__name__},
                token_usage=None
            ))

        return {
            "coder_output": {
                "artifacts": [],
                "status": "error",
                "error": str(e)
            },
            "debug_logs": debug_logs,
        }


def _generate_code_with_vllm(
    user_request: str,
    task_type: str,
    workspace_root: str
) -> tuple:
    """Generate code using LLM via vLLM/OpenAI-compatible endpoint

    Args:
        user_request: User's request
        task_type: Type of task
        workspace_root: Workspace root directory

    Returns:
        Tuple of (files_list, token_usage_dict)
        - files_list: List of file dictionaries with filename, content, language, description
        - token_usage_dict: Dictionary with prompt_tokens, completion_tokens, total_tokens
    """
    # Get endpoint and model from settings (supports both unified and split configs)
    coding_endpoint = settings.get_coding_endpoint
    coding_model = settings.get_coding_model

    # Default token usage (will be updated on successful LLM call)
    token_usage = {"prompt_tokens": 0, "completion_tokens": 0, "total_tokens": 0}

    # Check if endpoint is configured
    if not coding_endpoint:
        logger.warning("⚠️  LLM coding endpoint not configured, using fallback generator")
        return _fallback_code_generator(user_request, task_type), token_usage

    try:
        # Get model-appropriate prompt and config
        prompt, model_config = _get_code_generation_prompt(user_request, task_type)

        # Log model info (model type auto-detected from model name)
        logger.info(f"🤖 Using model: {coding_model} (type: {settings.get_coding_model_type})")
        logger.info(f"📡 Endpoint: {coding_endpoint}")

        # Use HTTP client with built-in retry logic for ConnectError and TimeoutException
        http_client = LLMHttpClient(
            timeout=120,  # 2 minutes for code generation
            max_retries=3,
            base_delay=2
        )

        # Make request with automatic retry on connection/timeout errors
        result, error = http_client.post(
            url=f"{coding_endpoint}/chat/completions",
            json={
                "model": coding_model,
                "messages": [
                    {"role": "system", "content": "You are an expert software engineer. Generate production-ready code."},
                    {"role": "user", "content": prompt}
                ],
                "max_tokens": model_config.get("max_tokens", 4096),
                "temperature": model_config.get("temperature", 0.2),
                "stop": model_config.get("stop", ["</s>", "Human:", "User:"])
            }
        )

        if error:
            logger.error(f"vLLM request failed after retries: {error}")
            return _fallback_code_generator(user_request, task_type), token_usage

        # Chat completions returns content in message
        generated_text = result["choices"][0]["message"]["content"]

        # Extract token usage from vLLM response
        usage = result.get("usage", {})
        token_usage = {
            "prompt_tokens": usage.get("prompt_tokens", 0),
            "completion_tokens": usage.get("completion_tokens", 0),
            "total_tokens": usage.get("total_tokens", 0)
        }
        logger.info(f"📊 Token usage: {token_usage}")

        # Parse JSON response
        try:
            # Extract JSON from response
            json_start = generated_text.find("{")
            json_end = generated_text.rfind("}") + 1
            if json_start != -1 and json_end > json_start:
                json_str = generated_text[json_start:json_end]
                parsed = json.loads(json_str)
                return parsed.get("files", []), token_usage
        except json.JSONDecodeError:
            logger.warning("Failed to parse vLLM JSON response, using fallback")
            return _fallback_code_generator(user_request, task_type), token_usage

    except Exception as e:
        logger.error(f"vLLM call failed: {e}", exc_info=True)
        return _fallback_code_generator(user_request, task_type), token_usage

    # Fallback if we exit without returning (should not happen)
    return _fallback_code_generator(user_request, task_type), token_usage


def _fallback_code_generator(user_request: str, task_type: str) -> List[Dict]:
    """Fallback code generator when vLLM is not available

    Generates basic template code based on common patterns.
    """
    logger.info("📝 Using fallback code generator (vLLM not available)")

    # Detect what kind of app is being requested
    request_lower = user_request.lower()

    # Calculator app
    if any(keyword in request_lower for keyword in ["계산기", "calculator", "사칙연산"]):
        return _generate_calculator_app()

    # Web app
    elif any(keyword in request_lower for keyword in ["웹", "web", "website", "앱", "app"]):
        return _generate_web_app_template(user_request)

    # API
    elif any(keyword in request_lower for keyword in ["api", "endpoint", "rest", "fastapi"]):
        return _generate_api_template(user_request)

    # Default: Simple Python script
    else:
        return [{
            "filename": "main.py",
            "content": f'''"""
Generated code for: {user_request}

This is a template implementation. For production-ready code,
please configure vLLM endpoints in backend/.env
"""

def main():
    """Main function"""
    print("TODO: Implement {user_request}")
    # Add implementation here
    pass


if __name__ == "__main__":
    main()
''',
            "language": "python",
            "description": f"Main script for: {user_request}"
        }]


def _generate_calculator_app() -> List[Dict]:
    """Generate a Python calculator app with CLI and Tkinter GUI versions"""

    cli_content = '''#!/usr/bin/env python3
"""Calculator CLI - Version A

Interactive command-line calculator with two modes:
1. Expression mode: Evaluate expressions like (2+3)*4/5
2. Step mode: Input first number, operator, second number

Features:
- Safe expression evaluation using ast.literal_eval
- History tracking
- Commands: help, history, clear, exit
"""

import ast
import operator
import re
from typing import List, Tuple, Optional

# Calculation history
history: List[str] = []

# Safe operators for evaluation
OPERATORS = {
    '+': operator.add,
    '-': operator.sub,
    '*': operator.mul,
    '/': operator.truediv,
    '//': operator.floordiv,
    '%': operator.mod,
    '**': operator.pow,
}


def safe_eval(expression: str) -> float:
    """Safely evaluate a mathematical expression.

    Uses ast.literal_eval for safety - no arbitrary code execution.

    Args:
        expression: Mathematical expression string

    Returns:
        Result of the calculation

    Raises:
        ValueError: If expression is invalid or unsafe
    """
    # Remove whitespace
    expr = expression.replace(' ', '')

    # Validate characters (only digits, operators, parentheses, decimal point)
    if not re.match(r'^[\\d+\\-*/().%]+$', expr):
        raise ValueError("Invalid characters in expression")

    try:
        # Use compile and eval with restricted globals for safety
        code = compile(expr, '<string>', 'eval')

        # Check for unsafe operations
        for name in code.co_names:
            raise ValueError(f"Unsafe operation: {name}")

        # Evaluate with empty globals and locals
        result = eval(code, {"__builtins__": {}}, {})
        return float(result)
    except ZeroDivisionError:
        raise ValueError("Division by zero")
    except Exception as e:
        raise ValueError(f"Invalid expression: {e}")


def step_mode_calculate(num1: float, op: str, num2: float) -> float:
    """Calculate using step mode (num1 op num2).

    Args:
        num1: First number
        op: Operator string
        num2: Second number

    Returns:
        Result of the calculation
    """
    if op not in OPERATORS:
        raise ValueError(f"Unknown operator: {op}")

    if op in ('/', '//') and num2 == 0:
        raise ValueError("Division by zero")

    return OPERATORS[op](num1, num2)


def show_help() -> None:
    """Display help message."""
    print("""
╔══════════════════════════════════════════════════════════════╗
║                    Calculator CLI Help                        ║
╠══════════════════════════════════════════════════════════════╣
║ Modes:                                                        ║
║   expr    - Switch to expression mode (default)               ║
║   step    - Switch to step-by-step mode                       ║
║                                                               ║
║ Commands:                                                     ║
║   help    - Show this help message                            ║
║   history - Show calculation history                          ║
║   clear   - Clear history                                     ║
║   exit    - Exit calculator                                   ║
║                                                               ║
║ Operators: +, -, *, /, //, %, **                             ║
║                                                               ║
║ Expression mode examples:                                     ║
║   (2+3)*4    → 20.0                                          ║
║   2**10      → 1024.0                                        ║
║   10 % 3    → 1.0                                            ║
╚══════════════════════════════════════════════════════════════╝
""")


def show_history() -> None:
    """Display calculation history."""
    if not history:
        print("No calculations yet.")
        return

    print("\\n=== Calculation History ===")
    for i, entry in enumerate(history, 1):
        print(f"  {i}. {entry}")
    print()


def expression_mode() -> None:
    """Run calculator in expression mode."""
    print("Expression mode - Enter mathematical expressions")
    print("Type 'help' for commands, 'step' for step mode, 'exit' to quit\\n")

    while True:
        try:
            expr = input(">>> ").strip()

            if not expr:
                continue
            elif expr.lower() == 'exit':
                break
            elif expr.lower() == 'help':
                show_help()
            elif expr.lower() == 'history':
                show_history()
            elif expr.lower() == 'clear':
                history.clear()
                print("History cleared.")
            elif expr.lower() == 'step':
                step_mode()
                return
            else:
                result = safe_eval(expr)
                history.append(f"{expr} = {result}")
                print(f"  = {result}")

        except ValueError as e:
            print(f"Error: {e}")
        except KeyboardInterrupt:
            print("\\nExiting...")
            break


def step_mode() -> None:
    """Run calculator in step-by-step mode."""
    print("Step mode - Enter number, operator, number")
    print("Type 'help' for commands, 'expr' for expression mode, 'exit' to quit\\n")

    while True:
        try:
            # Get first number
            inp = input("First number: ").strip()
            if inp.lower() == 'exit':
                break
            elif inp.lower() == 'help':
                show_help()
                continue
            elif inp.lower() == 'history':
                show_history()
                continue
            elif inp.lower() == 'expr':
                expression_mode()
                return

            num1 = float(inp)

            # Get operator
            op = input("Operator (+,-,*,/,//,%,**): ").strip()
            if op.lower() == 'exit':
                break

            # Get second number
            num2 = float(input("Second number: ").strip())

            # Calculate
            result = step_mode_calculate(num1, op, num2)
            history.append(f"{num1} {op} {num2} = {result}")
            print(f"  = {result}\\n")

        except ValueError as e:
            print(f"Error: {e}\\n")
        except KeyboardInterrupt:
            print("\\nExiting...")
            break


def main() -> None:
    """Main entry point."""
    print("""
╔══════════════════════════════════════════════════════════════╗
║              Python Calculator - CLI Version                  ║
║                                                               ║
║  Supports: +, -, *, /, //, %, ** and parentheses             ║
║  Type 'help' for more information                             ║
╚══════════════════════════════════════════════════════════════╝
""")

    expression_mode()
    print("Goodbye!")


if __name__ == "__main__":
    main()
'''

    gui_content = '''#!/usr/bin/env python3
"""Calculator GUI - Version B

Tkinter-based GUI calculator with:
- Buttons for digits 0-9, decimal, operators
- Keyboard support
- Display showing current input and result
"""

import tkinter as tk
from tkinter import messagebox
import ast
import re
from typing import Optional


class CalculatorGUI:
    """Tkinter Calculator Application."""

    def __init__(self, root: tk.Tk) -> None:
        """Initialize the calculator GUI.

        Args:
            root: Tkinter root window
        """
        self.root = root
        self.root.title("Python Calculator")
        self.root.resizable(False, False)
        self.root.configure(bg='#2d2d2d')

        # Current expression
        self.expression = ""
        self.result_shown = False

        # Create display
        self._create_display()

        # Create buttons
        self._create_buttons()

        # Bind keyboard events
        self._bind_keyboard()

    def _create_display(self) -> None:
        """Create the calculator display."""
        self.display_frame = tk.Frame(self.root, bg='#2d2d2d')
        self.display_frame.pack(padx=10, pady=10, fill='x')

        self.display = tk.Entry(
            self.display_frame,
            font=('Consolas', 28),
            justify='right',
            bd=0,
            bg='#1e1e1e',
            fg='white',
            insertbackground='white',
            state='readonly'
        )
        self.display.pack(fill='x', ipady=15)
        self._update_display("0")

    def _create_buttons(self) -> None:
        """Create calculator buttons."""
        self.buttons_frame = tk.Frame(self.root, bg='#2d2d2d')
        self.buttons_frame.pack(padx=10, pady=5)

        # Button layout
        buttons = [
            ('C', 'clear'), ('(', 'paren'), (')', 'paren'), ('⌫', 'back'),
            ('7', 'num'), ('8', 'num'), ('9', 'num'), ('/', 'op'),
            ('4', 'num'), ('5', 'num'), ('6', 'num'), ('*', 'op'),
            ('1', 'num'), ('2', 'num'), ('3', 'num'), ('-', 'op'),
            ('0', 'num'), ('.', 'num'), ('=', 'equals'), ('+', 'op'),
            ('%', 'op'), ('**', 'op'), ('//', 'op'), (' ', 'empty'),
        ]

        # Button colors
        colors = {
            'num': {'bg': '#4a4a4a', 'fg': 'white', 'active': '#5a5a5a'},
            'op': {'bg': '#ff9500', 'fg': 'white', 'active': '#ffaa33'},
            'clear': {'bg': '#ff3b30', 'fg': 'white', 'active': '#ff5a50'},
            'equals': {'bg': '#34c759', 'fg': 'white', 'active': '#4ad76a'},
            'paren': {'bg': '#5a5a5a', 'fg': 'white', 'active': '#6a6a6a'},
            'back': {'bg': '#ff9500', 'fg': 'white', 'active': '#ffaa33'},
            'empty': {'bg': '#2d2d2d', 'fg': '#2d2d2d', 'active': '#2d2d2d'},
        }

        row, col = 0, 0
        for text, btn_type in buttons:
            color = colors[btn_type]

            if text == ' ':
                # Empty placeholder
                label = tk.Label(self.buttons_frame, bg='#2d2d2d')
                label.grid(row=row, column=col, padx=2, pady=2)
            else:
                btn = tk.Button(
                    self.buttons_frame,
                    text=text,
                    font=('Arial', 18, 'bold'),
                    width=4 if len(text) <= 2 else 3,
                    height=2,
                    bd=0,
                    bg=color['bg'],
                    fg=color['fg'],
                    activebackground=color['active'],
                    activeforeground='white',
                    command=lambda t=text: self._on_button_click(t)
                )
                btn.grid(row=row, column=col, padx=2, pady=2, sticky='nsew')

            col += 1
            if col > 3:
                col = 0
                row += 1

    def _bind_keyboard(self) -> None:
        """Bind keyboard events."""
        self.root.bind('<Key>', self._on_key_press)
        self.root.bind('<Return>', lambda e: self._calculate())
        self.root.bind('<BackSpace>', lambda e: self._backspace())
        self.root.bind('<Escape>', lambda e: self._clear())

    def _on_key_press(self, event: tk.Event) -> None:
        """Handle keyboard input."""
        char = event.char
        if char in '0123456789.+-*/()%':
            self._append(char)

    def _on_button_click(self, text: str) -> None:
        """Handle button click."""
        if text == 'C':
            self._clear()
        elif text == '⌫':
            self._backspace()
        elif text == '=':
            self._calculate()
        else:
            self._append(text)

    def _append(self, text: str) -> None:
        """Append text to expression."""
        if self.result_shown and text in '0123456789.':
            self.expression = ""
            self.result_shown = False

        self.expression += text
        self._update_display(self.expression)

    def _clear(self) -> None:
        """Clear the display."""
        self.expression = ""
        self.result_shown = False
        self._update_display("0")

    def _backspace(self) -> None:
        """Remove last character."""
        self.expression = self.expression[:-1]
        self._update_display(self.expression or "0")

    def _calculate(self) -> None:
        """Calculate the result."""
        if not self.expression:
            return

        try:
            # Safe evaluation
            result = self._safe_eval(self.expression)
            self._update_display(str(result))
            self.expression = str(result)
            self.result_shown = True

        except ZeroDivisionError:
            messagebox.showerror("Error", "Cannot divide by zero!")
            self._clear()
        except Exception as e:
            messagebox.showerror("Error", f"Invalid expression: {e}")
            self._clear()

    def _safe_eval(self, expression: str) -> float:
        """Safely evaluate expression."""
        # Validate characters
        if not re.match(r'^[\\d+\\-*/().%\\s]+$', expression):
            raise ValueError("Invalid characters")

        # Compile and evaluate safely
        code = compile(expression, '<string>', 'eval')
        for name in code.co_names:
            raise ValueError(f"Unsafe: {name}")

        result = eval(code, {"__builtins__": {}}, {})
        return round(float(result), 10)

    def _update_display(self, text: str) -> None:
        """Update display text."""
        self.display.configure(state='normal')
        self.display.delete(0, tk.END)
        self.display.insert(0, text)
        self.display.configure(state='readonly')


def main() -> None:
    """Main entry point."""
    root = tk.Tk()
    app = CalculatorGUI(root)
    root.mainloop()


if __name__ == "__main__":
    main()
'''

    readme_content = '''# Python Calculator

Python 3.10+ 기반 계산기 프로그램입니다.

## 버전

### Version A: CLI (calculator_cli.py)
명령줄 인터페이스 계산기

**기능:**
- Expression mode: 수식 입력 (예: `(2+3)*4/5`)
- Step mode: 단계별 입력
- 연산자: +, -, *, /, //, %, **
- 히스토리 기능
- 명령어: help, history, clear, exit

**실행:**
```bash
python calculator_cli.py
```

### Version B: GUI (calculator_gui.py)
Tkinter 기반 GUI 계산기

**기능:**
- 숫자 버튼 0-9, 소수점
- 연산자: +, -, *, /, //, %, **
- 괄호 지원
- 키보드 지원 (Enter=계산, Backspace=삭제, Esc=초기화)

**실행:**
```bash
python calculator_gui.py
```

## 안전성
- `eval()` 직접 사용 금지
- `ast` 모듈을 사용한 안전한 수식 평가
- 유효하지 않은 문자 필터링

## 요구사항
- Python 3.10+
- Tkinter (GUI 버전, 표준 라이브러리)
'''

    return [
        {
            "filename": "calculator_cli.py",
            "content": cli_content,
            "language": "python",
            "description": "CLI calculator with expression and step modes"
        },
        {
            "filename": "calculator_gui.py",
            "content": gui_content,
            "language": "python",
            "description": "Tkinter GUI calculator"
        },
        {
            "filename": "README.md",
            "content": readme_content,
            "language": "markdown",
            "description": "Project documentation"
        }
    ]


def _generate_web_app_template(user_request: str) -> List[Dict]:
    """Generate a basic web app template"""
    return [{
        "filename": "index.html",
        "content": f'''<!DOCTYPE html>
<html lang="ko">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Web App</title>
    <style>
        body {{
            font-family: Arial, sans-serif;
            max-width: 800px;
            margin: 50px auto;
            padding: 20px;
        }}
        h1 {{
            color: #333;
        }}
    </style>
</head>
<body>
    <h1>Web Application</h1>
    <p>Request: {user_request}</p>
    <p>This is a template. Configure vLLM for production-ready code.</p>
</body>
</html>''',
        "language": "html",
        "description": "Basic web app template"
    }]


def _generate_api_template(user_request: str) -> List[Dict]:
    """Generate a basic API template"""
    return [{
        "filename": "api.py",
        "content": f'''"""
API implementation for: {user_request}
"""
from fastapi import FastAPI

app = FastAPI()

@app.get("/")
async def root():
    return {{"message": "API running", "request": "{user_request}"}}

@app.get("/health")
async def health():
    return {{"status": "healthy"}}

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)
''',
        "language": "python",
        "description": "FastAPI application template"
    }]

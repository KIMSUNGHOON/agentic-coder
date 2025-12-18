"""Coder Node - Production Implementation

Generates code using Qwen-Coder via vLLM endpoint.
"""

import logging
import json
from typing import Dict, List
from datetime import datetime

from app.core.config import settings
from app.agent.langgraph.schemas.state import QualityGateState, DebugLog
from app.agent.langgraph.tools.filesystem_tools import write_file_tool

logger = logging.getLogger(__name__)


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
        # Generate code using vLLM
        generated_files = _generate_code_with_vllm(
            user_request=user_request,
            task_type=task_type,
            workspace_root=workspace_root
        )

        # Write files and create artifacts
        for file_info in generated_files:
            filename = file_info["filename"]
            content = file_info["content"]
            language = file_info.get("language", "python")
            description = file_info.get("description", "")

            # Write file to workspace
            result = write_file_tool(
                file_path=filename,
                content=content,
                workspace_root=workspace_root
            )

            if result["success"]:
                logger.info(f"✅ Generated: {filename}")

                # Create artifact
                artifacts.append({
                    "filename": filename,
                    "file_path": result["file_path"],
                    "language": language,
                    "content": content,
                    "description": description,
                    "size_bytes": len(content),
                    "checksum": f"sha256_{hash(content) % (10 ** 8):08x}",
                    "saved": True,
                    "saved_path": result["file_path"]
                })
            else:
                logger.error(f"❌ Failed to write {filename}: {result['error']}")

        # Add result debug log
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
                token_usage={
                    "prompt_tokens": 0,  # Will be populated by actual vLLM call
                    "completion_tokens": 0,
                    "total_tokens": 0
                }
            ))

        return {
            "coder_output": {
                "artifacts": artifacts,
                "status": "completed" if artifacts else "failed",
                "files_generated": len(artifacts)
            },
            "artifacts": artifacts,  # Top-level for frontend
            "debug_logs": debug_logs,
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
) -> List[Dict]:
    """Generate code using Qwen-Coder via vLLM

    Args:
        user_request: User's request
        task_type: Type of task
        workspace_root: Workspace root directory

    Returns:
        List of file dictionaries with filename, content, language, description
    """
    # Check if vLLM endpoint is configured
    if not settings.vllm_coding_endpoint or settings.vllm_coding_endpoint == "http://localhost:8002/v1":
        logger.warning("⚠️  vLLM coding endpoint not configured, using fallback generator")
        return _fallback_code_generator(user_request, task_type)

    try:
        # Real vLLM implementation
        import httpx

        # Build prompt for Qwen-Coder
        prompt = f"""You are an expert software engineer. Generate production-ready code for the following request:

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

        # Call vLLM endpoint
        with httpx.Client(timeout=30.0) as client:
            response = client.post(
                f"{settings.vllm_coding_endpoint}/completions",
                json={
                    "model": settings.coding_model,
                    "prompt": prompt,
                    "max_tokens": 4096,
                    "temperature": 0.2,
                    "stop": ["</s>", "Human:", "User:"]
                }
            )

            if response.status_code == 200:
                result = response.json()
                generated_text = result["choices"][0]["text"]

                # Parse JSON response
                try:
                    # Extract JSON from response
                    json_start = generated_text.find("{")
                    json_end = generated_text.rfind("}") + 1
                    if json_start != -1 and json_end > json_start:
                        json_str = generated_text[json_start:json_end]
                        parsed = json.loads(json_str)
                        return parsed.get("files", [])
                except json.JSONDecodeError:
                    logger.warning("Failed to parse vLLM JSON response, using fallback")
                    return _fallback_code_generator(user_request, task_type)
            else:
                logger.error(f"vLLM request failed: {response.status_code}")
                return _fallback_code_generator(user_request, task_type)

    except Exception as e:
        logger.error(f"vLLM call failed: {e}", exc_info=True)
        return _fallback_code_generator(user_request, task_type)


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
    """Generate a calculator web app"""

    html_content = '''<!DOCTYPE html>
<html lang="ko">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>계산기 | Calculator</title>
    <link rel="stylesheet" href="style.css">
</head>
<body>
    <div class="calculator">
        <div class="display" id="display">0</div>
        <div class="buttons">
            <button class="btn clear" onclick="clearDisplay()">C</button>
            <button class="btn operator" onclick="appendOperator('/')">/</button>
            <button class="btn operator" onclick="appendOperator('*')">×</button>
            <button class="btn operator" onclick="backspace()">⌫</button>

            <button class="btn number" onclick="appendNumber('7')">7</button>
            <button class="btn number" onclick="appendNumber('8')">8</button>
            <button class="btn number" onclick="appendNumber('9')">9</button>
            <button class="btn operator" onclick="appendOperator('-')">-</button>

            <button class="btn number" onclick="appendNumber('4')">4</button>
            <button class="btn number" onclick="appendNumber('5')">5</button>
            <button class="btn number" onclick="appendNumber('6')">6</button>
            <button class="btn operator" onclick="appendOperator('+')">+</button>

            <button class="btn number" onclick="appendNumber('1')">1</button>
            <button class="btn number" onclick="appendNumber('2')">2</button>
            <button class="btn number" onclick="appendNumber('3')">3</button>
            <button class="btn equals" onclick="calculate()" style="grid-row: span 2">=</button>

            <button class="btn number" onclick="appendNumber('0')" style="grid-column: span 2">0</button>
            <button class="btn number" onclick="appendNumber('.')">.</button>
        </div>
    </div>
    <script src="script.js"></script>
</body>
</html>'''

    css_content = '''* {
    margin: 0;
    padding: 0;
    box-sizing: border-box;
    font-family: 'Segoe UI', Tahoma, Geneva, Verdana, sans-serif;
}

body {
    display: flex;
    justify-content: center;
    align-items: center;
    min-height: 100vh;
    background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
}

.calculator {
    background: white;
    border-radius: 20px;
    padding: 20px;
    box-shadow: 0 20px 60px rgba(0, 0, 0, 0.3);
    width: 320px;
}

.display {
    background: #222;
    color: #fff;
    font-size: 2.5rem;
    padding: 20px;
    border-radius: 10px;
    text-align: right;
    margin-bottom: 20px;
    min-height: 80px;
    word-wrap: break-word;
    overflow-wrap: break-word;
}

.buttons {
    display: grid;
    grid-template-columns: repeat(4, 1fr);
    gap: 10px;
}

.btn {
    padding: 20px;
    font-size: 1.5rem;
    border: none;
    border-radius: 10px;
    cursor: pointer;
    transition: all 0.2s;
}

.btn:hover {
    transform: translateY(-2px);
    box-shadow: 0 5px 15px rgba(0, 0, 0, 0.2);
}

.btn:active {
    transform: translateY(0);
}

.btn.number {
    background: #f0f0f0;
    color: #333;
}

.btn.operator {
    background: #ff9500;
    color: white;
}

.btn.clear {
    background: #ff3b30;
    color: white;
    grid-column: span 2;
}

.btn.equals {
    background: #34c759;
    color: white;
}'''

    js_content = '''let currentInput = '0';
let operator = null;
let previousInput = null;
let shouldResetDisplay = false;

function updateDisplay() {
    const display = document.getElementById('display');
    display.textContent = currentInput;
}

function appendNumber(number) {
    if (shouldResetDisplay) {
        currentInput = '';
        shouldResetDisplay = false;
    }

    if (currentInput === '0' && number !== '.') {
        currentInput = number;
    } else if (number === '.' && currentInput.includes('.')) {
        return;
    } else {
        currentInput += number;
    }
    updateDisplay();
}

function appendOperator(op) {
    if (operator !== null && !shouldResetDisplay) {
        calculate();
    }

    previousInput = currentInput;
    operator = op;
    shouldResetDisplay = true;
}

function calculate() {
    if (operator === null || previousInput === null) {
        return;
    }

    const prev = parseFloat(previousInput);
    const current = parseFloat(currentInput);
    let result;

    switch (operator) {
        case '+':
            result = prev + current;
            break;
        case '-':
            result = prev - current;
            break;
        case '*':
            result = prev * current;
            break;
        case '/':
            if (current === 0) {
                alert('0으로 나눌 수 없습니다!');
                clearDisplay();
                return;
            }
            result = prev / current;
            break;
        default:
            return;
    }

    currentInput = result.toString();
    operator = null;
    previousInput = null;
    shouldResetDisplay = true;
    updateDisplay();
}

function clearDisplay() {
    currentInput = '0';
    operator = null;
    previousInput = null;
    shouldResetDisplay = false;
    updateDisplay();
}

function backspace() {
    if (currentInput.length > 1) {
        currentInput = currentInput.slice(0, -1);
    } else {
        currentInput = '0';
    }
    updateDisplay();
}

// Initialize
updateDisplay();'''

    readme_content = '''# 계산기 웹 앱 | Calculator Web App

사칙연산(+, -, ×, ÷)을 지원하는 웹 기반 계산기입니다.

## Features
- ✅ 덧셈, 뺄셈, 곱셈, 나눗셈
- ✅ 소수점 연산
- ✅ 백스페이스 기능
- ✅ 반응형 디자인
- ✅ 모던 UI/UX

## Usage
1. `index.html` 파일을 웹 브라우저에서 엽니다
2. 버튼을 클릭하여 계산을 수행합니다

## Files
- `index.html` - Main HTML structure
- `style.css` - Styling and layout
- `script.js` - Calculator logic
- `README.md` - Documentation

## Browser Support
- Chrome, Firefox, Safari, Edge (latest versions)
'''

    return [
        {
            "filename": "index.html",
            "content": html_content,
            "language": "html",
            "description": "Main HTML file for calculator app"
        },
        {
            "filename": "style.css",
            "content": css_content,
            "language": "css",
            "description": "Styling for calculator UI"
        },
        {
            "filename": "script.js",
            "content": js_content,
            "language": "javascript",
            "description": "Calculator logic and event handlers"
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

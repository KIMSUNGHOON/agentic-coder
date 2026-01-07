"""Architect Agent Node - Project Structure & Design

This agent analyzes requirements and designs:
- Project directory structure
- Module/file organization
- API schemas and endpoints
- Data models
- Technology stack decisions
- Dependency graph

Supports multiple LLM backends:
- DeepSeek-R1: Uses <think></think> tags for reasoning
- GPT-OSS: Structured prompts without special tags
- Qwen: Standard prompting
"""

import logging
import time
import json
import re
from typing import Dict, List, Any, Optional
from datetime import datetime

from app.agent.langgraph.schemas.state import QualityGateState, DebugLog
from app.core.config import settings
from app.services.http_client import LLMHttpClient

# Import LLM provider for model-agnostic calls
try:
    from shared.llm import LLMProviderFactory, TaskType
    LLM_PROVIDER_AVAILABLE = True
except ImportError:
    LLM_PROVIDER_AVAILABLE = False

logger = logging.getLogger(__name__)


# Architecture Design Prompt
ARCHITECT_SYSTEM_PROMPT = """You are an Expert Software Architect with 20+ years of experience.

Your role is to analyze requirements and design a comprehensive project structure BEFORE any code is written.

CRITICAL RESPONSIBILITIES:
1. Analyze the user's requirements thoroughly
2. Design optimal directory/file structure
3. Define module boundaries and responsibilities
4. Specify API endpoints and schemas
5. Define data models
6. Choose appropriate technology stack
7. Consider scalability, maintainability, and security

OUTPUT FORMAT (JSON):
```json
{
    "project_name": "project-name",
    "description": "Brief description",
    "tech_stack": {
        "language": "python/typescript/etc",
        "framework": "fastapi/react/etc",
        "database": "postgresql/mongodb/etc",
        "other": ["redis", "celery"]
    },
    "directory_structure": {
        "src/": {
            "description": "Main source code",
            "subdirs": {
                "api/": "API endpoints",
                "models/": "Data models",
                "services/": "Business logic",
                "utils/": "Utility functions"
            }
        },
        "tests/": "Test files",
        "docs/": "Documentation"
    },
    "files_to_create": [
        {
            "path": "src/main.py",
            "purpose": "Application entry point",
            "dependencies": ["src/api/routes.py"],
            "priority": 1
        }
    ],
    "api_endpoints": [
        {
            "method": "POST",
            "path": "/api/users",
            "description": "Create new user",
            "request_schema": {"name": "string", "email": "string"},
            "response_schema": {"id": "integer", "name": "string"}
        }
    ],
    "data_models": [
        {
            "name": "User",
            "fields": {"id": "int", "name": "str", "email": "str"},
            "relationships": []
        }
    ],
    "implementation_phases": [
        {
            "phase": 1,
            "name": "Core Setup",
            "files": ["src/main.py", "src/config.py"],
            "description": "Set up project foundation"
        },
        {
            "phase": 2,
            "name": "Data Layer",
            "files": ["src/models/user.py", "src/db/connection.py"],
            "description": "Implement data models"
        }
    ],
    "parallel_tasks": [
        {
            "group": "api_endpoints",
            "tasks": ["src/api/users.py", "src/api/auth.py"],
            "can_parallelize": true,
            "reason": "Independent API modules"
        }
    ],
    "estimated_complexity": "moderate",
    "estimated_files": 15,
    "requires_human_review": true,
    "review_reason": "Architecture decisions need validation"
}
```

IMPORTANT:
- Be thorough but practical
- Consider real-world best practices
- Identify what can be parallelized
- Flag anything that needs human review
"""

ARCHITECT_USER_PROMPT = """Analyze the following request and design a complete project architecture:

USER REQUEST:
{user_request}

WORKSPACE: {workspace_root}

SUPERVISOR ANALYSIS:
- Task Type: {task_type}
- Complexity: {complexity}
- Required Agents: {required_agents}

Please provide a comprehensive architecture design in the JSON format specified.
Think step by step about:
1. What is the user actually trying to build?
2. What are the core components needed?
3. How should files be organized?
4. What can be built in parallel?
5. What needs human review before proceeding?
"""


def architect_node(state: QualityGateState) -> Dict:
    """Architect Node: Design project structure before implementation

    This node runs AFTER supervisor but BEFORE coders.
    It creates a blueprint for the entire project.

    Args:
        state: Current workflow state

    Returns:
        State updates with architecture design
    """
    start_time = time.time()
    logger.info("🏗️ Architect Node: Designing project structure...")

    user_request = state["user_request"]
    workspace_root = state["workspace_root"]
    supervisor_analysis = state.get("supervisor_analysis", {})
    enable_debug = state.get("enable_debug", True)

    debug_logs: List[DebugLog] = []

    # Add start log
    if enable_debug:
        debug_logs.append(DebugLog(
            timestamp=datetime.utcnow().isoformat(),
            node="architect",
            agent="ArchitectAgent",
            event_type="thinking",
            content="Starting architecture design...",
            metadata={"phase": "start"},
            token_usage=None
        ))

    # Build the prompt
    prompt = ARCHITECT_USER_PROMPT.format(
        user_request=user_request,
        workspace_root=workspace_root,
        task_type=supervisor_analysis.get("task_type", "implementation"),
        complexity=supervisor_analysis.get("complexity", "moderate"),
        required_agents=supervisor_analysis.get("required_agents", [])
    )

    # Try LLM-based architecture design first
    architecture = _generate_architecture_with_llm(
        user_request,
        workspace_root,
        supervisor_analysis,
        enable_debug
    )

    # Fallback to rule-based if LLM fails or returns invalid result
    if not architecture or not architecture.get("files_to_create"):
        logger.warning("⚠️ LLM architecture generation failed, using rule-based fallback")
        architecture = _generate_architecture(user_request, workspace_root, supervisor_analysis)

    # Calculate execution time
    execution_time = time.time() - start_time

    # Add completion log
    if enable_debug:
        debug_logs.append(DebugLog(
            timestamp=datetime.utcnow().isoformat(),
            node="architect",
            agent="ArchitectAgent",
            event_type="result",
            content=f"Architecture design complete: {architecture['estimated_files']} files planned",
            metadata={
                "files_count": architecture["estimated_files"],
                "phases": len(architecture.get("implementation_phases", [])),
                "parallel_groups": len(architecture.get("parallel_tasks", [])),
                "execution_time_seconds": round(execution_time, 2)
            },
            token_usage=None
        ))

    logger.info(f"✅ Architecture Design Complete:")
    logger.info(f"   Project: {architecture['project_name']}")
    logger.info(f"   Files: {architecture['estimated_files']}")
    logger.info(f"   Phases: {len(architecture.get('implementation_phases', []))}")
    logger.info(f"   Parallel Groups: {len(architecture.get('parallel_tasks', []))}")
    logger.info(f"   Execution Time: {execution_time:.2f}s")

    return {
        "current_node": "architect",
        "architecture_design": architecture,
        "files_to_create": architecture.get("files_to_create", []),
        "implementation_phases": architecture.get("implementation_phases", []),
        "parallel_tasks": architecture.get("parallel_tasks", []),
        "requires_architecture_review": architecture.get("requires_human_review", False),
        "debug_logs": debug_logs,
        "agent_execution_times": {"architect": round(execution_time, 2)},
    }


def _get_architect_prompt(model_type: str, user_request: str, workspace_root: str, supervisor_analysis: Dict) -> str:
    """Generate model-specific architect prompt

    Args:
        model_type: Type of model (deepseek, gpt-oss, qwen, generic)
        user_request: User's request
        workspace_root: Workspace directory
        supervisor_analysis: Analysis from supervisor

    Returns:
        Formatted prompt for the model
    """
    base_context = f"""USER REQUEST:
{user_request}

WORKSPACE: {workspace_root}

SUPERVISOR ANALYSIS:
- Task Type: {supervisor_analysis.get("task_type", "implementation")}
- Complexity: {supervisor_analysis.get("complexity", "moderate")}
- Required Agents: {supervisor_analysis.get("required_agents", [])}"""

    json_schema = """{
    "project_name": "project-name",
    "description": "Brief description",
    "tech_stack": {"language": "python", "framework": "fastapi"},
    "files_to_create": [
        {"path": "src/main.py", "purpose": "Entry point", "priority": 1}
    ],
    "implementation_phases": [
        {"phase": 1, "name": "Setup", "files": ["main.py"], "description": "Project setup"}
    ],
    "estimated_complexity": "moderate",
    "estimated_files": 5,
    "requires_human_review": false
}"""

    if model_type == "deepseek":
        # DeepSeek-R1: Use <think> tags for reasoning
        return f"""You are an Expert Software Architect. Design a project structure for the following request.

<think>
1. Analyze what the user is trying to build
2. Determine appropriate technology stack
3. Plan file structure and modules
4. Identify implementation phases
5. Consider what can be parallelized
</think>

{base_context}

Provide your architecture design in JSON format:
```json
{json_schema}
```"""

    elif model_type in ("gpt-oss", "gpt"):
        # GPT-OSS: Structured prompt without special tags
        return f"""## Software Architecture Design Task

You are an Expert Software Architect with 20+ years of experience.

### Context
{base_context}

### Design Process
1. **Analyze Requirements** - What is the user building?
2. **Technology Selection** - Choose appropriate stack
3. **Structure Design** - Plan files and modules
4. **Implementation Planning** - Define phases

### Response Format
Provide your architecture design in JSON:
```json
{json_schema}
```

Design:"""

    else:
        # Generic/Qwen: Simple prompt
        return f"""You are an Expert Software Architect. Design a project structure for the following request.

{base_context}

Provide your architecture design in JSON format:
```json
{json_schema}
```

Architecture:"""


def _generate_architecture_with_llm(
    user_request: str,
    workspace_root: str,
    supervisor_analysis: Dict,
    enable_debug: bool = False
) -> Optional[Dict[str, Any]]:
    """Generate architecture using LLM

    Args:
        user_request: User's request
        workspace_root: Workspace directory
        supervisor_analysis: Analysis from supervisor
        enable_debug: Enable debug logging

    Returns:
        Architecture dict or None if LLM fails
    """
    # Get model configuration
    endpoint = settings.get_reasoning_endpoint
    model = settings.get_reasoning_model
    model_type = settings.get_reasoning_model_type

    if not endpoint:
        logger.info("📝 LLM endpoint not configured, skipping LLM architecture")
        return None

    logger.info(f"🏗️ Generating architecture with LLM ({model_type})")

    # Get model-specific prompt
    prompt = _get_architect_prompt(model_type, user_request, workspace_root, supervisor_analysis)

    # Try LLM provider first
    if LLM_PROVIDER_AVAILABLE:
        try:
            provider = LLMProviderFactory.create(
                model_type=model_type,
                endpoint=endpoint,
                model=model
            )

            response = provider.generate_sync(prompt, TaskType.REASONING)

            if response.parsed_json:
                logger.info(f"✅ LLM architecture via {model_type} adapter")
                return _validate_architecture(response.parsed_json)

            # Try to extract JSON from content
            if response.content:
                parsed = _extract_json_from_response(response.content)
                if parsed:
                    return _validate_architecture(parsed)

        except Exception as e:
            logger.warning(f"LLM provider failed: {e}, trying direct call")

    # Fallback to direct HTTP call with retry logic
    try:
        http_client = LLMHttpClient(
            timeout=120,
            max_retries=3,
            base_delay=2
        )

        result, error = http_client.post(
            url=f"{endpoint}/chat/completions",
            json={
                "model": model,
                "messages": [
                    {"role": "system", "content": ARCHITECT_SYSTEM_PROMPT},
                    {"role": "user", "content": prompt}
                ],
                "temperature": 0.3,
                "max_tokens": 4096
            }
        )

        if error:
            logger.warning(f"Direct HTTP call failed after retries: {error}")
            return None

        content = result["choices"][0].get("message", {}).get("content", "")

        if content:
            parsed = _extract_json_from_response(content)
            if parsed:
                logger.info("✅ LLM architecture via direct HTTP")
                return _validate_architecture(parsed)

    except Exception as e:
        logger.warning(f"Direct HTTP call failed: {e}")

    return None


def _extract_json_from_response(text: str) -> Optional[Dict]:
    """Extract JSON from LLM response text"""
    if not text:
        return None

    # Remove <think>...</think> tags if present
    text = re.sub(r'<think>.*?</think>', '', text, flags=re.DOTALL)

    # Try to find JSON in code blocks
    json_match = re.search(r'```json\s*(.*?)\s*```', text, re.DOTALL)
    if json_match:
        try:
            return json.loads(json_match.group(1))
        except json.JSONDecodeError:
            pass

    # Try to find raw JSON object
    json_start = text.find("{")
    json_end = text.rfind("}") + 1
    if json_start != -1 and json_end > json_start:
        try:
            return json.loads(text[json_start:json_end])
        except json.JSONDecodeError:
            pass

    return None


def _validate_architecture(arch: Dict) -> Optional[Dict]:
    """Validate and normalize architecture dict"""
    if not arch:
        return None

    # Required fields
    if not arch.get("files_to_create"):
        return None

    # Normalize files_to_create
    files = arch.get("files_to_create", [])
    normalized_files = []
    for f in files:
        if isinstance(f, dict) and f.get("path"):
            normalized_files.append({
                "path": f["path"],
                "purpose": f.get("purpose", "Implementation"),
                "priority": f.get("priority", 1)
            })
        elif isinstance(f, str):
            normalized_files.append({
                "path": f,
                "purpose": "Implementation",
                "priority": 1
            })

    if not normalized_files:
        return None

    arch["files_to_create"] = normalized_files
    arch["estimated_files"] = len(normalized_files)

    # Set defaults
    arch.setdefault("project_name", "project")
    arch.setdefault("description", "Generated project")
    arch.setdefault("tech_stack", {"language": "python", "framework": "none"})
    arch.setdefault("implementation_phases", [])
    arch.setdefault("parallel_tasks", [])
    arch.setdefault("estimated_complexity", "moderate")
    arch.setdefault("requires_human_review", False)

    return arch


def _generate_architecture(
    user_request: str,
    workspace_root: str,
    supervisor_analysis: Dict
) -> Dict[str, Any]:
    """Generate architecture based on request analysis (rule-based fallback)

    This is a rule-based fallback when LLM is unavailable.
    """
    request_lower = user_request.lower()

    # Detect project type
    if any(word in request_lower for word in ["web app", "website", "frontend"]):
        return _web_app_architecture(user_request, workspace_root)
    elif any(word in request_lower for word in ["api", "backend", "server", "rest"]):
        return _api_architecture(user_request, workspace_root)
    elif any(word in request_lower for word in ["cli", "command line", "script"]):
        return _cli_architecture(user_request, workspace_root)
    elif any(word in request_lower for word in ["library", "package", "module"]):
        return _library_architecture(user_request, workspace_root)
    else:
        return _default_architecture(user_request, workspace_root)


def _web_app_architecture(user_request: str, workspace_root: str) -> Dict[str, Any]:
    """Generate web application architecture"""
    return {
        "project_name": "web-app",
        "description": "Full-stack web application",
        "tech_stack": {
            "language": "typescript",
            "framework": "react",
            "backend": "fastapi",
            "database": "postgresql",
            "other": ["tailwindcss", "vite"]
        },
        "directory_structure": {
            "frontend/": {
                "description": "React frontend application",
                "subdirs": {
                    "src/components/": "React components",
                    "src/pages/": "Page components",
                    "src/hooks/": "Custom hooks",
                    "src/api/": "API client",
                    "src/types/": "TypeScript types"
                }
            },
            "backend/": {
                "description": "FastAPI backend",
                "subdirs": {
                    "app/api/": "API routes",
                    "app/models/": "Data models",
                    "app/services/": "Business logic",
                    "app/db/": "Database"
                }
            }
        },
        "files_to_create": [
            {"path": "backend/app/main.py", "purpose": "Backend entry", "priority": 1},
            {"path": "backend/app/api/routes.py", "purpose": "API routes", "priority": 2},
            {"path": "backend/app/models/base.py", "purpose": "Base models", "priority": 2},
            {"path": "frontend/src/App.tsx", "purpose": "React app", "priority": 1},
            {"path": "frontend/src/components/Layout.tsx", "purpose": "Layout", "priority": 2},
            {"path": "frontend/package.json", "purpose": "Dependencies", "priority": 1},
        ],
        "implementation_phases": [
            {"phase": 1, "name": "Project Setup", "files": ["package.json", "main.py"], "description": "Initialize projects"},
            {"phase": 2, "name": "Backend Core", "files": ["routes.py", "models/"], "description": "Backend API"},
            {"phase": 3, "name": "Frontend Core", "files": ["App.tsx", "components/"], "description": "Frontend UI"},
            {"phase": 4, "name": "Integration", "files": ["api/client.ts"], "description": "Connect frontend to backend"},
        ],
        "parallel_tasks": [
            {"group": "setup", "tasks": ["backend/main.py", "frontend/App.tsx"], "can_parallelize": True, "reason": "Independent projects"},
            {"group": "components", "tasks": ["Layout.tsx", "Header.tsx", "Footer.tsx"], "can_parallelize": True, "reason": "Independent components"},
        ],
        "estimated_complexity": "complex",
        "estimated_files": 15,
        "requires_human_review": True,
        "review_reason": "Full-stack architecture needs validation"
    }


def _api_architecture(user_request: str, workspace_root: str) -> Dict[str, Any]:
    """Generate API/Backend architecture"""
    return {
        "project_name": "api-server",
        "description": "RESTful API server",
        "tech_stack": {
            "language": "python",
            "framework": "fastapi",
            "database": "postgresql",
            "other": ["sqlalchemy", "pydantic", "uvicorn"]
        },
        "directory_structure": {
            "app/": {
                "description": "Main application",
                "subdirs": {
                    "api/routes/": "API endpoints",
                    "models/": "SQLAlchemy models",
                    "schemas/": "Pydantic schemas",
                    "services/": "Business logic",
                    "db/": "Database configuration"
                }
            },
            "tests/": {"description": "Test files"},
            "docs/": {"description": "API documentation"}
        },
        "files_to_create": [
            {"path": "app/main.py", "purpose": "Application entry", "priority": 1},
            {"path": "app/config.py", "purpose": "Configuration", "priority": 1},
            {"path": "app/db/database.py", "purpose": "DB connection", "priority": 2},
            {"path": "app/models/base.py", "purpose": "Base model", "priority": 2},
            {"path": "app/api/routes/__init__.py", "purpose": "Routes init", "priority": 2},
            {"path": "app/schemas/base.py", "purpose": "Base schemas", "priority": 2},
            {"path": "requirements.txt", "purpose": "Dependencies", "priority": 1},
        ],
        "implementation_phases": [
            {"phase": 1, "name": "Setup", "files": ["main.py", "config.py", "requirements.txt"], "description": "Project foundation"},
            {"phase": 2, "name": "Database", "files": ["db/database.py", "models/"], "description": "Data layer"},
            {"phase": 3, "name": "API", "files": ["api/routes/", "schemas/"], "description": "API endpoints"},
            {"phase": 4, "name": "Services", "files": ["services/"], "description": "Business logic"},
        ],
        "parallel_tasks": [
            {"group": "models", "tasks": ["models/user.py", "models/item.py"], "can_parallelize": True, "reason": "Independent models"},
            {"group": "routes", "tasks": ["routes/users.py", "routes/items.py"], "can_parallelize": True, "reason": "Independent endpoints"},
        ],
        "estimated_complexity": "moderate",
        "estimated_files": 12,
        "requires_human_review": True,
        "review_reason": "API design needs review"
    }


def _cli_architecture(user_request: str, workspace_root: str) -> Dict[str, Any]:
    """Generate CLI tool architecture"""
    return {
        "project_name": "cli-tool",
        "description": "Command-line interface tool",
        "tech_stack": {
            "language": "python",
            "framework": "click",
            "other": ["rich", "typer"]
        },
        "directory_structure": {
            "src/": {
                "description": "Source code",
                "subdirs": {
                    "commands/": "CLI commands",
                    "utils/": "Utilities"
                }
            },
            "tests/": {"description": "Tests"}
        },
        "files_to_create": [
            {"path": "src/main.py", "purpose": "Entry point", "priority": 1},
            {"path": "src/cli.py", "purpose": "CLI setup", "priority": 1},
            {"path": "src/commands/__init__.py", "purpose": "Commands", "priority": 2},
            {"path": "setup.py", "purpose": "Package setup", "priority": 1},
        ],
        "implementation_phases": [
            {"phase": 1, "name": "Setup", "files": ["main.py", "cli.py", "setup.py"], "description": "CLI foundation"},
            {"phase": 2, "name": "Commands", "files": ["commands/"], "description": "Implement commands"},
        ],
        "parallel_tasks": [
            {"group": "commands", "tasks": ["commands/init.py", "commands/run.py"], "can_parallelize": True, "reason": "Independent commands"},
        ],
        "estimated_complexity": "simple",
        "estimated_files": 6,
        "requires_human_review": False,
        "review_reason": ""
    }


def _library_architecture(user_request: str, workspace_root: str) -> Dict[str, Any]:
    """Generate library/package architecture"""
    return {
        "project_name": "python-library",
        "description": "Reusable Python library",
        "tech_stack": {
            "language": "python",
            "framework": "none",
            "other": ["pytest", "sphinx"]
        },
        "directory_structure": {
            "src/": {"description": "Library source"},
            "tests/": {"description": "Test suite"},
            "docs/": {"description": "Documentation"}
        },
        "files_to_create": [
            {"path": "src/__init__.py", "purpose": "Package init", "priority": 1},
            {"path": "src/core.py", "purpose": "Core functionality", "priority": 1},
            {"path": "tests/test_core.py", "purpose": "Core tests", "priority": 2},
            {"path": "setup.py", "purpose": "Package setup", "priority": 1},
            {"path": "README.md", "purpose": "Documentation", "priority": 3},
        ],
        "implementation_phases": [
            {"phase": 1, "name": "Setup", "files": ["setup.py", "__init__.py"], "description": "Package setup"},
            {"phase": 2, "name": "Core", "files": ["core.py"], "description": "Core implementation"},
            {"phase": 3, "name": "Tests", "files": ["tests/"], "description": "Test coverage"},
        ],
        "parallel_tasks": [],
        "estimated_complexity": "simple",
        "estimated_files": 5,
        "requires_human_review": False,
        "review_reason": ""
    }


def _default_architecture(user_request: str, workspace_root: str) -> Dict[str, Any]:
    """Default architecture for general projects"""
    return {
        "project_name": "project",
        "description": "General Python project",
        "tech_stack": {
            "language": "python",
            "framework": "none",
            "other": []
        },
        "directory_structure": {
            "src/": {"description": "Source code"},
            "tests/": {"description": "Tests"}
        },
        "files_to_create": [
            {"path": "src/main.py", "purpose": "Entry point", "priority": 1},
            {"path": "src/utils.py", "purpose": "Utilities", "priority": 2},
            {"path": "requirements.txt", "purpose": "Dependencies", "priority": 1},
        ],
        "implementation_phases": [
            {"phase": 1, "name": "Setup", "files": ["main.py", "requirements.txt"], "description": "Project setup"},
            {"phase": 2, "name": "Implementation", "files": ["src/"], "description": "Core implementation"},
        ],
        "parallel_tasks": [],
        "estimated_complexity": "simple",
        "estimated_files": 3,
        "requires_human_review": False,
        "review_reason": ""
    }

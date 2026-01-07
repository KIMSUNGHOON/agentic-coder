"""Dynamic workflow-based coding agent using LangGraph with SupervisorAgent.

Supports optional DeepAgents integration for enhanced capabilities:
- FilesystemMiddleware: Direct file read/write operations
- SubAgentMiddleware: Delegate tasks to specialized sub-agents
- TodoListMiddleware: Automatic task tracking
"""
import asyncio
import glob
import logging
import os
import re
import time
import uuid
from datetime import datetime
from typing import List, Dict, Any, AsyncGenerator, Optional, TypedDict, Annotated, Literal
from operator import add
from dataclasses import dataclass, field
from langchain_openai import ChatOpenAI
from langchain_core.messages import HumanMessage, SystemMessage
from langgraph.graph import StateGraph, START, END
from app.core.config import settings
from app.agent.base.interface import BaseWorkflow, BaseWorkflowManager
from app.agent.langchain.shared_context import SharedContext, ContextEntry

logger = logging.getLogger(__name__)

# Check for DeepAgents availability
DEEPAGENTS_AVAILABLE = False
deepagents_middleware = {}

try:
    from deepagents import create_deep_agent
    from deepagents.middleware.subagents import SubAgentMiddleware
    from deepagents.middleware.filesystem import FilesystemMiddleware
    from deepagents.backends.filesystem import FilesystemBackend
    DEEPAGENTS_AVAILABLE = True
    deepagents_middleware = {
        "FilesystemMiddleware": FilesystemMiddleware,
        "SubAgentMiddleware": SubAgentMiddleware,
        "FilesystemBackend": FilesystemBackend,
    }
    logger.info("DeepAgents v0.3.0 integration enabled for LangChain workflow")
except ImportError:
    logger.info("DeepAgents not available - using standard LangChain workflow")


# Task types that can be identified
TaskType = Literal[
    "code_generation",    # Create new code from scratch
    "bug_fix",            # Fix existing code
    "refactoring",        # Improve code structure
    "test_generation",    # Write tests
    "code_review",        # Review existing code
    "documentation",      # Write docs
    "general"             # Default fallback
]


# Workflow templates for each task type
WORKFLOW_TEMPLATES: Dict[TaskType, Dict[str, Any]] = {
    "code_generation": {
        "name": "Code Generation Workflow",
        "nodes": ["PlanningAgent", "CodingAgent", "ReviewAgent", "FixCodeAgent"],
        "flow": [
            ("START", "PlanningAgent"),
            ("PlanningAgent", "CodingAgent"),
            ("CodingAgent", "ReviewAgent"),
            ("ReviewAgent", "decision"),  # conditional
            ("FixCodeAgent", "ReviewAgent"),  # loop back
        ],
        "has_review_loop": True
    },
    "bug_fix": {
        "name": "Bug Fix Workflow",
        "nodes": ["AnalysisAgent", "DebugAgent", "FixCodeAgent", "TestAgent"],
        "flow": [
            ("START", "AnalysisAgent"),
            ("AnalysisAgent", "DebugAgent"),
            ("DebugAgent", "FixCodeAgent"),
            ("FixCodeAgent", "TestAgent"),
            ("TestAgent", "decision"),  # conditional
        ],
        "has_review_loop": True
    },
    "refactoring": {
        "name": "Refactoring Workflow",
        "nodes": ["AnalysisAgent", "RefactorAgent", "ReviewAgent", "FixCodeAgent"],
        "flow": [
            ("START", "AnalysisAgent"),
            ("AnalysisAgent", "RefactorAgent"),
            ("RefactorAgent", "ReviewAgent"),
            ("ReviewAgent", "decision"),
            ("FixCodeAgent", "ReviewAgent"),
        ],
        "has_review_loop": True
    },
    "test_generation": {
        "name": "Test Generation Workflow",
        "nodes": ["AnalysisAgent", "TestGenAgent", "ValidationAgent"],
        "flow": [
            ("START", "AnalysisAgent"),
            ("AnalysisAgent", "TestGenAgent"),
            ("TestGenAgent", "ValidationAgent"),
            ("ValidationAgent", "decision"),
        ],
        "has_review_loop": True
    },
    "code_review": {
        "name": "Code Review Workflow",
        "nodes": ["ReviewAgent", "SuggestionAgent"],
        "flow": [
            ("START", "ReviewAgent"),
            ("ReviewAgent", "SuggestionAgent"),
        ],
        "has_review_loop": False
    },
    "documentation": {
        "name": "Documentation Workflow",
        "nodes": ["AnalysisAgent", "DocGenAgent", "ReviewAgent"],
        "flow": [
            ("START", "AnalysisAgent"),
            ("AnalysisAgent", "DocGenAgent"),
            ("DocGenAgent", "ReviewAgent"),
        ],
        "has_review_loop": False
    },
    "general": {
        "name": "General Coding Workflow",
        "nodes": ["PlanningAgent", "CodingAgent", "ReviewAgent", "FixCodeAgent"],
        "flow": [
            ("START", "PlanningAgent"),
            ("PlanningAgent", "CodingAgent"),
            ("CodingAgent", "ReviewAgent"),
            ("ReviewAgent", "decision"),
            ("FixCodeAgent", "ReviewAgent"),
        ],
        "has_review_loop": True
    }
}


# State definition for LangGraph
class WorkflowState(TypedDict):
    """State maintained throughout the workflow."""
    user_request: str
    task_type: TaskType
    task_analysis: str
    plan_text: str
    checklist: List[Dict[str, Any]]
    code_text: str
    artifacts: Annotated[List[Dict[str, Any]], add]
    review_result: Dict[str, Any]
    review_iteration: int
    max_iterations: int
    current_task_idx: int
    status: str
    error: Optional[str]


def parse_checklist(text: str) -> List[Dict[str, Any]]:
    """Parse text into checklist items.

    Handles deepseek-r1 output format with <think> tags by:
    1. Stripping <think>...</think> reasoning blocks
    2. Looking for numbered lists or bullet points

    Args:
        text: Raw LLM output text

    Returns:
        List of checklist items
    """
    items = []

    # Step 1: Remove <think> tags and their content (deepseek-r1 reasoning)
    # This regex handles multi-line think blocks
    clean_text = re.sub(r'<think>.*?</think>', '', text, flags=re.DOTALL | re.IGNORECASE)

    # Also remove any orphaned opening/closing tags
    clean_text = re.sub(r'</?think>', '', clean_text, flags=re.IGNORECASE)

    # Step 2: Try to find output_format section first (more reliable)
    output_match = re.search(r'<output(?:_format)?>(.*?)</output(?:_format)?>', clean_text, re.DOTALL | re.IGNORECASE)
    if output_match:
        clean_text = output_match.group(1)

    # Step 3: Parse numbered lists and bullet points
    pattern = r'(?:^|\n)\s*(?:(\d+)[.\)]\s*|[-*]\s*)(.+?)(?=\n|$)'
    matches = re.findall(pattern, clean_text)

    for i, (num, task) in enumerate(matches, 1):
        task = task.strip()
        # Filter out markdown headers, empty lines, and template placeholders
        if task and not task.startswith('#') and '[' not in task[:5]:
            items.append({
                "id": int(num) if num else i,
                "task": task,
                "completed": False,
                "artifacts": []
            })

    # Fallback: If no items found, try alternative patterns
    if not items:
        # Try parsing lines that look like tasks (sentences starting with verbs)
        lines = clean_text.strip().split('\n')
        for i, line in enumerate(lines, 1):
            line = line.strip()
            # Skip empty lines and headers
            if not line or line.startswith('#') or line.startswith('<'):
                continue
            # Accept lines that look like task descriptions
            if len(line) > 10 and not line.startswith('```'):
                items.append({
                    "id": i,
                    "task": line,
                    "completed": False,
                    "artifacts": []
                })

    logger.debug(f"parse_checklist: found {len(items)} items from text length {len(text)}")
    return items


def parse_code_blocks(text: str) -> List[Dict[str, Any]]:
    """Extract code blocks from text with unique filename generation.

    Handles deepseek-r1 output format with <think> tags.
    """
    artifacts = []

    # Remove <think> tags and their content first (deepseek-r1 reasoning)
    clean_text = re.sub(r'<think>.*?</think>', '', text, flags=re.DOTALL | re.IGNORECASE)
    clean_text = re.sub(r'</?think>', '', clean_text, flags=re.IGNORECASE)

    pattern = r'```(\w+)?(?:\s+(\S+))?\n(.*?)```'
    matches = re.findall(pattern, clean_text, re.DOTALL)

    extensions = {
        "python": "py", "javascript": "js", "typescript": "ts",
        "java": "java", "go": "go", "rust": "rs", "cpp": "cpp",
        "c": "c", "html": "html", "css": "css", "json": "json",
        "yaml": "yaml", "sql": "sql", "bash": "sh", "shell": "sh"
    }

    # Track used filenames to generate unique names
    used_filenames = set()
    file_counter = {}  # Track counter per extension

    for lang, filename, content in matches:
        lang = lang or "text"
        content = content.strip()

        # Try to extract filename from first comment line if not provided
        if not filename and content:
            first_line = content.split('\n')[0] if content else ""
            # Match patterns like: # filename.py, // filename.js, /* filename.css */
            comment_match = re.match(r'^(?:#|//|/\*)\s*(?:file(?:name)?:\s*)?(\S+\.\w+)', first_line, re.IGNORECASE)
            if comment_match:
                filename = comment_match.group(1)

        # Generate unique filename if still not provided
        if not filename:
            ext = extensions.get(lang.lower(), "txt")
            base_name = f"code_{lang.lower()}" if lang != "text" else "code"

            # Initialize counter for this extension
            if ext not in file_counter:
                file_counter[ext] = 0
            file_counter[ext] += 1

            # Generate unique name
            if file_counter[ext] == 1:
                filename = f"{base_name}.{ext}"
            else:
                filename = f"{base_name}_{file_counter[ext]}.{ext}"

        # Ensure filename is unique even if explicitly provided
        original_filename = filename
        counter = 1
        while filename in used_filenames:
            name, ext = original_filename.rsplit('.', 1) if '.' in original_filename else (original_filename, 'txt')
            filename = f"{name}_{counter}.{ext}"
            counter += 1

        used_filenames.add(filename)

        artifacts.append({
            "type": "artifact",
            "language": lang,
            "filename": filename,
            "content": content
        })

    return artifacts


def parse_review(text: str) -> Dict[str, Any]:
    """Parse review text into structured format with line-specific issues.

    Handles deepseek-r1 output format with <think> tags.

    Expected format:
    ANALYSIS: [summary]
    ISSUES:
    - File: [filename]
    - Line: [line number]
    - Severity: [critical/warning/info]
    - Issue: [problem]
    - Fix: [suggestion]
    SUGGESTIONS:
    - File: [filename]
    - Line: [line]
    - Suggestion: [improvement]
    STATUS: APPROVED or NEEDS_REVISION
    """
    issues = []
    suggestions = []
    approved = False
    analysis = ""

    # Remove <think> tags and their content first (deepseek-r1 reasoning)
    clean_text = re.sub(r'<think>.*?</think>', '', text, flags=re.DOTALL | re.IGNORECASE)
    clean_text = re.sub(r'</?think>', '', clean_text, flags=re.IGNORECASE)

    # Parse ANALYSIS
    analysis_match = re.search(r'ANALYSIS:\s*(.+?)(?=\n\n|ISSUES:|$)', clean_text, re.IGNORECASE | re.DOTALL)
    if analysis_match:
        analysis = analysis_match.group(1).strip()

    # Parse STATUS field explicitly - this takes precedence
    status_match = re.search(r'STATUS:\s*(APPROVED|NEEDS_REVISION)', clean_text, re.IGNORECASE)
    if status_match:
        approved = status_match.group(1).upper() == "APPROVED"
    else:
        # Fallback: if no explicit status, check for approval keywords
        if re.search(r'\b(?:lgtm|looks good|no issues found)\b', clean_text, re.IGNORECASE):
            approved = True

    # Parse ISSUES section with structured format
    issues_section = re.search(r'ISSUES:\s*(.*?)(?=SUGGESTIONS:|STATUS:|```|$)', clean_text, re.IGNORECASE | re.DOTALL)
    if issues_section:
        issues_text = issues_section.group(1).strip()

        # Try to parse structured issues (File/Line/Severity/Issue/Fix format)
        issue_blocks = re.split(r'\n\s*\n|\n(?=-\s*File:)', issues_text)
        for block in issue_blocks:
            if not block.strip():
                continue

            issue_obj = {}
            # Parse each field
            file_match = re.search(r'-?\s*File:\s*(.+?)(?:\n|$)', block, re.IGNORECASE)
            line_match = re.search(r'-?\s*Line:\s*(.+?)(?:\n|$)', block, re.IGNORECASE)
            severity_match = re.search(r'-?\s*Severity:\s*(.+?)(?:\n|$)', block, re.IGNORECASE)
            issue_match = re.search(r'-?\s*Issue:\s*(.+?)(?:\n-|$)', block, re.IGNORECASE | re.DOTALL)
            fix_match = re.search(r'-?\s*Fix:\s*(.+?)(?:\n\n|$)', block, re.IGNORECASE | re.DOTALL)

            if file_match:
                issue_obj["file"] = file_match.group(1).strip()
            if line_match:
                issue_obj["line"] = line_match.group(1).strip()
            if severity_match:
                issue_obj["severity"] = severity_match.group(1).strip().lower()
            if issue_match:
                issue_obj["issue"] = issue_match.group(1).strip()
            if fix_match:
                issue_obj["fix"] = fix_match.group(1).strip()

            # If we got at least an issue description, add it
            if issue_obj.get("issue"):
                issues.append(issue_obj)
            elif block.strip() and not any(k in block.lower() for k in ['file:', 'line:', 'severity:']):
                # Fallback: simple text issue (old format compatibility)
                simple_match = re.search(r'[-*]\s*(?:Issue:\s*)?(.+)', block, re.IGNORECASE)
                if simple_match:
                    issues.append({"issue": simple_match.group(1).strip(), "severity": "warning"})

    # Parse SUGGESTIONS section with structured format
    suggestions_section = re.search(r'SUGGESTIONS:\s*(.*?)(?=STATUS:|ISSUES:|```|$)', clean_text, re.IGNORECASE | re.DOTALL)
    if suggestions_section:
        suggestions_text = suggestions_section.group(1).strip()

        # Try to parse structured suggestions
        suggestion_blocks = re.split(r'\n\s*\n|\n(?=-\s*File:)', suggestions_text)
        for block in suggestion_blocks:
            if not block.strip():
                continue

            suggestion_obj = {}
            file_match = re.search(r'-?\s*File:\s*(.+?)(?:\n|$)', block, re.IGNORECASE)
            line_match = re.search(r'-?\s*Line:\s*(.+?)(?:\n|$)', block, re.IGNORECASE)
            suggestion_match = re.search(r'-?\s*Suggestion:\s*(.+?)(?:\n\n|$)', block, re.IGNORECASE | re.DOTALL)

            if file_match:
                suggestion_obj["file"] = file_match.group(1).strip()
            if line_match:
                suggestion_obj["line"] = line_match.group(1).strip()
            if suggestion_match:
                suggestion_obj["suggestion"] = suggestion_match.group(1).strip()

            if suggestion_obj.get("suggestion"):
                suggestions.append(suggestion_obj)
            elif block.strip() and not any(k in block.lower() for k in ['file:', 'line:']):
                # Fallback: simple text suggestion
                simple_match = re.search(r'[-*]\s*(?:Suggest(?:ion)?:\s*)?(.+)', block, re.IGNORECASE)
                if simple_match:
                    suggestions.append({"suggestion": simple_match.group(1).strip()})

    # If issues exist but STATUS says APPROVED, check severity
    if issues and approved:
        for issue in issues:
            severity = issue.get("severity", "warning") if isinstance(issue, dict) else "warning"
            if severity in ["critical", "error"]:
                approved = False
                break

    return {
        "analysis": analysis,
        "issues": issues,
        "suggestions": suggestions,
        "approved": approved,
        "corrected_artifacts": parse_code_blocks(clean_text)
    }


def parse_task_type(text: str) -> TaskType:
    """Parse task type from supervisor analysis.

    Handles deepseek-r1 output format with <think> tags.
    First tries to find explicit TASK_TYPE: declaration,
    then falls back to keyword matching.
    """
    # Remove <think> tags and their content first (deepseek-r1 reasoning)
    clean_text = re.sub(r'<think>.*?</think>', '', text, flags=re.DOTALL | re.IGNORECASE)
    clean_text = re.sub(r'</?think>', '', clean_text, flags=re.IGNORECASE)

    # Try to find explicit TASK_TYPE declaration
    task_type_match = re.search(r'TASK_TYPE:\s*(\w+)', clean_text, re.IGNORECASE)
    if task_type_match:
        task_type_str = task_type_match.group(1).lower()
        # Validate it's a known type
        if task_type_str in ["code_generation", "bug_fix", "refactoring", "test_generation", "code_review", "documentation", "general"]:
            return task_type_str  # type: ignore
        logger.warning(f"Found TASK_TYPE but unknown value: {task_type_str}, falling back to keyword matching")

    # Fallback to keyword matching
    text_lower = clean_text.lower()

    if any(kw in text_lower for kw in ["code_generation", "create new", "implement new", "build new"]):
        return "code_generation"
    elif any(kw in text_lower for kw in ["bug_fix", "fix bug", "fix error", "debug"]):
        return "bug_fix"
    elif any(kw in text_lower for kw in ["refactor", "improve code", "optimize", "clean up"]):
        return "refactoring"
    elif any(kw in text_lower for kw in ["test_generation", "unit test", "write tests"]):
        return "test_generation"
    elif any(kw in text_lower for kw in ["code_review", "review code", "check code"]):
        return "code_review"
    elif any(kw in text_lower for kw in ["documentation", "write docs", "readme"]):
        return "documentation"
    elif any(kw in text_lower for kw in ["general", "question", "explain", "how to"]):
        return "general"
    else:
        # Default to code_generation for unknown patterns (better than general for first request)
        logger.warning(f"Could not determine task type from text, defaulting to code_generation")
        return "code_generation"


class DynamicLangGraphWorkflow(BaseWorkflow):
    """Dynamic multi-agent workflow that creates workflow based on task analysis.

    Supports optional DeepAgents middleware integration for enhanced capabilities.
    """

    def __init__(self, enable_deepagents: bool = False):
        """Initialize the dynamic workflow.

        Args:
            enable_deepagents: Whether to use DeepAgents middleware (if available)
        """
        # Initialize LLM clients
        base_reasoning_llm = ChatOpenAI(
            base_url=settings.vllm_reasoning_endpoint,
            model=settings.reasoning_model,
            temperature=0.7,
            max_tokens=2048,
            api_key="not-needed",
        )

        base_coding_llm = ChatOpenAI(
            base_url=settings.vllm_coding_endpoint,
            model=settings.coding_model,
            temperature=0.7,
            max_tokens=2048,
            api_key="not-needed",
        )

        # Try to wrap with DeepAgents if requested and available
        if enable_deepagents and DEEPAGENTS_AVAILABLE:
            try:
                # Use thread-safe singleton middleware accessor
                from app.agent.langchain.deepagent_workflow import get_or_create_middleware

                middleware_list = []

                # SubAgentMiddleware only (FilesystemMiddleware causes issues)
                SubAgentMiddleware = deepagents_middleware.get("SubAgentMiddleware")
                if SubAgentMiddleware:
                    subagent_middleware = get_or_create_middleware(
                        "subagent",
                        lambda: SubAgentMiddleware(
                            default_model=base_reasoning_llm,
                            default_tools=[]
                        )
                    )
                    if subagent_middleware:
                        middleware_list.append(subagent_middleware)

                # Wrap LLMs with DeepAgents
                if middleware_list:
                    self.reasoning_llm = create_deep_agent(
                        model=base_reasoning_llm,
                        tools=[],
                        middleware=middleware_list,
                        system_prompt="You are a reasoning agent for task analysis."
                    )
                    self.coding_llm = create_deep_agent(
                        model=base_coding_llm,
                        tools=[],
                        middleware=middleware_list,
                        system_prompt="You are a coding agent for implementation."
                    )
                    logger.info("✅ Standard workflow using DeepAgents with SubAgentMiddleware")
                else:
                    self.reasoning_llm = base_reasoning_llm
                    self.coding_llm = base_coding_llm
                    logger.info("⚠️  DeepAgents enabled but no middleware available")
            except Exception as e:
                logger.warning(f"Failed to enable DeepAgents, using standard LLMs: {e}")
                self.reasoning_llm = base_reasoning_llm
                self.coding_llm = base_coding_llm
        else:
            self.reasoning_llm = base_reasoning_llm
            self.coding_llm = base_coding_llm
            if enable_deepagents:
                logger.info("DeepAgents requested but not available, using standard LLMs")

        # Shared context for parallel agent execution
        self.shared_context: Optional[SharedContext] = None

        # Parallel execution settings (loaded from config)
        # RTX 3090 + Ollama: 1-2, H100 + vLLM: 25
        self.max_parallel_agents = getattr(settings, 'max_parallel_agents', 2)
        self.enable_parallel_coding = getattr(settings, 'enable_parallel_coding', True)
        self.adaptive_parallelism = True  # Adjust based on task count

        logger.info(f"Parallel execution: max_agents={self.max_parallel_agents}, enabled={self.enable_parallel_coding}")

        # Supervisor prompt for task analysis with context awareness
        self.supervisor_prompt = """You are a Supervisor Agent that analyzes user requests and determines the best workflow.

**CRITICAL: Check if the task requires NEW work or is a QUESTION about EXISTING work**

<context_awareness>
BEFORE determining the workflow, check:
1. Is there EXISTING CODE in the context?
2. Is the user asking about HOW TO USE/RUN existing code?
3. Is the user asking for EXPLANATIONS/DOCUMENTATION?
4. Is the user requesting MODIFICATIONS to existing code?

If the user is asking about existing code (execution, usage, explanation):
- Set TASK_TYPE to "general" (this will use chat mode, not workflow)
- Do NOT regenerate code that already exists
- The question can be answered without creating new files
</context_awareness>

<task>
Analyze the user's request considering ANY existing code/context and determine:
1. TASK_TYPE: One of:
   - code_generation: Create NEW code/project from scratch
   - bug_fix: Fix errors in existing code
   - refactoring: Improve existing code structure
   - test_generation: Create tests for existing code
   - code_review: Review existing code
   - documentation: Create docs for existing code
   - general: Questions, explanations, usage instructions (NO new code needed)

2. COMPLEXITY: [simple, medium, complex]
3. REQUIREMENTS: List key requirements
4. RECOMMENDED_AGENTS: Which agents should be used
5. NEEDS_NEW_FILES: true/false (Does this require creating new files?)
</task>

<examples>
Example 1 - Question about existing code:
User: "How do I run this program?"
Context: [existing Python files]
→ TASK_TYPE: general
→ NEEDS_NEW_FILES: false
→ ANALYSIS: User asking about execution, not requesting new code

Example 2 - New code request:
User: "Create a web scraper"
Context: [empty or unrelated]
→ TASK_TYPE: code_generation
→ NEEDS_NEW_FILES: true
→ ANALYSIS: User requesting new functionality

Example 3 - Modification request:
User: "Add error handling to the auth function"
Context: [existing auth.py]
→ TASK_TYPE: bug_fix
→ NEEDS_NEW_FILES: false
→ ANALYSIS: Modifying existing code
</examples>

<response_format>
TASK_TYPE: [type]
COMPLEXITY: [level]
NEEDS_NEW_FILES: [true/false]
REQUIREMENTS:
- [requirement 1]
- [requirement 2]
RECOMMENDED_AGENTS: [agent1, agent2, ...]
ANALYSIS: [brief analysis considering existing context]
</response_format>

Be precise and concise. **Avoid regenerating code that already exists.**"""

        # Agent-specific prompts
        self.prompts = {
            "PlanningAgent": """Analyze request and create implementation checklist.

<think>
Break down the request into atomic, sequential steps.
Consider dependencies between tasks.
Order by implementation sequence.
</think>

<output_format>
1. [Task description]
2. [Task description]
</output_format>

Rules:
- One task per line
- Clear, actionable steps
- No explanations, only the numbered list""",

            "CodingAgent": """Implement the specified task.

<response_format>
THOUGHTS: [brief analysis]

```language filename.ext
// complete code
```
</response_format>

<rules>
- Focus ONLY on current task
- One code block per file
- Include filename after language
- Write complete, runnable code
</rules>""",

            "ReviewAgent": """Review code and provide detailed, line-specific feedback.

<response_format>
ANALYSIS: [brief overall review summary]

ISSUES:
For each issue, specify:
- File: [filename]
- Line: [line number or range, e.g., "15" or "15-20"]
- Severity: [critical/warning/info]
- Issue: [detailed description of the problem]
- Fix: [suggested fix]

Example:
- File: calculator.py
- Line: 25
- Severity: critical
- Issue: Division by zero not handled
- Fix: Add check for zero divisor before division

SUGGESTIONS:
- File: [filename]
- Line: [line number]
- Suggestion: [improvement recommendation]

STATUS: [APPROVED or NEEDS_REVISION]

If NEEDS_REVISION, provide corrected code:
```language filename.ext
// corrected complete code with fixes applied
```
</response_format>

<rules>
- Be specific about line numbers
- Critical issues = bugs, errors, security problems (MUST fix)
- Warnings = code smells, potential issues (SHOULD fix)
- Info = style, best practices (COULD improve)
- Only set STATUS: APPROVED if no critical/warning issues exist
</rules>""",

            "FixCodeAgent": """Fix the code based on review feedback.

<review_issues>
{issues}
</review_issues>

<review_suggestions>
{suggestions}
</review_suggestions>

<response_format>
FIXES_APPLIED: [list what you fixed]

```language filename.ext
// corrected complete code
```
</response_format>""",

            "AnalysisAgent": """Analyze the code/problem and provide insights.

<response_format>
ANALYSIS:
- [finding 1]
- [finding 2]

ROOT_CAUSE: [if applicable]
RECOMMENDATION: [suggested approach]
</response_format>""",

            "DebugAgent": """Debug the code and identify issues.

<response_format>
BUGS_FOUND:
- [bug 1]: [description]
- [bug 2]: [description]

DEBUG_STEPS:
1. [step]
2. [step]
</response_format>""",

            "RefactorAgent": """Refactor the code for better quality.

<response_format>
REFACTORING_PLAN:
- [change 1]
- [change 2]

```language filename.ext
// refactored code
```
</response_format>""",

            "TestGenAgent": """Generate tests for the code.

<response_format>
TEST_STRATEGY: [approach]

```language test_filename.ext
// test code
```
</response_format>""",

            "ValidationAgent": """Validate the tests and coverage.

<response_format>
VALIDATION_RESULT:
- Coverage: [percentage]
- Edge cases: [covered/missing]

STATUS: [PASS or NEEDS_MORE_TESTS]
</response_format>""",

            "DocGenAgent": """Generate documentation for the code.

<response_format>
```markdown README.md
// documentation
```
</response_format>""",

            "SuggestionAgent": """Provide improvement suggestions.

<response_format>
SUGGESTIONS:
1. [suggestion with explanation]
2. [suggestion with explanation]

PRIORITY: [high/medium/low for each]
</response_format>"""
        }

        logger.info("DynamicLangGraphWorkflow initialized")

    async def _analyze_task(self, user_request: str) -> tuple[TaskType, str, Dict[str, Any]]:
        """Use Supervisor to analyze the task and determine workflow type."""
        messages = [
            SystemMessage(content=self.supervisor_prompt),
            HumanMessage(content=user_request)
        ]

        response = await self.reasoning_llm.ainvoke(messages)
        analysis_text = response.content

        # Parse task type from response
        task_type = parse_task_type(analysis_text)

        # Get workflow template
        template = WORKFLOW_TEMPLATES[task_type]

        return task_type, analysis_text, template

    async def execute(
        self,
        user_request: str,
        context: Optional[Any] = None
    ) -> str:
        """Execute the dynamic workflow."""
        logger.info(f"Executing dynamic workflow for: {user_request[:100]}...")

        # First, analyze the task
        task_type, analysis, template = await self._analyze_task(user_request)
        logger.info(f"Task type determined: {task_type}, using workflow: {template['name']}")

        # For now, use the streaming version's logic
        # This is a simplified non-streaming version
        return f"Task analyzed as: {task_type}\nWorkflow: {template['name']}"

    async def execute_stream(
        self,
        user_request: str,
        context: Optional[Any] = None
    ) -> AsyncGenerator[Dict[str, Any], None]:
        """Execute the dynamic workflow with streaming updates."""
        logger.info(f"Streaming dynamic workflow for: {user_request[:100]}...")
        workflow_id = str(uuid.uuid4())[:8]
        max_iterations = settings.max_review_iterations

        # Extract workspace from context
        workspace = None
        if context and isinstance(context, dict):
            workspace = context.get("workspace")

        try:
            # ========================================
            # Phase 0: Workspace Exploration (if workspace exists)
            # ========================================
            if workspace and os.path.exists(workspace):
                import glob
                # Check for existing code files
                code_patterns = ["*.py", "*.js", "*.ts", "*.tsx", "*.java", "*.cpp", "*.go", "*.rs"]
                existing_files = []
                for pattern in code_patterns:
                    existing_files.extend(glob.glob(os.path.join(workspace, "**", pattern), recursive=True))

                if existing_files:
                    # Found existing code - notify user
                    file_list = [os.path.basename(f) for f in existing_files[:10]]  # First 10 files
                    more_count = len(existing_files) - 10

                    yield {
                        "agent": "WorkspaceExplorer",
                        "type": "workspace_info",
                        "status": "info",
                        "message": f"📁 Found {len(existing_files)} existing file(s) in workspace",
                        "workspace": workspace,
                        "file_count": len(existing_files),
                        "files": file_list + ([f"... and {more_count} more"] if more_count > 0 else []),
                        "timestamp": datetime.now().isoformat()
                    }
                else:
                    yield {
                        "agent": "WorkspaceExplorer",
                        "type": "workspace_info",
                        "status": "info",
                        "message": "📂 Workspace is empty - starting fresh project",
                        "workspace": workspace,
                        "file_count": 0,
                        "timestamp": datetime.now().isoformat()
                    }

            # ========================================
            # Phase 1: Supervisor analyzes the task
            # ========================================
            yield {
                "agent": "SupervisorAgent",
                "type": "agent_spawn",
                "status": "running",
                "message": "Spawning SupervisorAgent for task analysis",
                "agent_spawn": {
                    "agent_id": f"supervisor-{uuid.uuid4().hex[:6]}",
                    "agent_type": "SupervisorAgent",
                    "parent_agent": None,
                    "spawn_reason": "Analyze user request and determine optimal workflow",
                    "timestamp": datetime.now().isoformat()
                }
            }

            yield {
                "agent": "SupervisorAgent",
                "type": "thinking",
                "status": "running",
                "message": "Analyzing task to determine optimal workflow..."
            }

            # Analyze the task
            messages = [
                SystemMessage(content=self.supervisor_prompt),
                HumanMessage(content=user_request)
            ]

            start_time = time.time()
            analysis_text = ""
            async for chunk in self.reasoning_llm.astream(messages):
                if chunk.content:
                    analysis_text += chunk.content
            analysis_latency_ms = int((time.time() - start_time) * 1000)

            # Parse task type
            task_type = parse_task_type(analysis_text)
            template = WORKFLOW_TEMPLATES[task_type]

            yield {
                "agent": "SupervisorAgent",
                "type": "completed",
                "status": "completed",
                "message": f"Task identified as: {task_type}",
                "task_analysis": {
                    "task_type": task_type,
                    "workflow_name": template["name"],
                    "agents": template["nodes"],
                    "has_review_loop": template["has_review_loop"]
                },
                "prompt_info": {
                    "system_prompt": self.supervisor_prompt,
                    "user_prompt": user_request,
                    "output": analysis_text,
                    "model": settings.reasoning_model,
                    "latency_ms": analysis_latency_ms
                }
            }

            # ========================================
            # Phase 2: Create dynamic workflow
            # ========================================
            # Build workflow edges with conditions
            edges = []
            for i, (from_node, to_node) in enumerate(template["flow"]):
                edge = {"from": from_node, "to": to_node}
                if to_node == "decision":
                    edge["to"] = "Decision"
                    edge["condition"] = "review result"
                edges.append(edge)

            # Add decision edges if has review loop
            if template["has_review_loop"]:
                edges.append({"from": "Decision", "to": "FixCodeAgent", "condition": "not approved"})
                edges.append({"from": "Decision", "to": "END", "condition": "approved"})

            yield {
                "agent": "Orchestrator",
                "type": "workflow_created",
                "status": "running",
                "message": f"Created {template['name']} (max {max_iterations} iterations)",
                "workflow_info": {
                    "workflow_id": workflow_id,
                    "workflow_type": template["name"],
                    "task_type": task_type,
                    "nodes": template["nodes"],
                    "edges": edges,
                    "current_node": template["nodes"][0] if template["nodes"] else "END",
                    "max_iterations": max_iterations,
                    "dynamically_created": True
                }
            }

            # ========================================
            # Phase 3: Execute the workflow
            # ========================================

            # IMPORTANT: "general" task type = simple question/explanation, NO workflow needed
            if task_type == "general":
                # This is a question about existing code or general inquiry
                # Use chat mode instead of workflow
                yield {
                    "agent": "ChatAssistant",
                    "type": "thinking",
                    "status": "running",
                    "message": "This looks like a question about existing code. Using chat mode instead of workflow..."
                }

                # Simple chat response using coding LLM
                messages = [
                    SystemMessage(content="You are a helpful assistant. Answer the user's question about their code or project. Be concise and practical."),
                    HumanMessage(content=user_request)
                ]

                response_text = ""
                async for chunk in self.coding_llm.astream(messages):
                    if chunk.content:
                        response_text += chunk.content

                yield {
                    "agent": "ChatAssistant",
                    "type": "completed",
                    "status": "completed",
                    "message": response_text,
                    "content": response_text
                }

                # Mark workflow as complete
                yield {
                    "agent": "Orchestrator",
                    "type": "completed",
                    "status": "completed",
                    "message": "Response completed (no new files generated)"
                }
                return

            # For code_generation, bug_fix, refactoring - use standard flow
            if task_type in ["code_generation", "bug_fix", "refactoring"]:
                # Execute standard Planning -> Coding -> Review loop
                async for update in self._execute_coding_workflow(
                    user_request, task_type, template, workflow_id, max_iterations
                ):
                    yield update
            elif task_type == "test_generation":
                async for update in self._execute_test_workflow(
                    user_request, template, workflow_id, max_iterations
                ):
                    yield update
            elif task_type == "code_review":
                async for update in self._execute_review_only_workflow(
                    user_request, template, workflow_id
                ):
                    yield update
            elif task_type == "documentation":
                async for update in self._execute_doc_workflow(
                    user_request, template, workflow_id
                ):
                    yield update
            else:
                # Fallback to general coding workflow
                async for update in self._execute_coding_workflow(
                    user_request, task_type, template, workflow_id, max_iterations
                ):
                    yield update

        except Exception as e:
            logger.error(f"Error in dynamic workflow: {e}")
            yield {
                "agent": "Workflow",
                "type": "error",
                "status": "error",
                "message": str(e)
            }
            raise

    async def _execute_coding_workflow(
        self,
        user_request: str,
        task_type: TaskType,
        template: Dict[str, Any],
        workflow_id: str,
        max_iterations: int
    ) -> AsyncGenerator[Dict[str, Any], None]:
        """Execute the standard coding workflow (Planning -> Coding -> Review -> Fix loop)."""

        # Helper to build workflow_info with current node
        def build_workflow_info(current_node: str) -> Dict[str, Any]:
            return {
                "workflow_id": workflow_id,
                "workflow_type": template["name"],
                "task_type": task_type,
                "nodes": template["nodes"],
                "current_node": current_node,
                "max_iterations": max_iterations,
                "dynamically_created": True
            }

        # Step 1: Planning
        planning_agent = template["nodes"][0]  # Usually PlanningAgent or AnalysisAgent
        yield {
            "agent": planning_agent,
            "type": "agent_spawn",
            "status": "running",
            "message": f"Spawning {planning_agent}",
            "workflow_info": build_workflow_info(planning_agent),
            "agent_spawn": {
                "agent_id": f"{planning_agent.lower()}-{uuid.uuid4().hex[:6]}",
                "agent_type": planning_agent,
                "parent_agent": "Orchestrator",
                "spawn_reason": "Create implementation plan",
                "timestamp": datetime.now().isoformat()
            }
        }

        yield {
            "agent": planning_agent,
            "type": "thinking",
            "status": "running",
            "message": "Creating implementation plan..."
        }

        planning_prompt = self.prompts.get(planning_agent, self.prompts["PlanningAgent"])
        messages = [
            SystemMessage(content=planning_prompt),
            HumanMessage(content=user_request)
        ]

        start_time = time.time()
        plan_text = ""
        chunk_count = 0
        async for chunk in self.reasoning_llm.astream(messages):
            if chunk.content:
                plan_text += chunk.content
                chunk_count += 1
                # 실시간 스트리밍: 5 청크마다 계획 진행 상황 전송 (더 자주 업데이트)
                if chunk_count % 5 == 0:
                    lines = plan_text.split('\n')
                    # 마지막 10줄 미리보기 (더 많은 컨텍스트)
                    preview = '\n'.join(lines[-10:] if len(lines) > 10 else lines)
                    yield {
                        "agent": planning_agent,
                        "type": "streaming",
                        "status": "running",
                        "message": f"계획 수립 중... ({len(plan_text):,} 자)",
                        "streaming_content": preview
                    }
        latency_ms = int((time.time() - start_time) * 1000)

        checklist = parse_checklist(plan_text)

        yield {
            "agent": planning_agent,
            "type": "completed",
            "status": "completed",
            "items": checklist,
            "prompt_info": {
                "system_prompt": planning_prompt,
                "user_prompt": user_request,
                "output": plan_text,
                "model": settings.reasoning_model,
                "latency_ms": latency_ms
            }
        }

        # Step 2: Coding (with parallel execution option)
        coding_agent = "CodingAgent" if "CodingAgent" in template["nodes"] else "RefactorAgent"
        coding_prompt = self.prompts.get(coding_agent, self.prompts["CodingAgent"])

        # Decide whether to use parallel execution
        use_parallel = (
            self.enable_parallel_coding and
            len(checklist) >= 2  # Only parallelize if multiple tasks
        )

        if use_parallel:
            # Parallel execution mode
            yield {
                "agent": "Orchestrator",
                "type": "mode_selection",
                "status": "running",
                "message": f"Using PARALLEL coding mode for {len(checklist)} tasks",
                "execution_mode": "parallel",
                "parallel_config": {
                    "max_parallel_agents": self.max_parallel_agents,
                    "total_tasks": len(checklist)
                }
            }

            # Execute tasks in parallel
            all_artifacts = []
            code_text = ""

            async for update in self._execute_parallel_coding(
                checklist=checklist,
                user_request=user_request,
                plan_text=plan_text,
                coding_prompt=coding_prompt,
                build_workflow_info=build_workflow_info
            ):
                yield update

                # Capture final artifacts and code_text from parallel execution
                if update.get("type") == "parallel_complete":
                    all_artifacts = update.get("artifacts", [])
                    code_text = update.get("code_text", "")

        else:
            # Sequential execution mode (original behavior)
            yield {
                "agent": coding_agent,
                "type": "agent_spawn",
                "status": "running",
                "message": f"Spawning {coding_agent}",
                "workflow_info": build_workflow_info(coding_agent),
                "agent_spawn": {
                    "agent_id": f"{coding_agent.lower()}-{uuid.uuid4().hex[:6]}",
                    "agent_type": coding_agent,
                    "parent_agent": "Orchestrator",
                    "spawn_reason": f"Implement {len(checklist)} tasks",
                    "timestamp": datetime.now().isoformat()
                },
                "execution_mode": "sequential"
            }

            all_artifacts = []
            code_text = ""
            existing_code = ""

            for idx, task_item in enumerate(checklist):
                task_num = idx + 1
                task_description = task_item["task"]

                yield {
                    "agent": coding_agent,
                    "type": "thinking",
                    "status": "running",
                    "message": f"Task {task_num}/{len(checklist)}: {task_description}",
                    "checklist": checklist
                }

                context_parts = [f"Original request: {user_request}"]
                context_parts.append(f"\nFull plan:\n{plan_text}")
                if existing_code:
                    context_parts.append(f"\nCode so far:\n{existing_code}")
                context_parts.append(f"\nCurrent task ({task_num}/{len(checklist)}): {task_description}")

                user_prompt = "\n".join(context_parts)
                messages = [
                    SystemMessage(content=coding_prompt),
                    HumanMessage(content=user_prompt)
                ]

                start_time = time.time()
                task_code = ""
                chunk_count = 0
                async for chunk in self.coding_llm.astream(messages):
                    if chunk.content:
                        task_code += chunk.content
                        chunk_count += 1
                        # 실시간 스트리밍: 3 청크마다 프론트엔드에 업데이트 전송 (더 자주 업데이트)
                        if chunk_count % 3 == 0:
                            # 마지막 12줄 미리보기 (더 많은 컨텍스트)
                            lines = task_code.split('\n')
                            preview = '\n'.join(lines[-12:] if len(lines) > 12 else lines)
                            yield {
                                "agent": coding_agent,
                                "type": "streaming",
                                "status": "running",
                                "message": f"코드 생성 중... ({len(task_code):,} 자)",
                                "streaming_content": preview
                            }
                task_latency_ms = int((time.time() - start_time) * 1000)

                code_text += task_code + "\n"
                task_artifacts = parse_code_blocks(task_code)
                all_artifacts.extend(task_artifacts)

                for artifact in task_artifacts:
                    existing_code += f"\n\n```{artifact['language']} {artifact['filename']}\n{artifact['content']}\n```"
                    yield {
                        "agent": coding_agent,
                        "type": "artifact",
                        "status": "running",
                        "message": f"Created {artifact['filename']}",
                        "artifact": artifact
                    }

                checklist[idx]["completed"] = True
                checklist[idx]["artifacts"] = [a["filename"] for a in task_artifacts]

                yield {
                    "agent": coding_agent,
                    "type": "task_completed",
                    "status": "running",
                    "message": f"Task {task_num}/{len(checklist)} completed",
                    "task_result": {"task_num": task_num, "task": task_description, "artifacts": task_artifacts},
                    "checklist": checklist,
                    "prompt_info": {
                        "system_prompt": coding_prompt,
                        "user_prompt": user_prompt,
                        "output": task_code,
                        "model": settings.coding_model,
                        "latency_ms": task_latency_ms
                    }
                }

            yield {
                "agent": coding_agent,
                "type": "completed",
                "status": "completed",
                "artifacts": all_artifacts,
                "checklist": checklist
            }

        # Step 3: Review Loop (if has_review_loop)
        if template["has_review_loop"]:
            review_iteration = 0
            approved = False
            review_result = {"approved": False, "issues": [], "suggestions": [], "corrected_artifacts": [], "analysis": ""}  # Initialize
            review_prompt = self.prompts["ReviewAgent"]
            fix_prompt_template = self.prompts["FixCodeAgent"]

            while not approved and review_iteration < max_iterations:
                review_iteration += 1

                # Determine if we should use parallel review
                # Use parallel review for multiple files (3+ files to make it worthwhile)
                num_artifacts = len(all_artifacts)
                use_parallel_review = self.enable_parallel_coding and num_artifacts >= 3

                if use_parallel_review:
                    # Parallel review for multiple files
                    yield {
                        "agent": "Orchestrator",
                        "type": "mode_selection",
                        "status": "running",
                        "message": f"Using PARALLEL review mode for {num_artifacts} files",
                        "execution_mode": "parallel",
                        "parallel_config": {
                            "max_parallel_agents": self.max_parallel_agents * 2,
                            "total_files": num_artifacts
                        }
                    }

                    # Execute parallel review
                    review_completed = False
                    # Keep default review_result from line 1220 initialization
                    # Will be updated when parallel review completes
                    async for update in self._execute_parallel_review(
                        artifacts=all_artifacts,
                        user_request=user_request,
                        review_prompt=review_prompt,
                        review_iteration=review_iteration,
                        max_iterations=max_iterations
                    ):
                        # Check if this is the completion update
                        if update.get("type") == "completed" and update.get("agent") == "ReviewAgent":
                            # Extract review result from parallel review
                            approved = update.get("approved", False)
                            review_result = {
                                "approved": approved,
                                "issues": update.get("issues", []),
                                "suggestions": update.get("suggestions", []),
                                "corrected_artifacts": update.get("corrected_artifacts", []),
                                "analysis": update.get("analysis", "")
                            }
                            review_completed = True

                        yield update

                    if not review_completed:
                        # Fallback if parallel review didn't complete properly
                        approved = False
                        review_result = {
                            "approved": False,
                            "issues": [],
                            "suggestions": [],
                            "corrected_artifacts": [],
                            "analysis": "Review did not complete properly"
                        }

                else:
                    # Sequential review for single file or few files
                    yield {
                        "agent": "ReviewAgent",
                        "type": "agent_spawn",
                        "status": "running",
                        "message": f"Spawning ReviewAgent (iteration {review_iteration}/{max_iterations})",
                        "workflow_info": build_workflow_info("ReviewAgent"),
                        "agent_spawn": {
                            "agent_id": f"review-{uuid.uuid4().hex[:6]}",
                            "agent_type": "ReviewAgent",
                            "parent_agent": "Orchestrator",
                            "spawn_reason": f"Review iteration {review_iteration}",
                            "timestamp": datetime.now().isoformat()
                        },
                        "iteration_info": {"current": review_iteration, "max": max_iterations}
                    }

                    yield {
                        "agent": "ReviewAgent",
                        "type": "thinking",
                        "status": "running",
                        "message": f"Reviewing code (iteration {review_iteration}/{max_iterations})..."
                    }

                    review_user_prompt = f"Review this code:\n\n{code_text}"
                    messages = [
                        SystemMessage(content=review_prompt),
                        HumanMessage(content=review_user_prompt)
                    ]

                    start_time = time.time()
                    review_text = ""
                    chunk_count = 0
                    async for chunk in self.coding_llm.astream(messages):
                        if chunk.content:
                            review_text += chunk.content
                            chunk_count += 1
                            # 실시간 스트리밍: 3 청크마다 리뷰 진행 상황 전송 (더 자주 업데이트)
                            if chunk_count % 3 == 0:
                                lines = review_text.split('\n')
                                preview = '\n'.join(lines[-10:] if len(lines) > 10 else lines)
                                yield {
                                    "agent": "ReviewAgent",
                                    "type": "streaming",
                                    "status": "running",
                                    "message": f"코드 검토 중... ({len(review_text):,} 자)",
                                    "streaming_content": preview
                                }
                    review_latency_ms = int((time.time() - start_time) * 1000)

                    review_result = parse_review(review_text)
                    approved = review_result["approved"]

                    yield {
                        "agent": "ReviewAgent",
                        "type": "completed",
                        "status": "completed",
                        "analysis": review_result.get("analysis", ""),
                        "issues": review_result["issues"],
                        "suggestions": review_result["suggestions"],
                        "approved": approved,
                        "corrected_artifacts": review_result["corrected_artifacts"],
                        "prompt_info": {
                            "system_prompt": review_prompt,
                            "user_prompt": review_user_prompt,
                            "output": review_text,
                            "model": settings.coding_model,
                            "latency_ms": review_latency_ms
                        },
                        "iteration_info": {"current": review_iteration, "max": max_iterations}
                    }

                # Decision
                yield {
                    "agent": "Orchestrator",
                    "type": "decision",
                    "status": "running",
                    "message": f"Decision: {'APPROVED' if approved else 'NEEDS_REVISION'}",
                    "workflow_info": build_workflow_info("Decision"),
                    "decision": {
                        "approved": approved,
                        "iteration": review_iteration,
                        "max_iterations": max_iterations,
                        "action": "end" if approved else ("fix_code" if review_iteration < max_iterations else "end_max_iterations")
                    }
                }

                # Fix if needed
                if not approved and review_iteration < max_iterations:
                    yield {
                        "agent": "FixCodeAgent",
                        "type": "agent_spawn",
                        "status": "running",
                        "message": f"Spawning FixCodeAgent",
                        "workflow_info": build_workflow_info("FixCodeAgent"),
                        "agent_spawn": {
                            "agent_id": f"fix-{uuid.uuid4().hex[:6]}",
                            "agent_type": "FixCodeAgent",
                            "parent_agent": "Orchestrator",
                            "spawn_reason": f"Fix {len(review_result['issues'])} issues",
                            "timestamp": datetime.now().isoformat()
                        }
                    }

                    yield {
                        "agent": "FixCodeAgent",
                        "type": "thinking",
                        "status": "running",
                        "message": f"Fixing {len(review_result['issues'])} issues..."
                    }

                    # Format issues for FixCodeAgent (handle both old and new format)
                    def format_issue(issue):
                        if isinstance(issue, dict):
                            parts = []
                            if issue.get("file"):
                                parts.append(f"File: {issue['file']}")
                            if issue.get("line"):
                                parts.append(f"Line: {issue['line']}")
                            if issue.get("severity"):
                                parts.append(f"Severity: {issue['severity']}")
                            if issue.get("issue"):
                                parts.append(f"Issue: {issue['issue']}")
                            if issue.get("fix"):
                                parts.append(f"Suggested Fix: {issue['fix']}")
                            return "\n  ".join(parts)
                        return str(issue)

                    def format_suggestion(suggestion):
                        if isinstance(suggestion, dict):
                            parts = []
                            if suggestion.get("file"):
                                parts.append(f"File: {suggestion['file']}")
                            if suggestion.get("line"):
                                parts.append(f"Line: {suggestion['line']}")
                            if suggestion.get("suggestion"):
                                parts.append(f"Suggestion: {suggestion['suggestion']}")
                            return "\n  ".join(parts)
                        return str(suggestion)

                    issues_text = "\n".join(f"- {format_issue(i)}" for i in review_result["issues"]) or "None"
                    suggestions_text = "\n".join(f"- {format_suggestion(s)}" for s in review_result["suggestions"]) or "None"

                    fix_prompt = fix_prompt_template.format(
                        issues=issues_text,
                        suggestions=suggestions_text
                    )

                    fix_user_prompt = f"Code to fix:\n\n{code_text}"
                    messages = [
                        SystemMessage(content=fix_prompt),
                        HumanMessage(content=fix_user_prompt)
                    ]

                    start_time = time.time()
                    fixed_code = ""
                    chunk_count = 0
                    async for chunk in self.coding_llm.astream(messages):
                        if chunk.content:
                            fixed_code += chunk.content
                            chunk_count += 1
                            # 실시간 스트리밍: 3 청크마다 수정 진행 상황 전송 (더 자주 업데이트)
                            if chunk_count % 3 == 0:
                                lines = fixed_code.split('\n')
                                preview = '\n'.join(lines[-12:] if len(lines) > 12 else lines)
                                yield {
                                    "agent": "FixCodeAgent",
                                    "type": "streaming",
                                    "status": "running",
                                    "message": f"코드 수정 중... ({len(fixed_code):,} 자)",
                                    "streaming_content": preview
                                }
                    fix_latency_ms = int((time.time() - start_time) * 1000)

                    code_text = fixed_code
                    fixed_artifacts = parse_code_blocks(fixed_code)
                    all_artifacts = fixed_artifacts

                    for artifact in fixed_artifacts:
                        yield {
                            "agent": "FixCodeAgent",
                            "type": "artifact",
                            "status": "running",
                            "message": f"Fixed: {artifact['filename']}",
                            "artifact": artifact
                        }

                    yield {
                        "agent": "FixCodeAgent",
                        "type": "completed",
                        "status": "completed",
                        "artifacts": fixed_artifacts,
                        "prompt_info": {
                            "system_prompt": fix_prompt,
                            "user_prompt": fix_user_prompt,
                            "output": fixed_code,
                            "model": settings.coding_model,
                            "latency_ms": fix_latency_ms
                        }
                    }

            # Final result summary
            final_status = "approved" if approved else "max_iterations_reached"
            final_message = (
                f"Code review passed. Generated {len(all_artifacts)} file(s)."
                if approved else
                f"Review loop ended after {review_iteration} iterations. Generated {len(all_artifacts)} file(s)."
            )

            # Orchestrator completion
            yield {
                "agent": "Orchestrator",
                "type": "completed",
                "status": "completed",
                "message": final_message,
                "final_result": {
                    "success": approved,
                    "message": final_message,
                    "tasks_completed": sum(1 for item in checklist if item["completed"]),
                    "total_tasks": len(checklist),
                    "artifacts": [{"filename": a["filename"], "language": a["language"]} for a in all_artifacts],
                    "review_status": "approved" if approved else "needs_revision",
                    "review_iterations": review_iteration
                },
                "artifacts": all_artifacts,
                "workflow_info": {
                    "workflow_id": workflow_id,
                    "workflow_type": template["name"],
                    "task_type": task_type,
                    "nodes": template["nodes"],
                    "current_node": "END",
                    "final_status": final_status,
                    "dynamically_created": True
                }
            }
        else:
            # No review loop - just finish
            final_message = f"Completed. Generated {len(all_artifacts)} file(s)."

            yield {
                "agent": "Orchestrator",
                "type": "completed",
                "status": "completed",
                "message": final_message,
                "final_result": {
                    "success": True,
                    "message": final_message,
                    "tasks_completed": len(checklist),
                    "total_tasks": len(checklist),
                    "artifacts": [{"filename": a["filename"], "language": a["language"]} for a in all_artifacts],
                    "review_status": "skipped",
                    "review_iterations": 0
                },
                "artifacts": all_artifacts,
                "workflow_info": {
                    "workflow_id": workflow_id,
                    "workflow_type": template["name"],
                    "task_type": task_type,
                    "nodes": template["nodes"],
                    "current_node": "END",
                    "dynamically_created": True
                }
            }

    async def _execute_single_coding_task(
        self,
        task_idx: int,
        task_item: Dict[str, Any],
        user_request: str,
        plan_text: str,
        coding_prompt: str,
        agent_id: str,
        progress_callback: Optional[callable] = None
    ) -> Dict[str, Any]:
        """Execute a single coding task - used for parallel execution with streaming preview."""
        task_description = task_item["task"]

        context_parts = [f"Original request: {user_request}"]
        context_parts.append(f"\nFull plan:\n{plan_text}")
        context_parts.append(f"\nCurrent task: {task_description}")
        context_parts.append("\nGenerate ONLY the code for this specific task. Include filename in the code block.")

        user_prompt = "\n".join(context_parts)
        messages = [
            SystemMessage(content=coding_prompt),
            HumanMessage(content=user_prompt)
        ]

        start_time = time.time()
        task_code = ""
        chunk_count = 0

        async for chunk in self.coding_llm.astream(messages):
            if chunk.content:
                task_code += chunk.content
                chunk_count += 1

                # Send streaming preview every 10 chunks (to avoid spam)
                if progress_callback and chunk_count % 10 == 0:
                    # Extract last 6 lines for preview
                    lines = task_code.split('\n')
                    preview_lines = lines[-6:] if len(lines) >= 6 else lines
                    preview = '\n'.join(preview_lines)

                    # Try to extract filename from current code
                    filename = "generating..."
                    if '```' in task_code:
                        # Look for filename after ```
                        for line in lines:
                            if line.strip().startswith('```') and len(line.strip()) > 3:
                                parts = line.strip()[3:].split()
                                filename = parts[0] if parts else "code"
                                break

                    await progress_callback({
                        "task_idx": task_idx,
                        "agent_id": agent_id,
                        "filename": filename,
                        "preview": preview,
                        "total_chars": len(task_code)
                    })

        latency_ms = int((time.time() - start_time) * 1000)

        artifacts = parse_code_blocks(task_code)

        # Store in shared context
        if self.shared_context:
            await self.shared_context.set(
                agent_id=agent_id,
                agent_type="CodingAgent",
                key=f"task_{task_idx}_result",
                value={
                    "code": task_code,
                    "artifacts": artifacts,
                    "task": task_description
                },
                description=f"Code generated for task: {task_description[:50]}..."
            )

        return {
            "task_idx": task_idx,
            "task_description": task_description,
            "code": task_code,
            "artifacts": artifacts,
            "agent_id": agent_id,
            "latency_ms": latency_ms,
            "prompt_info": {
                "system_prompt": coding_prompt,
                "user_prompt": user_prompt,
                "output": task_code,
                "model": settings.coding_model,
                "latency_ms": latency_ms
            }
        }

    def calculate_optimal_parallel(self, task_count: int) -> int:
        """
        Calculate optimal parallelism based on H100 GPU capabilities.

        H100 96GB NVL with vLLM can handle 20-30 concurrent requests efficiently
        due to continuous batching and large VRAM capacity.

        Args:
            task_count: Number of tasks to process

        Returns:
            Optimal number of parallel workers
        """
        H100_MAX_PARALLEL = 25  # Optimized for H100 + vLLM

        if task_count <= 10:
            # Small projects: Run all tasks in parallel
            return task_count
        elif task_count <= H100_MAX_PARALLEL:
            # Medium projects: Use all available parallelism
            return task_count
        else:
            # Large projects: Cap at H100 optimal parallelism
            return H100_MAX_PARALLEL

    def _group_similar_tasks(self, checklist: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """Group similar tasks together for better parallel execution.

        Groups tasks by:
        1. Same file type/extension
        2. Same directory/module
        3. Similar task description keywords
        """
        from collections import defaultdict
        import re

        # Extract file info from task descriptions
        def get_task_info(task: Dict[str, Any]) -> tuple:
            task_desc = task.get("task", "")

            # Try to extract filename from task description
            # Look for patterns like: "filename.py", "path/to/file.ext"
            file_match = re.search(r'[\w/.-]+\.\w+', task_desc)
            if file_match:
                filename = file_match.group(0)
                ext = filename.split('.')[-1] if '.' in filename else ''
                directory = '/'.join(filename.split('/')[:-1]) if '/' in filename else ''
                return (ext, directory)

            # Fallback: use keywords from description
            keywords = set(word.lower() for word in re.findall(r'\b\w+\b', task_desc)
                          if len(word) > 3)
            return ('', '', frozenset(keywords))

        # Group tasks by similarity
        groups = defaultdict(list)
        for task in checklist:
            key = get_task_info(task)
            groups[key].append(task)

        # Flatten groups back to list, keeping similar tasks together
        grouped_checklist = []
        for group in groups.values():
            grouped_checklist.extend(group)

        return grouped_checklist

    async def _execute_parallel_coding(
        self,
        checklist: List[Dict[str, Any]],
        user_request: str,
        plan_text: str,
        coding_prompt: str,
        build_workflow_info: callable
    ) -> AsyncGenerator[Dict[str, Any], None]:
        """Execute multiple coding tasks in parallel with optimized grouping."""

        # Initialize shared context for this workflow
        self.shared_context = SharedContext()

        # Group similar tasks together for better cache locality
        grouped_checklist = self._group_similar_tasks(checklist)

        # Dynamically adjust parallelism based on task count and H100 capabilities
        if self.adaptive_parallelism:
            # Use H100-optimized calculation for optimal parallelism
            optimal_parallel = self.calculate_optimal_parallel(len(grouped_checklist))
        else:
            optimal_parallel = self.max_parallel_agents

        # Notify parallel execution start
        yield {
            "agent": "Orchestrator",
            "type": "parallel_start",
            "status": "running",
            "message": f"Starting parallel execution with up to {optimal_parallel} concurrent agents",
            "parallel_info": {
                "total_tasks": len(grouped_checklist),
                "max_parallel": optimal_parallel
            }
        }

        all_artifacts = []
        all_results = []

        # Spawn single unified CodingAgent for all tasks (shown once in UI)
        yield {
            "agent": "CodingAgent",
            "agent_label": f"Implementing {len(grouped_checklist)} Tasks",
            "task_description": f"Creating {len(grouped_checklist)} files in parallel (up to {optimal_parallel} concurrent)",
            "type": "agent_spawn",
            "status": "running",
            "message": f"Starting parallel implementation with {optimal_parallel} concurrent agents",
            "workflow_info": build_workflow_info("CodingAgent"),
            "agent_spawn": {
                "agent_id": f"coding-unified-{uuid.uuid4().hex[:6]}",
                "agent_type": "CodingAgent",
                "parent_agent": "Orchestrator",
                "spawn_reason": f"Implement {len(grouped_checklist)} tasks in parallel (grouped by similarity)",
                "timestamp": datetime.now().isoformat()
            }
        }

        # Process tasks in batches using optimal parallelism
        batch_count = (len(grouped_checklist) + optimal_parallel - 1) // optimal_parallel
        for batch_start in range(0, len(grouped_checklist), optimal_parallel):
            batch_end = min(batch_start + optimal_parallel, len(grouped_checklist))

            # Create tasks for this batch with progress callback
            pending_tasks = {}  # task_object -> (idx, task_item)
            preview_queue = asyncio.Queue()

            # Progress callback to send streaming previews
            async def on_progress(preview_data):
                await preview_queue.put(preview_data)

            for idx in range(batch_start, batch_end):
                agent_id = f"coding-{uuid.uuid4().hex[:6]}"
                task_item = grouped_checklist[idx]

                # Start task and immediately notify user
                task_coro = self._execute_single_coding_task(
                    task_idx=idx,
                    task_item=task_item,
                    user_request=user_request,
                    plan_text=plan_text,
                    coding_prompt=coding_prompt,
                    agent_id=agent_id,
                    progress_callback=on_progress
                )
                task_obj = asyncio.create_task(task_coro)
                pending_tasks[task_obj] = (idx, task_item, agent_id)

                # Immediately show what task is starting
                yield {
                    "agent": "CodingAgent",
                    "agent_label": f"Implementing {len(grouped_checklist)} Tasks",
                    "type": "thinking",
                    "status": "running",
                    "message": f"🔄 Starting: {task_item['task'][:80]}...",
                    "task_info": {
                        "task_num": idx + 1,
                        "total_tasks": len(grouped_checklist),
                        "description": task_item['task']
                    }
                }

            # Execute batch with real-time streaming (process as tasks complete)
            current_batch = batch_start // optimal_parallel + 1
            yield {
                "agent": "CodingAgent",
                "agent_label": f"Implementing {len(grouped_checklist)} Tasks",
                "type": "thinking",
                "status": "running",
                "message": f"Batch {current_batch}/{batch_count}: Processing {len(pending_tasks)} tasks in parallel ({batch_start + 1}-{batch_end} of {len(grouped_checklist)})",
                "batch_info": {
                    "batch_num": current_batch,
                    "total_batches": batch_count,
                    "tasks": list(range(batch_start + 1, batch_end + 1)),
                    "parallel_count": len(pending_tasks)
                }
            }

            # Process tasks as they complete (streaming results)
            completed_count = 0
            while pending_tasks:
                # Check for streaming previews first
                while not preview_queue.empty():
                    preview_data = await preview_queue.get()
                    yield {
                        "agent": "CodingAgent",
                        "agent_label": f"Implementing {len(grouped_checklist)} Tasks",
                        "type": "code_preview",
                        "status": "running",
                        "message": f"📝 Generating {preview_data['filename']}...",
                        "code_preview": {
                            "task_idx": preview_data['task_idx'],
                            "agent_id": preview_data['agent_id'],
                            "filename": preview_data['filename'],
                            "preview": preview_data['preview'],
                            "chars": preview_data['total_chars']
                        }
                    }

                # Wait for any task to complete (with timeout to check previews)
                done, pending = await asyncio.wait(
                    pending_tasks.keys(),
                    timeout=0.5,  # Check every 0.5s for previews
                    return_when=asyncio.FIRST_COMPLETED
                )

                if not done:
                    continue  # No task completed, check previews again

                # Process completed tasks immediately
                for task_obj in done:
                    idx, task_item, agent_id = pending_tasks.pop(task_obj)
                    completed_count += 1

                    try:
                        result = await task_obj
                        task_idx = result["task_idx"]
                        all_results.append(result)

                        # Show completion status
                        artifact_names = [a['filename'] for a in result["artifacts"]]
                        yield {
                            "agent": "CodingAgent",
                            "agent_label": f"Implementing {len(grouped_checklist)} Tasks",
                            "type": "thinking",
                            "status": "running",
                            "message": f"✓ Completed ({completed_count}/{len(pending_tasks) + completed_count}): {', '.join(artifact_names)}",
                            "task_info": {
                                "task_num": idx + 1,
                                "completed": True,
                                "artifacts": artifact_names
                            }
                        }

                        # Emit artifacts immediately
                        for artifact in result["artifacts"]:
                            all_artifacts.append(artifact)
                            yield {
                                "agent": "CodingAgent",
                                "agent_label": f"Implementing {len(grouped_checklist)} Tasks",
                                "type": "artifact",
                                "status": "running",
                                "message": f"Created {artifact['filename']}",
                                "artifact": artifact,
                                "parallel_agent_id": agent_id
                            }

                        # Mark task completed
                        grouped_checklist[task_idx]["completed"] = True
                        grouped_checklist[task_idx]["artifacts"] = artifact_names

                    except Exception as e:
                        logger.error(f"Parallel task failed: {e}")
                        yield {
                            "agent": "CodingAgent",
                            "agent_label": f"Implementing {len(grouped_checklist)} Tasks",
                            "type": "error",
                            "status": "error",
                            "message": f"❌ Failed ({completed_count}/{len(pending_tasks) + completed_count}): {task_item['task'][:50]}... - {str(e)}"
                        }

        # Emit shared context summary
        yield {
            "agent": "Orchestrator",
            "type": "shared_context",
            "status": "running",
            "message": "Shared context summary",
            "shared_context": {
                "entries": self.shared_context.get_entries_summary(),
                "access_log": self.shared_context.get_access_log()
            }
        }

        # Combine all code for review
        code_text = ""
        for result in sorted(all_results, key=lambda x: x["task_idx"]):
            code_text += result["code"] + "\n"

        # Mark CodingAgent as completed
        yield {
            "agent": "CodingAgent",
            "agent_label": f"Implementing {len(grouped_checklist)} Tasks",
            "type": "completed",
            "status": "completed",
            "message": f"Successfully created {len(all_artifacts)} files using parallel execution (up to {optimal_parallel} concurrent)",
            "artifacts": all_artifacts,
            "checklist": grouped_checklist
        }

        yield {
            "agent": "Orchestrator",
            "type": "parallel_complete",
            "status": "completed",
            "message": f"Parallel execution completed with {optimal_parallel} concurrent agents. Generated {len(all_artifacts)} files.",
            "parallel_summary": {
                "total_tasks": len(grouped_checklist),
                "completed_tasks": len(all_results),
                "total_artifacts": len(all_artifacts),
                "agents_used": 1,  # Now using unified agent
                "max_concurrent": optimal_parallel,
                "batch_count": batch_count
            },
            "artifacts": all_artifacts,
            "checklist": grouped_checklist,
            "code_text": code_text
        }

    async def _execute_single_review_task(
        self,
        file_idx: int,
        artifact: Dict[str, Any],
        user_request: str,
        review_prompt: str,
        agent_id: str
    ) -> Dict[str, Any]:
        """Execute a single file review task - used for parallel execution."""
        filename = artifact["filename"]
        content = artifact["content"]
        language = artifact.get("language", "text")

        user_prompt = f"""Review this file:

Filename: {filename}
Language: {language}

User Request: {user_request}

Code:
```{language}
{content}
```

Provide detailed review focusing on this specific file."""

        messages = [
            SystemMessage(content=review_prompt),
            HumanMessage(content=user_prompt)
        ]

        start_time = time.time()
        review_text = ""

        async for chunk in self.coding_llm.astream(messages):
            if chunk.content:
                review_text += chunk.content

        latency_ms = int((time.time() - start_time) * 1000)

        # Parse review result for this file
        review_result = parse_review(review_text)

        return {
            "file_idx": file_idx,
            "filename": filename,
            "review_text": review_text,
            "review_result": review_result,
            "latency_ms": latency_ms
        }

    async def _execute_parallel_review(
        self,
        artifacts: List[Dict[str, Any]],
        user_request: str,
        review_prompt: str,
        review_iteration: int,
        max_iterations: int
    ) -> AsyncGenerator[Dict[str, Any], None]:
        """Execute code review in parallel for multiple files.

        Similar to parallel coding, but for reviewing multiple artifacts.
        Leverages H100 GPU optimization for better throughput.
        """
        if not artifacts or len(artifacts) == 0:
            return

        # Determine optimal parallelism for review
        # Reviews are typically faster than coding, so we can use higher parallelism
        num_files = len(artifacts)
        if self.adaptive_parallelism:
            # For reviews, we can safely use up to 2x the coding parallelism
            optimal_parallel = min(num_files, self.max_parallel_agents * 2)
        else:
            optimal_parallel = min(num_files, self.max_parallel_agents)

        # Notify parallel review start
        yield {
            "agent": "Orchestrator",
            "type": "parallel_review_start",
            "status": "running",
            "message": f"Starting parallel review of {num_files} files with up to {optimal_parallel} concurrent review agents",
            "parallel_info": {
                "total_files": num_files,
                "max_parallel": optimal_parallel,
                "review_iteration": review_iteration
            }
        }

        # Spawn unified ReviewAgent for all files (shown once in UI)
        yield {
            "agent": "ReviewAgent",
            "agent_label": f"Reviewing {num_files} Files",
            "task_description": f"Reviewing {num_files} files in parallel (up to {optimal_parallel} concurrent)",
            "type": "agent_spawn",
            "status": "running",
            "message": f"Starting parallel review with {optimal_parallel} concurrent agents (iteration {review_iteration}/{max_iterations})",
            "workflow_info": {
                "current_agent": "ReviewAgent",
                "total_agents": num_files,
                "completed_agents": 0
            },
            "agent_spawn": {
                "agent_id": f"review-unified-{uuid.uuid4().hex[:6]}",
                "agent_type": "ReviewAgent",
                "parent_agent": "Orchestrator",
                "spawn_reason": f"Review {num_files} files in parallel",
                "timestamp": datetime.now().isoformat()
            },
            "iteration_info": {"current": review_iteration, "max": max_iterations}
        }

        all_reviews = []

        # Process files in batches
        batch_count = (num_files + optimal_parallel - 1) // optimal_parallel
        for batch_start in range(0, num_files, optimal_parallel):
            batch_end = min(batch_start + optimal_parallel, num_files)

            # Create review tasks for this batch
            pending_tasks = {}  # task_object -> (idx, artifact, agent_id)

            for idx in range(batch_start, batch_end):
                agent_id = f"review-{uuid.uuid4().hex[:6]}"
                artifact = artifacts[idx]

                # Start review task
                task_coro = self._execute_single_review_task(
                    file_idx=idx,
                    artifact=artifact,
                    user_request=user_request,
                    review_prompt=review_prompt,
                    agent_id=agent_id
                )
                task_obj = asyncio.create_task(task_coro)
                pending_tasks[task_obj] = (idx, artifact, agent_id)

                # Immediately show what file is being reviewed
                yield {
                    "agent": "ReviewAgent",
                    "agent_label": f"Reviewing {num_files} Files",
                    "type": "thinking",
                    "status": "running",
                    "message": f"🔄 Starting review: {artifact['filename']}",
                    "file_info": {
                        "file_num": idx + 1,
                        "total_files": num_files,
                        "filename": artifact['filename']
                    }
                }

            # Show batch info
            current_batch = batch_start // optimal_parallel + 1
            yield {
                "agent": "ReviewAgent",
                "agent_label": f"Reviewing {num_files} Files",
                "type": "thinking",
                "status": "running",
                "message": f"Batch {current_batch}/{batch_count}: Reviewing {len(pending_tasks)} files in parallel ({batch_start + 1}-{batch_end} of {num_files})",
                "batch_info": {
                    "batch_num": current_batch,
                    "total_batches": batch_count,
                    "files": list(range(batch_start + 1, batch_end + 1)),
                    "parallel_count": len(pending_tasks)
                }
            }

            # Process reviews as they complete
            completed_count = 0
            while pending_tasks:
                done, pending = await asyncio.wait(
                    pending_tasks.keys(),
                    return_when=asyncio.FIRST_COMPLETED
                )

                # Process completed reviews immediately
                for task_obj in done:
                    idx, artifact, agent_id = pending_tasks.pop(task_obj)
                    completed_count += 1

                    try:
                        result = await task_obj
                        all_reviews.append(result)

                        # Show completion status
                        review_summary = result["review_result"]
                        issue_count = len(review_summary.get("issues", []))
                        severity = "✓" if issue_count == 0 else f"⚠ {issue_count} issues"

                        yield {
                            "agent": "ReviewAgent",
                            "agent_label": f"Reviewing {num_files} Files",
                            "type": "thinking",
                            "status": "running",
                            "message": f"{severity} Completed ({completed_count}/{len(pending_tasks) + completed_count}): {result['filename']}",
                            "file_info": {
                                "file_num": idx + 1,
                                "completed": True,
                                "filename": result['filename'],
                                "issue_count": issue_count
                            }
                        }

                    except Exception as e:
                        logger.error(f"Parallel review task failed: {e}")
                        yield {
                            "agent": "ReviewAgent",
                            "agent_label": f"Reviewing {num_files} Files",
                            "type": "error",
                            "status": "error",
                            "message": f"❌ Failed ({completed_count}/{len(pending_tasks) + completed_count}): {artifact['filename']} - {str(e)}"
                        }

        # Combine all reviews
        combined_issues = []
        combined_suggestions = []
        all_approved = True

        for review in sorted(all_reviews, key=lambda x: x["file_idx"]):
            result = review["review_result"]
            combined_issues.extend(result.get("issues", []))
            combined_suggestions.extend(result.get("suggestions", []))
            if not result.get("approved", False):
                all_approved = False

        # Mark ReviewAgent as completed
        total_issues = len(combined_issues)
        yield {
            "agent": "ReviewAgent",
            "agent_label": f"Reviewing {num_files} Files",
            "type": "completed",
            "status": "completed",
            "message": f"Review completed: {num_files} files reviewed in parallel, {total_issues} total issues found",
            "analysis": f"Parallel review of {num_files} files completed. Total issues: {total_issues}",
            "issues": combined_issues,
            "suggestions": combined_suggestions,
            "approved": all_approved,
            "corrected_artifacts": [],  # Parallel review doesn't auto-correct
            "prompt_info": {
                "system_prompt": review_prompt,
                "user_prompt": f"Parallel review of {num_files} files",
                "output": f"Combined review from {num_files} parallel reviewers",
                "model": settings.coding_model,
                "latency_ms": sum(r["latency_ms"] for r in all_reviews)
            },
            "parallel_review_summary": {
                "total_files": num_files,
                "completed_files": len(all_reviews),
                "total_issues": total_issues,
                "max_concurrent": optimal_parallel,
                "batch_count": batch_count
            },
            "iteration_info": {"current": review_iteration, "max": max_iterations}
        }

        yield {
            "agent": "Orchestrator",
            "type": "parallel_review_complete",
            "status": "completed",
            "message": f"Parallel review completed with {optimal_parallel} concurrent agents. Reviewed {num_files} files, found {total_issues} issues.",
            "parallel_summary": {
                "total_files": num_files,
                "completed_files": len(all_reviews),
                "total_issues": total_issues,
                "all_approved": all_approved,
                "max_concurrent": optimal_parallel,
                "batch_count": batch_count
            }
        }

    async def _execute_test_workflow(
        self,
        user_request: str,
        template: Dict[str, Any],
        workflow_id: str,
        max_iterations: int
    ) -> AsyncGenerator[Dict[str, Any], None]:
        """Execute test generation workflow."""
        # Simplified - use coding workflow structure
        async for update in self._execute_coding_workflow(
            user_request, "test_generation", template, workflow_id, max_iterations
        ):
            yield update

    async def _execute_review_only_workflow(
        self,
        user_request: str,
        template: Dict[str, Any],
        workflow_id: str
    ) -> AsyncGenerator[Dict[str, Any], None]:
        """Execute review-only workflow (no code generation)."""
        # Review agent
        yield {
            "agent": "ReviewAgent",
            "type": "agent_spawn",
            "status": "running",
            "message": "Spawning ReviewAgent",
            "agent_spawn": {
                "agent_id": f"review-{uuid.uuid4().hex[:6]}",
                "agent_type": "ReviewAgent",
                "parent_agent": "Orchestrator",
                "spawn_reason": "Review provided code",
                "timestamp": datetime.now().isoformat()
            }
        }

        yield {
            "agent": "ReviewAgent",
            "type": "thinking",
            "status": "running",
            "message": "Reviewing code..."
        }

        messages = [
            SystemMessage(content=self.prompts["ReviewAgent"]),
            HumanMessage(content=user_request)
        ]

        start_time = time.time()
        review_text = ""
        async for chunk in self.coding_llm.astream(messages):
            if chunk.content:
                review_text += chunk.content
        latency_ms = int((time.time() - start_time) * 1000)

        review_result = parse_review(review_text)

        yield {
            "agent": "ReviewAgent",
            "type": "completed",
            "status": "completed",
            "issues": review_result["issues"],
            "suggestions": review_result["suggestions"],
            "approved": review_result["approved"],
            "prompt_info": {
                "system_prompt": self.prompts["ReviewAgent"],
                "user_prompt": user_request,
                "output": review_text,
                "model": settings.coding_model,
                "latency_ms": latency_ms
            }
        }

        yield {
            "agent": "Workflow",
            "type": "completed",
            "status": "finished",
            "summary": {
                "tasks_completed": 1,
                "total_tasks": 1,
                "artifacts_count": 0,
                "review_approved": review_result["approved"]
            },
            "workflow_info": {
                "workflow_id": workflow_id,
                "workflow_type": template["name"],
                "task_type": "code_review",
                "current_node": "END",
                "dynamically_created": True
            }
        }

    async def _execute_doc_workflow(
        self,
        user_request: str,
        template: Dict[str, Any],
        workflow_id: str
    ) -> AsyncGenerator[Dict[str, Any], None]:
        """Execute documentation workflow."""
        # Analysis
        yield {
            "agent": "AnalysisAgent",
            "type": "agent_spawn",
            "status": "running",
            "message": "Spawning AnalysisAgent",
            "agent_spawn": {
                "agent_id": f"analysis-{uuid.uuid4().hex[:6]}",
                "agent_type": "AnalysisAgent",
                "parent_agent": "Orchestrator",
                "spawn_reason": "Analyze code for documentation",
                "timestamp": datetime.now().isoformat()
            }
        }

        messages = [
            SystemMessage(content=self.prompts["AnalysisAgent"]),
            HumanMessage(content=user_request)
        ]

        analysis_text = ""
        async for chunk in self.reasoning_llm.astream(messages):
            if chunk.content:
                analysis_text += chunk.content

        yield {
            "agent": "AnalysisAgent",
            "type": "completed",
            "status": "completed",
            "content": analysis_text
        }

        # DocGen
        yield {
            "agent": "DocGenAgent",
            "type": "agent_spawn",
            "status": "running",
            "message": "Spawning DocGenAgent",
            "agent_spawn": {
                "agent_id": f"docgen-{uuid.uuid4().hex[:6]}",
                "agent_type": "DocGenAgent",
                "parent_agent": "Orchestrator",
                "spawn_reason": "Generate documentation",
                "timestamp": datetime.now().isoformat()
            }
        }

        messages = [
            SystemMessage(content=self.prompts["DocGenAgent"]),
            HumanMessage(content=f"{user_request}\n\nAnalysis:\n{analysis_text}")
        ]

        doc_text = ""
        async for chunk in self.coding_llm.astream(messages):
            if chunk.content:
                doc_text += chunk.content

        artifacts = parse_code_blocks(doc_text)

        for artifact in artifacts:
            yield {
                "agent": "DocGenAgent",
                "type": "artifact",
                "status": "running",
                "artifact": artifact
            }

        yield {
            "agent": "DocGenAgent",
            "type": "completed",
            "status": "completed",
            "artifacts": artifacts
        }

        yield {
            "agent": "Workflow",
            "type": "completed",
            "status": "finished",
            "summary": {
                "tasks_completed": 1,
                "total_tasks": 1,
                "artifacts_count": len(artifacts),
                "review_approved": True
            },
            "workflow_info": {
                "workflow_id": workflow_id,
                "workflow_type": template["name"],
                "task_type": "documentation",
                "current_node": "END",
                "dynamically_created": True
            }
        }


class LangGraphWorkflowManager(BaseWorkflowManager):
    """Manager for dynamic LangGraph workflow sessions."""

    def __init__(self):
        """Initialize workflow manager."""
        self.workflows: Dict[str, DynamicLangGraphWorkflow] = {}
        logger.info("LangGraphWorkflowManager initialized with dynamic workflow support")

    def get_or_create_workflow(self, session_id: str, enable_deepagents: bool = False) -> DynamicLangGraphWorkflow:
        """Get existing workflow or create new one for session.

        Args:
            session_id: Session identifier
            enable_deepagents: Whether to enable DeepAgents middleware

        Returns:
            DynamicLangGraphWorkflow instance
        """
        if session_id not in self.workflows:
            self.workflows[session_id] = DynamicLangGraphWorkflow(enable_deepagents=enable_deepagents)
            logger.info(f"Created new dynamic workflow for session {session_id} (deepagents={enable_deepagents})")
        return self.workflows[session_id]

    async def get_workflow(
        self,
        session_id: str,
        workspace: Optional[str] = None,
        enable_deepagents: bool = False
    ) -> DynamicLangGraphWorkflow:
        """Async wrapper for get_or_create_workflow (for CodeGenerationHandler compatibility).

        Args:
            session_id: Session identifier
            workspace: Workspace path (currently unused, reserved for future use)
            enable_deepagents: Whether to enable DeepAgents middleware

        Returns:
            DynamicLangGraphWorkflow instance
        """
        return self.get_or_create_workflow(session_id, enable_deepagents)

    def delete_workflow(self, session_id: str) -> None:
        """Delete workflow for session."""
        if session_id in self.workflows:
            del self.workflows[session_id]
            logger.info(f"Deleted workflow for session {session_id}")

    def get_active_sessions(self) -> List[str]:
        """Get list of active session IDs."""
        return list(self.workflows.keys())


# Global workflow manager instance
workflow_manager = LangGraphWorkflowManager()

# Backward compatibility alias
LangGraphWorkflow = DynamicLangGraphWorkflow


# DeepAgents integration helpers
class DeepAgentsHelper:
    """Helper class to access DeepAgents capabilities from LangChain workflow."""

    @staticmethod
    def is_available() -> bool:
        """Check if DeepAgents is available."""
        return DEEPAGENTS_AVAILABLE

    @staticmethod
    def get_capabilities() -> Dict[str, bool]:
        """Get available DeepAgents capabilities."""
        return {
            "filesystem": "FilesystemMiddleware" in deepagents_middleware,
            "subagent": "SubAgentMiddleware" in deepagents_middleware,
            "todolist": "TodoListMiddleware" in deepagents_middleware,
        }

    @staticmethod
    def create_filesystem_agent(allowed_paths: List[str] = None, read_only: bool = False):
        """Create an agent with filesystem access.

        Args:
            allowed_paths: List of paths the agent can access
            read_only: If True, agent can only read files

        Returns:
            Configured agent with filesystem middleware, or None if not available
        """
        if not DEEPAGENTS_AVAILABLE:
            logger.warning("DeepAgents not available for filesystem operations")
            return None

        try:
            from deepagents import create_deep_agent
            FilesystemMiddleware = deepagents_middleware.get("FilesystemMiddleware")
            FilesystemBackend = deepagents_middleware.get("FilesystemBackend")

            if FilesystemMiddleware and FilesystemBackend:
                # Use the first allowed path as root_dir
                root_dir = (allowed_paths or ["./workspace"])[0]
                # Create filesystem backend (v0.3.0 API)
                fs_backend = FilesystemBackend(
                    root_dir=root_dir,
                    virtual_mode=read_only  # Use virtual mode for read-only
                )
                return create_deep_agent(
                    tools=[],
                    middleware=[
                        FilesystemMiddleware(backend=fs_backend)
                    ]
                )
        except Exception as e:
            logger.error(f"Failed to create filesystem agent: {e}")
            logger.exception("Full traceback:")
        return None


# Export DeepAgents availability
def get_framework_capabilities() -> Dict[str, Any]:
    """Get current framework capabilities including DeepAgents status."""
    return {
        "framework": "langchain",
        "workflow_type": "DynamicLangGraphWorkflow",
        "deepagents_available": DEEPAGENTS_AVAILABLE,
        "deepagents_capabilities": DeepAgentsHelper.get_capabilities(),
        "task_types": list(WORKFLOW_TEMPLATES.keys()),
        "features": {
            "dynamic_workflow": True,
            "supervisor_agent": True,
            "review_loop": True,
            "line_specific_review": True,
            "multi_file_support": True,
        }
    }


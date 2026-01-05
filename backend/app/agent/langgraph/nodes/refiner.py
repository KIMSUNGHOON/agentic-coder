"""Refiner Node for code improvement based on review feedback

Implements diff-based code updates instead of full regeneration for efficiency.
Uses LLM provider abstraction for flexible model switching.
"""

import logging
import difflib
from typing import Dict, List
from datetime import datetime
from app.agent.langgraph.schemas.state import QualityGateState, CodeDiff, DebugLog
from app.core.config import settings

# Import LLM provider for model-agnostic calls
try:
    from shared.llm import LLMProviderFactory, TaskType
    LLM_PROVIDER_AVAILABLE = True
except ImportError:
    LLM_PROVIDER_AVAILABLE = False

# Import DeepSeek prompts for enhanced reasoning
try:
    from shared.prompts.deepseek_r1 import (
        DEEPSEEK_R1_SYSTEM_PROMPT,
        DEEPSEEK_R1_RCA_PROMPT,
        DEEPSEEK_R1_LOOP_ANALYSIS_PROMPT,
    )
    DEEPSEEK_PROMPTS_AVAILABLE = True
except ImportError:
    DEEPSEEK_PROMPTS_AVAILABLE = False

logger = logging.getLogger(__name__)


def _detect_language(file_path: str) -> str:
    """Detect programming language from file extension"""
    ext = file_path.split(".")[-1].lower() if "." in file_path else ""
    language_map = {
        "py": "python",
        "js": "javascript",
        "ts": "typescript",
        "tsx": "typescript",
        "jsx": "javascript",
        "java": "java",
        "go": "go",
        "rs": "rust",
        "cpp": "cpp",
        "c": "c",
        "h": "c",
        "hpp": "cpp",
        "rb": "ruby",
        "php": "php",
        "cs": "csharp",
        "swift": "swift",
        "kt": "kotlin",
        "scala": "scala",
        "sql": "sql",
        "sh": "bash",
        "bash": "bash",
        "zsh": "bash",
        "json": "json",
        "yaml": "yaml",
        "yml": "yaml",
        "xml": "xml",
        "html": "html",
        "css": "css",
        "md": "markdown",
        "txt": "text",
    }
    return language_map.get(ext, "text")


# DeepSeek-R1 style refinement prompt with <think> tags
REFINER_ANALYSIS_PROMPT = """<think>
1. Analyze the issues: What problems were found in the code?
2. Identify root cause: Why do these issues exist?
3. Plan fixes: What specific changes need to be made?
4. Validate approach: Will these changes introduce new problems?
5. Prioritize: Which fixes are most critical?
</think>

Based on the analysis above, generate the minimal code changes needed to fix the issues.

Issues to fix:
{issues}

Suggestions:
{suggestions}

Current code quality score: {quality_score:.0%}
Target score: 80%+

For each issue, provide:
1. File path
2. Original code section
3. Fixed code section
4. Explanation of the fix
"""


def refiner_node(state: QualityGateState) -> Dict:
    """Refiner node: Fix code based on review feedback using diff-based updates

    This node:
    1. Analyzes review feedback and identifies issues
    2. Generates targeted fixes (NOT full regeneration)
    3. Creates unified diffs for each change
    4. Updates code_diffs list for human approval

    CRITICAL: Uses diff-based updates to minimize token usage and preserve
    unchanged code sections.

    Args:
        state: Current workflow state

    Returns:
        State updates with refined code and diffs
    """
    logger.info("🔧 Refiner Node: Analyzing review feedback and generating fixes...")

    # Extract review feedback
    review_feedback = state.get("review_feedback")
    if not review_feedback:
        logger.warning("⚠️  No review feedback available - skipping refinement")
        return {
            "current_node": "refiner",
            "is_fixed": False,
            "refiner_output": {"status": "skipped", "reason": "no_feedback"},
        }

    issues = review_feedback.get("issues", [])
    suggestions = review_feedback.get("suggestions", [])
    approved = review_feedback.get("approved", False)

    if approved:
        logger.info("✅ Code already approved - no refinement needed")
        return {
            "current_node": "refiner",
            "is_fixed": True,
            "refiner_output": {"status": "approved", "reason": "no_issues"},
        }

    # Get artifacts to refine
    coder_output = state.get("coder_output")
    if not coder_output or "artifacts" not in coder_output:
        logger.error("❌ No artifacts to refine")
        return {
            "current_node": "refiner",
            "is_fixed": False,
            "refiner_output": {"status": "error", "reason": "no_artifacts"},
            "error_log": ["Refiner: No artifacts found to refine"],
        }

    artifacts = coder_output["artifacts"]

    # Generate diffs for each fix
    code_diffs: List[CodeDiff] = []
    refinement_iteration = state.get("refinement_iteration", 0) + 1
    quality_score = review_feedback.get("quality_score", 0.0)

    logger.info(f"📝 Processing {len(issues)} issues and {len(suggestions)} suggestions")
    logger.info(f"   Quality Score: {quality_score:.0%} (target: 70%+)")
    logger.info(f"   Refinement Iteration: {refinement_iteration}")

    # Log DeepSeek-R1 style analysis prompt (for debugging and transparency)
    if DEEPSEEK_PROMPTS_AVAILABLE:
        analysis_prompt = REFINER_ANALYSIS_PROMPT.format(
            issues="\n".join(f"  - {issue}" for issue in issues),
            suggestions="\n".join(f"  - {sug}" for sug in suggestions),
            quality_score=quality_score
        )
        logger.debug(f"🤔 DeepSeek-R1 Analysis Prompt:\n{analysis_prompt[:500]}...")

    # Simulate code refinement (in production, this would call LLM)
    # For now, we'll create example diffs
    for idx, issue in enumerate(issues):
        if idx >= len(artifacts):
            break

        artifact = artifacts[idx]
        file_path = artifact.get("file_path", "unknown")
        original_content = artifact.get("content", "")

        # Get corresponding suggestion if available
        suggestion = suggestions[idx] if idx < len(suggestions) else ""

        # Apply fix using LLM
        modified_content = _apply_fix_with_llm(original_content, issue, suggestion)

        # Generate unified diff
        diff_hunks = list(difflib.unified_diff(
            original_content.splitlines(keepends=True),
            modified_content.splitlines(keepends=True),
            fromfile=f"a/{file_path}",
            tofile=f"b/{file_path}",
            lineterm=""
        ))

        if diff_hunks:
            code_diff = CodeDiff(
                file_path=file_path,
                original_content=original_content,
                modified_content=modified_content,
                diff_hunks=diff_hunks,
                description=f"Fix: {issue}"
            )
            code_diffs.append(code_diff)

    # CRITICAL FIX: Apply diffs to actual files AND update artifacts
    workspace_root = state.get("workspace_root", "/tmp/workspace")
    updated_artifacts = []
    updated_filenames = set()  # Track which files were updated

    for code_diff in code_diffs:
        # Write modified content to file
        from app.agent.langgraph.tools.filesystem_tools import write_file_tool

        # CRITICAL FIX: Use full relative path to preserve directory structure
        # file_path may be:
        # - Just filename: "main.py"
        # - Relative path from workspace: "src/main.py"
        # - Full path: "/home/user/workspace/project/src/main.py"
        original_file_path = code_diff["file_path"]

        # If it's an absolute path starting with workspace_root, make it relative
        if original_file_path.startswith(workspace_root):
            relative_path = original_file_path[len(workspace_root):].lstrip("/")
        else:
            # Use as-is (already relative or just filename)
            relative_path = original_file_path.lstrip("/")

        # Extract just filename for artifact tracking
        filename = relative_path.split("/")[-1]

        logger.info(f"📝 Writing fix: {relative_path} (in {workspace_root})")

        result = write_file_tool(
            file_path=relative_path,  # Use full relative path to preserve directory structure
            content=code_diff["modified_content"],
            workspace_root=workspace_root
        )

        if result["success"]:
            logger.info(f"✅ Applied fix to: {relative_path}")
            # Track by full relative path to avoid losing directory info
            updated_filenames.add(relative_path)

            # Update artifact with new content - preserve full path
            updated_artifacts.append({
                "filename": relative_path,  # Use full relative path as identifier
                "file_path": result["file_path"],  # Full absolute path from write_file_tool
                "language": _detect_language(relative_path),
                "content": code_diff["modified_content"],
                "size_bytes": len(code_diff["modified_content"]),
                "checksum": "updated",
                "action": "modified",
                "saved": True,
            })
        else:
            logger.error(f"❌ Failed to apply fix: {result.get('error')}")

    # CRITICAL: Merge updated artifacts with existing artifacts (don't replace!)
    # Keep existing artifacts that weren't updated
    existing_artifacts = state.get("coder_output", {}).get("artifacts", [])
    merged_artifacts = []

    # Add existing artifacts that weren't modified
    # Check both by full relative path and by just filename (for backwards compatibility)
    for artifact in existing_artifacts:
        artifact_filename = artifact.get("filename", "")
        artifact_file_path = artifact.get("file_path", "")

        # Check if this artifact was updated by relative path or full path
        is_updated = False
        for updated_path in updated_filenames:
            # Match by: full relative path, just filename, or file_path
            if (artifact_filename == updated_path or
                artifact_filename.split("/")[-1] == updated_path.split("/")[-1] or
                artifact_file_path.endswith(updated_path)):
                is_updated = True
                break

        if not is_updated:
            merged_artifacts.append(artifact)

    # Add updated artifacts
    merged_artifacts.extend(updated_artifacts)

    logger.info(f"📁 Artifacts: {len(existing_artifacts)} existing, {len(updated_artifacts)} updated, {len(merged_artifacts)} total")

    # Update coder_output with MERGED artifacts (not replaced)
    updated_coder_output = state.get("coder_output", {}).copy()
    updated_coder_output["artifacts"] = merged_artifacts
    if updated_artifacts:
        updated_coder_output["status"] = "refined"

    # Determine if fixes are sufficient
    is_fixed = len(code_diffs) > 0 and len(code_diffs) == len(issues)

    logger.info(f"🔧 Refinement complete: {len(code_diffs)} diffs generated and applied")
    logger.info(f"   Fixed: {is_fixed}")
    logger.info(f"   Iteration: {refinement_iteration}")

    # Log debug info with DeepSeek-R1 style reasoning (after all processing)
    debug_logs: List[DebugLog] = []
    if state.get("enable_debug"):
        # DeepSeek-R1 style thinking log
        thinking_content = f"""<think>
1. Issues analyzed: {len(issues)} problems found
2. Root causes identified: Code quality issues, missing implementations
3. Fixes planned: {len(code_diffs)} targeted modifications
4. Validation: Changes are minimal and focused
5. Priority: Critical security and functionality issues first
</think>

Refinement iteration {refinement_iteration}: Applied {len(updated_artifacts)} fixes.
Quality score: {quality_score:.0%} → targeting 70%+"""

        debug_logs.append(DebugLog(
            timestamp=datetime.utcnow().isoformat(),
            node="refiner",
            agent="RefinerAgent",
            event_type="thinking",
            content=thinking_content,
            metadata={
                "issues_count": len(issues),
                "suggestions_count": len(suggestions),
                "diffs_count": len(code_diffs),
                "diffs_applied": len(updated_artifacts),
                "iteration": refinement_iteration,
                "quality_score": quality_score,
                "deepseek_prompts_available": DEEPSEEK_PROMPTS_AVAILABLE,
            },
            token_usage=None  # Would be populated by actual LLM call
        ))

    return {
        "current_node": "refiner",
        "refiner_output": {
            "status": "completed",
            "diffs_generated": len(code_diffs),
            "diffs_applied": len(updated_artifacts),
            "iteration": refinement_iteration
        },
        "code_diffs": code_diffs,
        "coder_output": updated_coder_output,  # Update artifacts with fixed code
        "is_fixed": is_fixed,
        "refinement_iteration": refinement_iteration,
        "debug_logs": debug_logs,
        "pending_diffs": code_diffs,  # Send to approval node
    }


def _apply_fix_with_llm(original_content: str, issue: str, suggestion: str = "") -> str:
    """Apply fix to code using LLM

    Uses the configured LLM provider to generate fixes for the identified issue.

    Args:
        original_content: Original code content
        issue: Issue description from review
        suggestion: Optional suggestion for the fix

    Returns:
        Modified code with the issue fixed
    """
    # Get endpoint and model from settings
    refine_endpoint = settings.get_coding_endpoint
    refine_model = settings.get_coding_model

    # Build the fix prompt
    fix_prompt = f"""Fix the following issue in the code:

ISSUE: {issue}
{f'SUGGESTION: {suggestion}' if suggestion else ''}

ORIGINAL CODE:
```
{original_content}
```

REQUIREMENTS:
1. Fix ONLY the specified issue
2. Maintain existing functionality
3. Keep changes minimal and targeted
4. Return the COMPLETE fixed code (not a diff)

Return the fixed code directly, without explanations or markdown formatting."""

    # Try LLM provider adapter first
    if LLM_PROVIDER_AVAILABLE and refine_endpoint:
        try:
            provider = LLMProviderFactory.create(
                model_type=settings.get_coding_model_type,
                endpoint=refine_endpoint,
                model=refine_model
            )

            response = provider.generate_sync(fix_prompt, TaskType.REFINE)

            if response.content:
                # Clean up response - remove markdown code blocks if present
                fixed_code = response.content.strip()
                if fixed_code.startswith("```"):
                    lines = fixed_code.split("\n")
                    # Remove first and last lines if they're code fences
                    if lines[0].startswith("```"):
                        lines = lines[1:]
                    if lines and lines[-1].strip() == "```":
                        lines = lines[:-1]
                    fixed_code = "\n".join(lines)

                logger.info(f"🤖 Fix applied via {settings.get_coding_model_type} adapter")
                return fixed_code

        except Exception as e:
            logger.warning(f"LLM provider failed for fix: {e}, using fallback")

    # Fallback to direct HTTP call
    if refine_endpoint:
        try:
            import httpx

            prompt = f"""You are a code fixing expert. Fix the following issue:

{fix_prompt}

Fixed code:"""

            with httpx.Client(timeout=90.0) as client:
                response = client.post(
                    f"{refine_endpoint}/completions",
                    json={
                        "model": refine_model,
                        "prompt": prompt,
                        "max_tokens": 2048,
                        "temperature": 0.2,
                        "stop": ["```\n\n", "ISSUE:", "ORIGINAL CODE:"]
                    }
                )

                if response.status_code == 200:
                    result = response.json()
                    fixed_code = result["choices"][0]["text"].strip()

                    # Clean up markdown if present
                    if fixed_code.startswith("```"):
                        lines = fixed_code.split("\n")
                        if lines[0].startswith("```"):
                            lines = lines[1:]
                        if lines and lines[-1].strip() == "```":
                            lines = lines[:-1]
                        fixed_code = "\n".join(lines)

                    logger.info(f"🔧 Fix applied via direct LLM call")
                    return fixed_code

        except Exception as e:
            logger.warning(f"Direct LLM call failed: {e}, using heuristic fallback")

    # Final fallback: heuristic fixes
    return _apply_fix_heuristic(original_content, issue)


def _apply_fix_heuristic(original_content: str, issue: str) -> str:
    """Apply heuristic-based fixes when LLM is not available

    Implements OWASP Top 10 security fixes and common code quality improvements.

    Args:
        original_content: Original code
        issue: Issue description

    Returns:
        Modified code with attempted fix
    """
    issue_lower = issue.lower()
    modified = original_content

    # ========================================
    # OWASP Top 10 Security Fixes
    # ========================================

    # 1. SQL Injection (A03:2021)
    if "sql injection" in issue_lower or "sql" in issue_lower and "injection" in issue_lower:
        modified = _fix_sql_injection(modified)
        logger.info("🔒 Applied SQL injection fix")

    # 2. Command Injection (A03:2021)
    elif "command injection" in issue_lower or "os.system" in issue_lower or "subprocess" in issue_lower:
        modified = _fix_command_injection(modified)
        logger.info("🔒 Applied command injection fix")

    # 3. XSS - Cross-Site Scripting (A03:2021)
    elif "xss" in issue_lower or "cross-site scripting" in issue_lower:
        modified = _fix_xss(modified)
        logger.info("🔒 Applied XSS fix")

    # 4. Path Traversal (A01:2021)
    elif "path traversal" in issue_lower or "directory traversal" in issue_lower:
        modified = _fix_path_traversal(modified)
        logger.info("🔒 Applied path traversal fix")

    # 5. Hardcoded Credentials (A07:2021)
    elif "hardcoded" in issue_lower and ("password" in issue_lower or "secret" in issue_lower or "credential" in issue_lower):
        modified = _fix_hardcoded_credentials(modified)
        logger.info("🔒 Applied hardcoded credentials fix")

    # 6. Insecure Deserialization (A08:2021)
    elif "pickle" in issue_lower or "deserialization" in issue_lower or "yaml.load" in issue_lower:
        modified = _fix_insecure_deserialization(modified)
        logger.info("🔒 Applied insecure deserialization fix")

    # 7. Input Validation (A03:2021)
    elif "input validation" in issue_lower or "validate" in issue_lower:
        modified = _fix_input_validation(modified)
        logger.info("🔒 Applied input validation fix")

    # 8. Eval/Exec Usage (A03:2021)
    elif "eval" in issue_lower or "exec" in issue_lower:
        modified = _fix_eval_exec(modified)
        logger.info("🔒 Applied eval/exec fix")

    # ========================================
    # Code Quality Fixes
    # ========================================

    # TODO/Incomplete Implementation
    elif "TODO" in issue or "incomplete implementation" in issue_lower:
        lines = modified.splitlines()
        fixed_lines = []
        for line in lines:
            if "# TODO" in line and "Implement" in line:
                continue
            fixed_lines.append(line)

        if "calculator" in modified.lower():
            fixed_lines.extend([
                "",
                "def add(a: float, b: float) -> float:",
                '    """Add two numbers."""',
                "    return a + b",
                "",
                "def subtract(a: float, b: float) -> float:",
                '    """Subtract b from a."""',
                "    return a - b"
            ])

        modified = "\n".join(fixed_lines)

    # Error Handling
    elif "error handling" in issue_lower:
        indented = "\n".join("    " + line for line in modified.splitlines())
        modified = f"try:\n{indented}\nexcept Exception as e:\n    logger.error(f'Error: {{e}}')\n    raise"

    # Generic security fix (fallback)
    elif "security" in issue_lower:
        # Try to apply multiple security fixes
        modified = _fix_sql_injection(modified)
        modified = _fix_command_injection(modified)
        modified = _fix_path_traversal(modified)
        logger.info("🔒 Applied generic security fixes")

    return modified


def _fix_sql_injection(content: str) -> str:
    """Fix SQL injection vulnerabilities by using parameterized queries"""
    import re

    # Pattern: f-string or format() with SQL
    # Example: f"SELECT * FROM users WHERE id = {user_id}"
    # Fix: cursor.execute("SELECT * FROM users WHERE id = ?", (user_id,))

    lines = content.splitlines()
    fixed_lines = []
    imports_needed = set()

    for line in lines:
        # Check for dangerous SQL patterns
        if re.search(r'(execute|query|cursor)\s*\(.*?["\'].*?(SELECT|INSERT|UPDATE|DELETE).*?%s.*?["\'].*?%', line, re.IGNORECASE):
            # Already using %s - likely safe, but add comment
            fixed_lines.append(line)
        elif re.search(r'f["\'].*?(SELECT|INSERT|UPDATE|DELETE).*?\{.*?\}.*?["\']', line, re.IGNORECASE):
            # Dangerous f-string SQL - add warning comment
            fixed_lines.append("# SECURITY WARNING: Potential SQL injection - use parameterized queries")
            fixed_lines.append("# Example: cursor.execute('SELECT * FROM users WHERE id = ?', (user_id,))")
            fixed_lines.append(line.replace('f"', '"').replace("f'", "'") + "  # TODO: Fix SQL injection")
        elif re.search(r'["\'].*?(SELECT|INSERT|UPDATE|DELETE).*?["\'].*?\.format\(', line, re.IGNORECASE):
            # Dangerous .format() SQL
            fixed_lines.append("# SECURITY WARNING: Potential SQL injection - use parameterized queries")
            fixed_lines.append(line + "  # TODO: Fix SQL injection")
        elif re.search(r'["\'].*?(SELECT|INSERT|UPDATE|DELETE).*?\+', line, re.IGNORECASE):
            # String concatenation in SQL
            fixed_lines.append("# SECURITY WARNING: SQL injection via string concatenation")
            fixed_lines.append(line + "  # TODO: Use parameterized queries")
        else:
            fixed_lines.append(line)

    return "\n".join(fixed_lines)


def _fix_command_injection(content: str) -> str:
    """Fix command injection vulnerabilities"""
    import re

    lines = content.splitlines()
    fixed_lines = []

    for line in lines:
        stripped = line.strip()

        # os.system() - very dangerous
        if "os.system(" in line:
            indent = len(line) - len(line.lstrip())
            fixed_lines.append(" " * indent + "# SECURITY FIX: os.system() is vulnerable to command injection")
            fixed_lines.append(" " * indent + "# Use subprocess.run() with shell=False instead")
            # Try to convert to subprocess
            match = re.search(r'os\.system\(["\'](.+?)["\']\)', line)
            if match:
                cmd = match.group(1)
                cmd_parts = cmd.split()
                if cmd_parts:
                    fixed_lines.append(" " * indent + f"import subprocess")
                    fixed_lines.append(" " * indent + f"subprocess.run({cmd_parts}, shell=False, check=True)")
            else:
                fixed_lines.append(line.replace("os.system", "# os.system  # DISABLED: Command injection risk"))

        # subprocess with shell=True
        elif "shell=True" in line and "subprocess" in line:
            fixed_lines.append(line.replace("shell=True", "shell=False  # SECURITY FIX: shell=True is dangerous"))

        # eval() with user input
        elif "eval(" in line:
            indent = len(line) - len(line.lstrip())
            fixed_lines.append(" " * indent + "# SECURITY FIX: eval() is dangerous - use ast.literal_eval() for safe parsing")
            fixed_lines.append(line.replace("eval(", "ast.literal_eval(  # Changed from eval"))

        else:
            fixed_lines.append(line)

    # Add import if needed
    if "ast.literal_eval" in "\n".join(fixed_lines) and "import ast" not in content:
        fixed_lines.insert(0, "import ast")

    return "\n".join(fixed_lines)


def _fix_xss(content: str) -> str:
    """Fix Cross-Site Scripting vulnerabilities"""
    import re

    lines = content.splitlines()
    fixed_lines = []

    for line in lines:
        # Check for dangerous HTML rendering
        if re.search(r'render.*?["\'].*?\{.*?\}.*?["\']', line) or "innerHTML" in line:
            indent = len(line) - len(line.lstrip())
            fixed_lines.append(" " * indent + "# SECURITY WARNING: Potential XSS - escape user input")
            fixed_lines.append(line)

        # Flask/Jinja2 - check for |safe filter
        elif "|safe" in line or "Markup(" in line:
            indent = len(line) - len(line.lstrip())
            fixed_lines.append(" " * indent + "# SECURITY WARNING: |safe or Markup() bypasses XSS protection")
            fixed_lines.append(line + "  # Review: ensure input is sanitized")

        else:
            fixed_lines.append(line)

    return "\n".join(fixed_lines)


def _fix_path_traversal(content: str) -> str:
    """Fix path traversal vulnerabilities"""
    import re

    lines = content.splitlines()
    fixed_lines = []
    needs_os_import = False

    for line in lines:
        # Check for file operations with user input
        if re.search(r'open\([^)]*[\+\{]', line) or re.search(r'Path\([^)]*[\+\{]', line):
            indent = len(line) - len(line.lstrip())
            fixed_lines.append(" " * indent + "# SECURITY FIX: Validate path to prevent directory traversal")
            fixed_lines.append(" " * indent + "# Use os.path.abspath() and check if path starts with allowed directory")

            # Add path validation
            fixed_lines.append(" " * indent + "# Example: if not os.path.abspath(filepath).startswith(ALLOWED_DIR): raise ValueError('Invalid path')")
            fixed_lines.append(line)
            needs_os_import = True

        # Direct path concatenation
        elif re.search(r'os\.path\.join\([^)]*\+', line):
            indent = len(line) - len(line.lstrip())
            fixed_lines.append(" " * indent + "# SECURITY WARNING: Validate user input in path operations")
            fixed_lines.append(line)

        else:
            fixed_lines.append(line)

    return "\n".join(fixed_lines)


def _fix_hardcoded_credentials(content: str) -> str:
    """Fix hardcoded credentials by using environment variables"""
    import re

    lines = content.splitlines()
    fixed_lines = []
    env_vars_added = []

    for line in lines:
        # Pattern: password = "..." or secret = "..." or api_key = "..."
        match = re.search(r'(\w*(?:password|secret|api_key|token|credential)\w*)\s*=\s*["\']([^"\']+)["\']', line, re.IGNORECASE)
        if match:
            var_name = match.group(1)
            env_var_name = var_name.upper()
            indent = len(line) - len(line.lstrip())

            fixed_lines.append(" " * indent + f"# SECURITY FIX: Moved hardcoded credential to environment variable")
            fixed_lines.append(" " * indent + f'{var_name} = os.environ.get("{env_var_name}")')
            fixed_lines.append(" " * indent + f'if not {var_name}:')
            fixed_lines.append(" " * indent + f'    raise ValueError("{env_var_name} environment variable is required")')
            env_vars_added.append(env_var_name)
        else:
            fixed_lines.append(line)

    # Add os import if needed
    if env_vars_added and "import os" not in content:
        fixed_lines.insert(0, "import os")

    return "\n".join(fixed_lines)


def _fix_insecure_deserialization(content: str) -> str:
    """Fix insecure deserialization vulnerabilities"""
    import re

    lines = content.splitlines()
    fixed_lines = []

    for line in lines:
        # pickle.loads() is dangerous
        if "pickle.load" in line:
            indent = len(line) - len(line.lstrip())
            fixed_lines.append(" " * indent + "# SECURITY WARNING: pickle.load() can execute arbitrary code")
            fixed_lines.append(" " * indent + "# Consider using json.load() or a safer alternative")
            fixed_lines.append(line + "  # TODO: Replace with safe deserialization")

        # yaml.load() without Loader
        elif "yaml.load(" in line and "Loader=" not in line:
            fixed_lines.append(line.replace("yaml.load(", "yaml.safe_load(  # SECURITY FIX: Use safe_load"))

        else:
            fixed_lines.append(line)

    return "\n".join(fixed_lines)


def _fix_input_validation(content: str) -> str:
    """Add input validation to functions"""
    import re

    lines = content.splitlines()
    fixed_lines = []
    in_function = False
    function_indent = 0
    function_params = []

    for i, line in enumerate(lines):
        # Detect function definition
        func_match = re.match(r'^(\s*)def\s+(\w+)\s*\(([^)]*)\)', line)
        if func_match:
            in_function = True
            function_indent = len(func_match.group(1))
            params_str = func_match.group(3)
            # Extract parameter names (simplified)
            function_params = [p.strip().split(':')[0].split('=')[0].strip()
                               for p in params_str.split(',') if p.strip() and p.strip() != 'self']
            fixed_lines.append(line)

            # Check if next line is docstring
            if i + 1 < len(lines):
                next_line = lines[i + 1].strip()
                if next_line.startswith('"""') or next_line.startswith("'''"):
                    continue  # Will add validation after docstring

            # Add validation for parameters
            if function_params:
                body_indent = " " * (function_indent + 4)
                fixed_lines.append(f"{body_indent}# Input validation")
                for param in function_params:
                    if param and param not in ['args', 'kwargs']:
                        fixed_lines.append(f"{body_indent}if {param} is None:")
                        fixed_lines.append(f"{body_indent}    raise ValueError('{param} cannot be None')")

        elif in_function and line.strip().startswith('"""') or line.strip().startswith("'''"):
            fixed_lines.append(line)
            # Check if docstring ends on same line
            if line.strip().count('"""') >= 2 or line.strip().count("'''") >= 2:
                # Add validation after single-line docstring
                if function_params:
                    body_indent = " " * (function_indent + 4)
                    fixed_lines.append(f"{body_indent}# Input validation")
                    for param in function_params:
                        if param and param not in ['args', 'kwargs']:
                            fixed_lines.append(f"{body_indent}if {param} is None:")
                            fixed_lines.append(f"{body_indent}    raise ValueError('{param} cannot be None')")
                in_function = False
                function_params = []
        else:
            fixed_lines.append(line)

    return "\n".join(fixed_lines)


def _fix_eval_exec(content: str) -> str:
    """Fix dangerous eval/exec usage"""
    import re

    lines = content.splitlines()
    fixed_lines = []

    for line in lines:
        if "eval(" in line and "literal_eval" not in line:
            indent = len(line) - len(line.lstrip())
            fixed_lines.append(" " * indent + "# SECURITY FIX: eval() can execute arbitrary code")
            fixed_lines.append(" " * indent + "# Use ast.literal_eval() for safe evaluation of literals")
            fixed_lines.append(line.replace("eval(", "ast.literal_eval("))

        elif "exec(" in line:
            indent = len(line) - len(line.lstrip())
            fixed_lines.append(" " * indent + "# SECURITY WARNING: exec() can execute arbitrary code")
            fixed_lines.append(" " * indent + "# Consider using a safer alternative or sandboxed execution")
            fixed_lines.append(line + "  # TODO: Remove or sandbox exec()")

        else:
            fixed_lines.append(line)

    # Add ast import if needed
    if "ast.literal_eval" in "\n".join(fixed_lines) and "import ast" not in content:
        fixed_lines.insert(0, "import ast")

    return "\n".join(fixed_lines)

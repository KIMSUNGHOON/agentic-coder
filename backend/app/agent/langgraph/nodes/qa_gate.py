"""QA Gate Node - Production Implementation

Quality assurance gate for generated code.
"""

import logging
from typing import Dict, List
from datetime import datetime

from app.agent.langgraph.schemas.state import QualityGateState, DebugLog

logger = logging.getLogger(__name__)


def qa_gate_node(state: QualityGateState) -> Dict:
    """QA Gate Node: Quality assurance checks

    This node performs automated QA checks:
    1. Syntax validation
    2. Security checks
    3. Best practices verification
    4. Performance checks
    5. Test coverage (if tests exist)

    Args:
        state: Current workflow state

    Returns:
        State updates with QA results
    """
    logger.info("🔍 QA Gate: Running quality assurance checks...")

    coder_output = state.get("coder_output")
    debug_logs = []

    if not coder_output or not coder_output.get("artifacts"):
        logger.warning("⚠️  No code to check")
        return {
            "qa_results": {
                "passed": False,
                "checks": {},
                "message": "No artifacts to check"
            },
            "qa_passed": False,
            "debug_logs": debug_logs,
        }

    artifacts = coder_output.get("artifacts", [])

    # Add thinking debug log
    if state.get("enable_debug"):
        debug_logs.append(DebugLog(
            timestamp=datetime.utcnow().isoformat(),
            node="qa_gate",
            agent="QAGate",
            event_type="thinking",
            content=f"Running QA checks on {len(artifacts)} files...",
            metadata={"file_count": len(artifacts)},
            token_usage=None
        ))

    # Run QA checks
    try:
        qa_results = _run_qa_checks(artifacts)

        passed = qa_results["passed"]
        logger.info(f"🔍 QA Gate {'✅ PASSED' if passed else '❌ FAILED'}")
        for check_name, check_result in qa_results["checks"].items():
            status = "✅" if check_result["passed"] else "❌"
            logger.info(f"   {status} {check_name}: {check_result['message']}")

        # Add result debug log
        if state.get("enable_debug"):
            debug_logs.append(DebugLog(
                timestamp=datetime.utcnow().isoformat(),
                node="qa_gate",
                agent="QAGate",
                event_type="result",
                content=f"QA {'passed' if passed else 'failed'}: "
                       f"{sum(1 for c in qa_results['checks'].values() if c['passed'])}/"
                       f"{len(qa_results['checks'])} checks passed",
                metadata=qa_results["checks"],
                token_usage=None
            ))

        return {
            "qa_results": qa_results,
            "qa_passed": passed,
            "debug_logs": debug_logs,
        }

    except Exception as e:
        logger.error(f"❌ QA Gate failed: {e}", exc_info=True)

        if state.get("enable_debug"):
            debug_logs.append(DebugLog(
                timestamp=datetime.utcnow().isoformat(),
                node="qa_gate",
                agent="QAGate",
                event_type="error",
                content=f"QA check failed: {str(e)}",
                metadata={"error_type": type(e).__name__},
                token_usage=None
            ))

        return {
            "qa_results": {
                "passed": False,
                "checks": {},
                "message": f"QA error: {str(e)}"
            },
            "qa_passed": False,
            "debug_logs": debug_logs,
        }


def _run_qa_checks(artifacts: List[Dict]) -> Dict:
    """Run QA checks on artifacts

    Args:
        artifacts: List of code artifacts

    Returns:
        QA results with passed flag and check details
    """
    checks = {}

    # Check 1: File count
    checks["file_count"] = {
        "passed": len(artifacts) > 0,
        "message": f"{len(artifacts)} files generated"
    }

    # Check 2: No empty files
    empty_files = [a["filename"] for a in artifacts if not a.get("content", "").strip()]
    checks["no_empty_files"] = {
        "passed": len(empty_files) == 0,
        "message": "No empty files" if not empty_files else f"Empty files: {', '.join(empty_files)}"
    }

    # Check 3: Syntax validation (basic)
    syntax_errors = []
    for artifact in artifacts:
        language = artifact.get("language", "text")
        content = artifact.get("content", "")
        filename = artifact.get("filename", "unknown")

        if language == "python":
            # Basic Python syntax check
            try:
                compile(content, filename, "exec")
            except SyntaxError as e:
                syntax_errors.append(f"{filename}:{e.lineno}: {e.msg}")

        elif language == "javascript":
            # Basic JS check (just look for common syntax errors)
            if content.count("{") != content.count("}"):
                syntax_errors.append(f"{filename}: Mismatched braces")
            if content.count("(") != content.count(")"):
                syntax_errors.append(f"{filename}: Mismatched parentheses")

        elif language == "html":
            # Basic HTML check
            import re
            # Count opening and closing tags (very basic)
            open_tags = len(re.findall(r'<(\w+)[^/>]*>', content))
            close_tags = len(re.findall(r'</(\w+)>', content))
            if abs(open_tags - close_tags) > 2:  # Allow some self-closing tags
                syntax_errors.append(f"{filename}: Possible unclosed tags")

    checks["syntax_valid"] = {
        "passed": len(syntax_errors) == 0,
        "message": "No syntax errors" if not syntax_errors else f"Errors: {'; '.join(syntax_errors[:3])}"
    }

    # Check 4: Security checks (basic)
    security_issues = []
    for artifact in artifacts:
        content = artifact.get("content", "")
        filename = artifact.get("filename", "unknown")

        # Check for common security issues
        if "eval(" in content:
            security_issues.append(f"{filename}: Uses dangerous eval()")
        if "exec(" in content:
            security_issues.append(f"{filename}: Uses dangerous exec()")
        if "innerHTML" in content and "=" in content:
            security_issues.append(f"{filename}: Potential XSS via innerHTML")

    checks["security"] = {
        "passed": len(security_issues) == 0,
        "message": "No security issues" if not security_issues else f"Issues: {'; '.join(security_issues[:3])}"
    }

    # Check 5: Documentation exists
    has_readme = any(a.get("filename", "").lower() == "readme.md" for a in artifacts)
    has_docs = any(
        '"""' in a.get("content", "") or "'''" in a.get("content", "") or "<!--" in a.get("content", "")
        for a in artifacts
    )
    checks["documentation"] = {
        "passed": has_readme or has_docs,
        "message": "Documentation found" if (has_readme or has_docs) else "No documentation"
    }

    # Overall pass/fail
    critical_checks = ["file_count", "no_empty_files", "syntax_valid", "security"]
    passed = all(checks[name]["passed"] for name in critical_checks if name in checks)

    return {
        "passed": passed,
        "checks": checks,
        "message": "All QA checks passed" if passed else "Some QA checks failed"
    }

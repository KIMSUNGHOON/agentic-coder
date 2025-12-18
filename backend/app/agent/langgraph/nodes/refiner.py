"""Refiner Node for code improvement based on review feedback

Implements diff-based code updates instead of full regeneration for efficiency.
"""

import logging
import difflib
from typing import Dict, List
from datetime import datetime
from app.agent.langgraph.schemas.state import QualityGateState, CodeDiff, DebugLog

logger = logging.getLogger(__name__)


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

    logger.info(f"📝 Processing {len(issues)} issues and {len(suggestions)} suggestions")

    # Simulate code refinement (in production, this would call LLM)
    # For now, we'll create example diffs
    for idx, issue in enumerate(issues):
        if idx >= len(artifacts):
            break

        artifact = artifacts[idx]
        file_path = artifact.get("file_path", "unknown")
        original_content = artifact.get("content", "")

        # PLACEHOLDER: In production, call LLM to generate fix
        # For now, simulate a simple fix
        modified_content = _apply_fix_simulation(original_content, issue)

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

    # Log debug info
    debug_logs: List[DebugLog] = []
    if state.get("enable_debug"):
        debug_logs.append(DebugLog(
            timestamp=datetime.utcnow().isoformat(),
            node="refiner",
            agent="RefinerAgent",
            event_type="thinking",
            content=f"Analyzed {len(issues)} issues, generated {len(code_diffs)} diffs",
            metadata={
                "issues_count": len(issues),
                "diffs_count": len(code_diffs),
                "iteration": refinement_iteration
            },
            token_usage=None  # Would be populated by actual LLM call
        ))

    # Determine if fixes are sufficient
    is_fixed = len(code_diffs) > 0 and len(code_diffs) == len(issues)

    logger.info(f"🔧 Refinement complete: {len(code_diffs)} diffs generated")
    logger.info(f"   Fixed: {is_fixed}")
    logger.info(f"   Iteration: {refinement_iteration}")

    return {
        "current_node": "refiner",
        "refiner_output": {
            "status": "completed",
            "diffs_generated": len(code_diffs),
            "iteration": refinement_iteration
        },
        "code_diffs": code_diffs,
        "is_fixed": is_fixed,
        "refinement_iteration": refinement_iteration,
        "debug_logs": debug_logs,
        "pending_diffs": code_diffs,  # Send to approval node
    }


def _apply_fix_simulation(original_content: str, issue: str) -> str:
    """Simulate applying a fix to code

    In production, this would call LLM with prompt:
    'Fix the following issue in this code: {issue}'

    Args:
        original_content: Original code
        issue: Issue description

    Returns:
        Modified code (simulated)
    """
    # PLACEHOLDER: Simulate a fix
    # In production, call LLM here
    if "security" in issue.lower():
        # Simulate adding input validation
        lines = original_content.splitlines()
        if lines:
            lines.insert(0, "# FIXED: Added input validation")
        return "\n".join(lines)

    if "error handling" in issue.lower():
        # Simulate adding try/except
        return f"try:\n    {original_content}\nexcept Exception as e:\n    logger.error(f'Error: {{e}}')"

    # Default: Add comment
    return f"# TODO: Fix - {issue}\n{original_content}"

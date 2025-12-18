"""Human Approval Node for human-in-the-loop workflow

Pauses workflow execution and waits for human approval of code diffs.
"""

import logging
from typing import Dict
from datetime import datetime
from app.agent.langgraph.schemas.state import QualityGateState, DebugLog

logger = logging.getLogger(__name__)


def human_approval_node(state: QualityGateState) -> Dict:
    """Human Approval node: Wait for human to approve/reject diffs

    This node:
    1. Checks if there are pending diffs
    2. Sets workflow status to "awaiting_approval"
    3. Returns control to frontend with pending diffs
    4. Resumes when approval/rejection received

    CRITICAL: This node implements human-in-the-loop pattern.
    Workflow execution pauses here until user provides input.

    Args:
        state: Current workflow state

    Returns:
        State updates with approval status
    """
    logger.info("🧑 Human Approval Node: Awaiting user decision...")

    pending_diffs = state.get("pending_diffs", [])
    approval_status = state.get("approval_status", "pending")

    # Check if approval already processed
    if approval_status in ["approved", "rejected"]:
        logger.info(f"✅ Approval already processed: {approval_status}")
        return {
            "current_node": "human_approval",
            "workflow_status": "completed" if approval_status == "approved" else "failed",
        }

    # Check if there are diffs to approve
    if not pending_diffs:
        logger.warning("⚠️  No pending diffs for approval - auto-approving")
        return {
            "current_node": "human_approval",
            "approval_status": "approved",
            "workflow_status": "completed",
        }

    # Log statistics
    total_diffs = len(pending_diffs)
    total_changes = sum(len(diff.get("diff_hunks", [])) for diff in pending_diffs)

    logger.info(f"📋 Pending approval:")
    logger.info(f"   Total diffs: {total_diffs}")
    logger.info(f"   Total changes: {total_changes} hunks")

    for idx, diff in enumerate(pending_diffs, 1):
        file_path = diff.get("file_path", "unknown")
        description = diff.get("description", "No description")
        logger.info(f"   {idx}. {file_path}: {description}")

    # Add debug log
    debug_logs = []
    if state.get("enable_debug"):
        debug_logs.append(DebugLog(
            timestamp=datetime.utcnow().isoformat(),
            node="human_approval",
            agent="HumanApprovalNode",
            event_type="result",
            content=f"Awaiting approval for {total_diffs} diffs with {total_changes} changes",
            metadata={
                "pending_diffs_count": total_diffs,
                "total_changes": total_changes,
                "files": [d.get("file_path") for d in pending_diffs]
            },
            token_usage=None
        ))

    # CRITICAL: Set status to awaiting_approval
    # This signals to frontend to show approval UI
    return {
        "current_node": "human_approval",
        "workflow_status": "awaiting_approval",
        "debug_logs": debug_logs,
    }


def process_approval(state: QualityGateState, approved: bool, message: str = "") -> Dict:
    """Process user's approval decision

    This function is called by the API endpoint when user clicks Approve/Reject.

    Args:
        state: Current workflow state
        approved: Whether user approved the changes
        message: Optional message from user

    Returns:
        State updates to resume workflow
    """
    logger.info(f"🧑 Processing user decision: {'APPROVED' if approved else 'REJECTED'}")

    if message:
        logger.info(f"   Message: {message}")

    # Add debug log
    debug_logs = []
    if state.get("enable_debug"):
        debug_logs.append(DebugLog(
            timestamp=datetime.utcnow().isoformat(),
            node="human_approval",
            agent="HumanApprovalNode",
            event_type="result",
            content=f"User {'approved' if approved else 'rejected'} changes",
            metadata={
                "approved": approved,
                "message": message,
                "pending_diffs_count": len(state.get("pending_diffs", []))
            },
            token_usage=None
        ))

    if approved:
        # Apply diffs and complete workflow
        logger.info("✅ Changes approved - applying diffs...")

        pending_diffs = state.get("pending_diffs", [])

        # Move pending diffs to final artifacts
        # In production, this would actually write files to disk
        for diff in pending_diffs:
            logger.info(f"   Applying: {diff.get('file_path')}")

        return {
            "approval_status": "approved",
            "approval_message": message,
            "workflow_status": "completed",
            "pending_diffs": [],  # Clear pending diffs
            "debug_logs": debug_logs,
        }
    else:
        # Rejection - need to refine again or fail
        logger.warning("❌ Changes rejected - will retry refinement")

        return {
            "approval_status": "rejected",
            "approval_message": message,
            "workflow_status": "self_healing",  # Trigger another refinement loop
            "debug_logs": debug_logs,
        }


def create_approval_summary(state: QualityGateState) -> Dict:
    """Create a summary of changes for approval UI

    Args:
        state: Current workflow state

    Returns:
        Dict with summary information for frontend
    """
    pending_diffs = state.get("pending_diffs", [])

    summary = {
        "total_files": len(pending_diffs),
        "total_changes": sum(len(d.get("diff_hunks", [])) for d in pending_diffs),
        "files": [],
        "status": "awaiting_approval"
    }

    for diff in pending_diffs:
        file_summary = {
            "path": diff.get("file_path"),
            "description": diff.get("description"),
            "changes": len(diff.get("diff_hunks", [])),
            "preview": diff.get("diff_hunks", [])[:5],  # First 5 lines of diff
        }
        summary["files"].append(file_summary)

    return summary

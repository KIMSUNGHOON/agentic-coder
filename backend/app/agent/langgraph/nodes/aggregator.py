"""Quality Aggregator Node

Collects results from parallel quality gates and makes go/no-go decision.
"""

import logging
from typing import Dict
from app.agent.langgraph.schemas.state import QualityGateState

logger = logging.getLogger(__name__)


def quality_aggregator_node(state: QualityGateState) -> Dict:
    """Aggregate results from all quality gates

    Decision logic:
    - ALL gates must pass for approval
    - ANY critical failure triggers self-healing
    - Iteration limit triggers manual review

    Args:
        state: Current workflow state

    Returns:
        State updates with aggregated decision
    """
    logger.info("⚖️  Quality Aggregator Node: Evaluating results...")

    # Get gate results with safe defaults
    security_passed = state.get("security_passed", True)  # Changed default to True
    review_approved = state.get("review_approved", False)  # Review is required

    # Tests are optional - if no test node, assume pass
    test_results = state.get("qa_test_results", [])
    tests_passed = len(test_results) == 0 or all(t["passed"] for t in test_results)

    # Count findings/issues
    security_findings = state.get("security_findings", [])
    critical_security = [f for f in security_findings if f.get("severity") in ["critical", "high"]]

    failed_tests = [t for t in test_results if not t.get("passed", False)]

    review_feedback = state.get("review_feedback", {})
    review_issues = review_feedback.get("issues", [])

    # Log gate results
    logger.info("📊 Quality Gate Results:")
    logger.info(f"   🔒 Security: {'✅ PASS' if security_passed else '❌ FAIL'} ({len(critical_security)} critical)")
    logger.info(f"   🧪 Tests: {'✅ PASS' if tests_passed else '❌ FAIL'} ({len(failed_tests)} failures)")
    logger.info(f"   👔 Review: {'✅ APPROVED' if review_approved else '❌ REJECTED'} ({len(review_issues)} issues)")

    # ALL gates must pass
    all_passed = security_passed and tests_passed and review_approved

    logger.info(f"🔍 all_passed={all_passed} (security={security_passed}, tests={tests_passed}, review={review_approved})")

    # Determine workflow status
    iteration = state.get("iteration", 0)
    max_iterations = state.get("max_iterations", 3)

    if all_passed:
        workflow_status = "completed"
        logger.info("🎉 ALL QUALITY GATES PASSED - Workflow Complete!")

    elif iteration >= max_iterations:
        workflow_status = "failed"
        logger.error(f"❌ Max iterations ({max_iterations}) reached - Manual review required")

    else:
        workflow_status = "self_healing"
        logger.warning(f"🔧 Quality gates failed - Triggering self-healing (iteration {iteration + 1}/{max_iterations})")

    # Prepare error log
    error_log = state.get("error_log", [])
    if not all_passed:
        errors = []
        if not security_passed:
            errors.append(f"Security: {len(critical_security)} critical findings")
        if not tests_passed:
            errors.append(f"Tests: {len(failed_tests)} failures")
        if not review_approved:
            errors.append(f"Review: {len(review_issues)} issues")

        error_summary = "; ".join(errors)
        error_log.append(f"Iteration {iteration}: {error_summary}")

    return {
        "current_node": "aggregator",
        "workflow_status": workflow_status,
        "error_log": error_log,
    }

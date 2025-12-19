"""Supervisor Node for task analysis and routing

Analyzes user request using DeepSeek-R1 reasoning and determines optimal workflow path.
Supports both sync and async modes with streaming thinking blocks.
"""

import logging
from typing import Dict, List, Any
from datetime import datetime

from app.agent.langgraph.schemas.state import QualityGateState, TaskType, DebugLog

# Import the enhanced Supervisor Agent
from core.supervisor import SupervisorAgent, supervisor as global_supervisor

logger = logging.getLogger(__name__)


def supervisor_node(state: QualityGateState) -> Dict:
    """Supervisor node: Analyze task and route to appropriate path (sync version)

    Uses rule-based analysis for synchronous execution.
    For streaming DeepSeek-R1 reasoning, use supervisor_node_async.

    Determines:
    1. Task type (implementation, review, testing, security_audit)
    2. Whether to use parallel execution
    3. Maximum iterations for self-healing
    4. Workflow strategy based on complexity

    Args:
        state: Current workflow state

    Returns:
        State updates including supervisor analysis
    """
    logger.info("🎯 Supervisor Node: Analyzing task...")

    user_request = state["user_request"]
    enable_debug = state.get("enable_debug", True)

    debug_logs: List[DebugLog] = []

    # Add start log
    if enable_debug:
        debug_logs.append(DebugLog(
            timestamp=datetime.utcnow().isoformat(),
            node="supervisor",
            agent="SupervisorAgent",
            event_type="thinking",
            content="Starting task analysis...",
            metadata={"mode": "sync", "api_mode": False},
            token_usage=None
        ))

    # Use global supervisor for analysis
    analysis = global_supervisor.analyze_request(user_request)

    # Extract values from analysis
    task_type: TaskType = analysis.get("task_type", "general")
    complexity = analysis.get("complexity", "moderate")
    workflow_strategy = analysis.get("workflow_strategy", "parallel_gates")
    required_agents = analysis.get("required_agents", [])
    max_iterations = analysis.get("max_iterations", 5)
    requires_human_approval = analysis.get("requires_human_approval", False)
    reasoning = analysis.get("reasoning", "")

    # Determine execution mode based on strategy
    if workflow_strategy in ["parallel_gates", "adaptive_loop", "staged_approval"]:
        execution_mode = "parallel"
        parallel_execution = True
    else:
        execution_mode = "sequential"
        parallel_execution = False

    # Add completion log
    if enable_debug:
        debug_logs.append(DebugLog(
            timestamp=datetime.utcnow().isoformat(),
            node="supervisor",
            agent="SupervisorAgent",
            event_type="result",
            content=f"Analysis complete: {task_type} task with {complexity} complexity",
            metadata={
                "complexity": complexity,
                "strategy": workflow_strategy,
                "agents": required_agents,
                "api_used": analysis.get("api_used", False)
            },
            token_usage=None
        ))

    logger.info(f"✅ Task Analysis Complete:")
    logger.info(f"   Task Type: {task_type}")
    logger.info(f"   Complexity: {complexity}")
    logger.info(f"   Workflow Strategy: {workflow_strategy}")
    logger.info(f"   Execution Mode: {execution_mode}")
    logger.info(f"   Max Iterations: {max_iterations}")
    logger.info(f"   Parallel Gates: {parallel_execution}")
    logger.info(f"   Human Approval: {requires_human_approval}")

    return {
        "current_node": "supervisor",
        "task_type": task_type,
        "task_complexity": complexity,
        "workflow_strategy": workflow_strategy,
        "required_agents": required_agents,
        "execution_mode": execution_mode,
        "parallel_execution": parallel_execution,
        "max_iterations": max_iterations,
        "supervisor_analysis": analysis,
        "current_thinking": reasoning,
        "thinking_stream": [reasoning] if reasoning else [],
        "debug_logs": debug_logs,
    }


async def supervisor_node_async(state: QualityGateState) -> Dict:
    """Supervisor node with async DeepSeek-R1 streaming (async version)

    Uses DeepSeek-R1 API for intelligent task analysis with streaming
    <think> blocks. Falls back to rule-based if API unavailable.

    Args:
        state: Current workflow state

    Returns:
        State updates including supervisor analysis and thinking stream
    """
    logger.info("🎯 Supervisor Node (Async): Analyzing task with DeepSeek-R1...")

    user_request = state["user_request"]
    enable_debug = state.get("enable_debug", True)

    debug_logs: List[DebugLog] = []
    thinking_blocks: List[str] = []
    analysis_result = None

    # Add start log
    if enable_debug:
        debug_logs.append(DebugLog(
            timestamp=datetime.utcnow().isoformat(),
            node="supervisor",
            agent="SupervisorAgent",
            event_type="thinking",
            content="Starting DeepSeek-R1 analysis...",
            metadata={"mode": "async", "api_mode": True},
            token_usage=None
        ))

    # Stream analysis from supervisor
    async for update in global_supervisor.analyze_request_async(user_request):
        if update["type"] == "thinking":
            thinking_blocks.append(update["content"])

            if enable_debug:
                debug_logs.append(DebugLog(
                    timestamp=datetime.utcnow().isoformat(),
                    node="supervisor",
                    agent="SupervisorAgent",
                    event_type="thinking",
                    content=update["content"][:500],  # Truncate for log
                    metadata={"is_complete": update.get("is_complete", False)},
                    token_usage=None
                ))

        elif update["type"] == "analysis":
            analysis_result = update["content"]

    # Fallback if no analysis received
    if not analysis_result:
        analysis_result = global_supervisor.analyze_request(user_request)

    # Extract values from analysis
    task_type: TaskType = analysis_result.get("task_type", "general")
    complexity = analysis_result.get("complexity", "moderate")
    workflow_strategy = analysis_result.get("workflow_strategy", "parallel_gates")
    required_agents = analysis_result.get("required_agents", [])
    max_iterations = analysis_result.get("max_iterations", 5)
    requires_human_approval = analysis_result.get("requires_human_approval", False)
    reasoning = analysis_result.get("reasoning", "")
    api_used = analysis_result.get("api_used", False)

    # Determine execution mode based on strategy
    if workflow_strategy in ["parallel_gates", "adaptive_loop", "staged_approval"]:
        execution_mode = "parallel"
        parallel_execution = True
    else:
        execution_mode = "sequential"
        parallel_execution = False

    # Add completion log
    if enable_debug:
        debug_logs.append(DebugLog(
            timestamp=datetime.utcnow().isoformat(),
            node="supervisor",
            agent="SupervisorAgent",
            event_type="result",
            content=f"Analysis complete: {task_type} task with {complexity} complexity",
            metadata={
                "complexity": complexity,
                "strategy": workflow_strategy,
                "agents": required_agents,
                "api_used": api_used,
                "thinking_blocks_count": len(thinking_blocks)
            },
            token_usage=None
        ))

    logger.info(f"✅ Task Analysis Complete (Async):")
    logger.info(f"   Task Type: {task_type}")
    logger.info(f"   Complexity: {complexity}")
    logger.info(f"   Workflow Strategy: {workflow_strategy}")
    logger.info(f"   Execution Mode: {execution_mode}")
    logger.info(f"   Max Iterations: {max_iterations}")
    logger.info(f"   Parallel Gates: {parallel_execution}")
    logger.info(f"   Human Approval: {requires_human_approval}")
    logger.info(f"   API Used: {api_used}")
    logger.info(f"   Thinking Blocks: {len(thinking_blocks)}")

    return {
        "current_node": "supervisor",
        "task_type": task_type,
        "task_complexity": complexity,
        "workflow_strategy": workflow_strategy,
        "required_agents": required_agents,
        "execution_mode": execution_mode,
        "parallel_execution": parallel_execution,
        "max_iterations": max_iterations,
        "supervisor_analysis": analysis_result,
        "current_thinking": reasoning,
        "thinking_stream": thinking_blocks,
        "debug_logs": debug_logs,
    }


def get_supervisor_routing(state: QualityGateState) -> str:
    """Determine next node based on supervisor analysis

    Routes to different paths based on workflow strategy and complexity.

    Args:
        state: Current workflow state

    Returns:
        Next node name for routing
    """
    strategy = state.get("workflow_strategy", "linear")
    requires_approval = state.get("supervisor_analysis", {}).get("requires_human_approval", False)

    # Critical tasks with approval required
    if requires_approval and strategy == "staged_approval":
        logger.info("📍 Routing: staged_approval -> plan_approval")
        return "plan_approval"

    # Route based on task type
    task_type = state.get("task_type", "general")

    if task_type == "security_audit":
        logger.info("📍 Routing: security_audit -> security_gate")
        return "security_gate"
    elif task_type == "testing":
        logger.info("📍 Routing: testing -> qa_gate")
        return "qa_gate"
    elif task_type == "review":
        logger.info("📍 Routing: review -> reviewer")
        return "reviewer"
    else:
        # Default: implementation path
        logger.info("📍 Routing: implementation -> coder")
        return "coder"

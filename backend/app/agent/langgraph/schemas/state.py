"""LangGraph state definitions for quality gate workflows

Implements type-safe state management following LangGraph best practices.
"""

from typing import TypedDict, Literal, List, Dict, Optional, Annotated, Any
from datetime import datetime
from operator import add


# Type aliases for clarity
TaskType = Literal["implementation", "review", "testing", "security_audit", "general"]
WorkflowStatus = Literal["running", "completed", "failed", "self_healing", "blocked", "awaiting_approval"]
Severity = Literal["critical", "high", "medium", "low", "info"]
ApprovalStatus = Literal["pending", "approved", "rejected"]


class SecurityFinding(TypedDict):
    """Security vulnerability finding"""
    severity: Severity
    category: str  # e.g., "path_traversal", "injection", "xss"
    description: str
    file_path: Optional[str]
    line_number: Optional[int]
    recommendation: str


class TestResult(TypedDict):
    """Test execution result"""
    test_name: str
    passed: bool
    duration_ms: float
    error_message: Optional[str]
    coverage_percent: Optional[float]


class ReviewFeedback(TypedDict):
    """Code review feedback"""
    approved: bool
    issues: Annotated[List[str], add]  # FIXED: Use append-only list
    suggestions: Annotated[List[str], add]  # FIXED: Use append-only list
    quality_score: float  # 0.0 - 1.0
    critique: Optional[str]  # Detailed critique text


class Artifact(TypedDict):
    """Generated or modified file artifact"""
    filename: str
    file_path: str
    language: str
    content: str
    size_bytes: int
    checksum: str


class CodeDiff(TypedDict):
    """Code diff for refinement"""
    file_path: str
    original_content: str
    modified_content: str
    diff_hunks: List[str]  # Unified diff format
    description: str


class DebugLog(TypedDict):
    """Debug log entry for observability"""
    timestamp: str
    node: str
    agent: str
    event_type: Literal["thinking", "tool_call", "prompt", "result", "error"]
    content: str
    metadata: Optional[Dict[str, Any]]
    token_usage: Optional[Dict[str, int]]  # {prompt_tokens, completion_tokens, total_tokens}


class QualityGateState(TypedDict, total=False):
    """LangGraph state for production quality gates

    This state flows through all nodes in the workflow.
    Uses Annotated[List, add] for reducer pattern (append-only lists).
    """

    # ==================== Input ====================
    user_request: str
    workspace_root: str
    task_type: TaskType

    # ==================== Context ====================
    previous_context: Optional[Dict]  # Loaded from .ai_context.json
    current_files: List[str]  # Files in workspace
    conversation_history: List[Dict[str, str]]  # CONTEXT IMPROVEMENT: Full conversation history for all agents

    # ==================== Workflow Tracking ====================
    current_node: str  # Current node in graph
    iteration: int  # Current iteration (for self-healing loops)
    max_iterations: int  # Maximum allowed iterations

    # ==================== Agent Outputs ====================
    coder_output: Optional[Dict]  # From CodingAgent node
    security_findings: Annotated[List[SecurityFinding], add]  # Append-only
    qa_test_results: Annotated[List[TestResult], add]  # Append-only
    review_feedback: Optional[ReviewFeedback]  # From ReviewAgent node

    # ==================== Quality Gates ====================
    security_passed: bool  # True if no critical/high findings
    tests_passed: bool  # True if all tests pass
    review_approved: bool  # True if reviewer approves

    # ==================== Execution ====================
    parallel_execution: bool  # Whether to run QA/Security/Review in parallel
    execution_mode: Literal["sequential", "parallel"]

    # ==================== Final Result ====================
    final_artifacts: Annotated[List[Artifact], add]  # All generated/modified files
    workflow_status: WorkflowStatus
    error_log: Annotated[List[str], add]  # All errors encountered

    # ==================== Metadata ====================
    started_at: str  # ISO 8601 timestamp
    completed_at: Optional[str]  # ISO 8601 timestamp
    total_duration_ms: Optional[float]

    # ==================== Self-Healing ====================
    retry_count: int  # Number of self-healing attempts
    last_error: Optional[str]  # Last error that triggered self-healing

    # ==================== Refinement Cycle (NEW) ====================
    refiner_output: Optional[Dict]  # From RefinerAgent node
    code_diffs: Annotated[List[CodeDiff], add]  # All code diffs generated
    is_fixed: bool  # True if refiner successfully fixed issues
    refinement_iteration: int  # Number of refinement loops
    review_results: Annotated[List[str], add]  # CRITICAL: All review results (prevents data loss)
    rca_analysis: Optional[str]  # Root Cause Analysis from DeepSeek-R1
    last_failure_reason: Optional[str]  # Why last iteration failed

    # ==================== Human Approval (NEW) ====================
    approval_status: ApprovalStatus  # Human approval status
    approval_message: Optional[str]  # Message from approver
    pending_diffs: List[CodeDiff]  # Diffs awaiting approval

    # ==================== Observability & Debug (NEW) ====================
    debug_logs: Annotated[List[DebugLog], add]  # All debug logs
    enable_debug: bool  # Whether to collect debug logs
    current_prompt: Optional[str]  # Current prompt being executed
    current_thinking: Optional[str]  # Current agent thinking process

    # ==================== Supervisor Analysis (NEW) ====================
    supervisor_analysis: Optional[Dict[str, Any]]  # Full supervisor analysis result
    thinking_stream: Annotated[List[str], add]  # DeepSeek-R1 <think> blocks (append-only)
    workflow_strategy: Optional[str]  # linear, parallel_gates, adaptive_loop, staged_approval
    required_agents: List[str]  # List of required agent capabilities
    task_complexity: Optional[str]  # simple, moderate, complex, critical

    # ==================== HITL Integration (NEW) ====================
    hitl_request: Optional[Dict[str, Any]]  # Current HITL request
    hitl_checkpoint_type: Optional[str]  # approval, review, edit, choice, confirm
    user_modified_content: Optional[str]  # Content modified by user during HITL
    selected_option: Optional[str]  # User's choice in CHOICE checkpoint

    # ==================== Architecture Design (NEW) ====================
    architecture_design: Optional[Dict[str, Any]]  # Full architecture from Architect Agent
    files_to_create: List[Dict[str, Any]]  # Planned files with priorities
    implementation_phases: List[Dict[str, Any]]  # Phased implementation plan
    parallel_tasks: List[Dict[str, Any]]  # Tasks that can run in parallel
    requires_architecture_review: bool  # Whether architecture needs HITL review

    # ==================== Agent Execution Tracking (NEW) ====================
    agent_execution_times: Dict[str, float]  # {agent_name: seconds}
    current_agent: Optional[str]  # Currently executing agent
    agent_start_time: Optional[str]  # When current agent started
    estimated_total_time: Optional[float]  # ETA in seconds
    completed_agents: List[str]  # List of completed agents
    pending_agents: List[str]  # List of pending agents

    # ==================== Streaming (NEW) ====================
    streaming_content: Optional[str]  # Current streaming content (code being generated)
    streaming_file: Optional[str]  # File being streamed
    streaming_tokens: int  # Number of tokens streamed


def create_initial_state(
    user_request: str,
    workspace_root: str,
    task_type: TaskType = "general",
    max_iterations: int = 5,  # Increased default for better quality
    enable_debug: bool = True,
    conversation_history: List[Dict[str, str]] = None  # CONTEXT IMPROVEMENT: Pass conversation history
) -> QualityGateState:
    """Create initial state for quality gate workflow

    CRITICAL: This function initializes ALL state fields to prevent UnboundLocalError.
    All list fields use empty lists, all optional fields use None.

    Args:
        user_request: User's request/task description
        workspace_root: Absolute path to workspace root
        task_type: Type of task to perform
        max_iterations: Maximum self-healing iterations
        enable_debug: Whether to enable debug logging

    Returns:
        Initialized QualityGateState with all fields properly initialized
    """
    return QualityGateState(
        # Input
        user_request=user_request,
        workspace_root=workspace_root,
        task_type=task_type,

        # Context
        previous_context=None,
        current_files=[],
        conversation_history=conversation_history if conversation_history is not None else [],  # CONTEXT IMPROVEMENT

        # Workflow tracking
        current_node="start",
        iteration=0,
        max_iterations=max_iterations,

        # Agent outputs (CRITICAL: Initialize to prevent UnboundLocalError)
        coder_output=None,
        security_findings=[],
        qa_test_results=[],
        review_feedback=None,

        # Quality gates
        security_passed=False,
        tests_passed=False,
        review_approved=False,

        # Execution
        parallel_execution=True,
        execution_mode="parallel",

        # Final result
        final_artifacts=[],
        workflow_status="running",
        error_log=[],

        # Metadata
        started_at=datetime.utcnow().isoformat(),
        completed_at=None,
        total_duration_ms=None,

        # Self-healing
        retry_count=0,
        last_error=None,

        # Refinement cycle (NEW)
        refiner_output=None,
        code_diffs=[],
        is_fixed=False,
        refinement_iteration=0,
        review_results=[],  # CRITICAL: Initialize to prevent data loss
        rca_analysis=None,
        last_failure_reason=None,

        # Human approval (NEW)
        approval_status="pending",
        approval_message=None,
        pending_diffs=[],

        # Observability & debug (NEW)
        debug_logs=[],
        enable_debug=enable_debug,
        current_prompt=None,
        current_thinking=None,

        # Supervisor analysis (NEW)
        supervisor_analysis=None,
        thinking_stream=[],
        workflow_strategy=None,
        required_agents=[],
        task_complexity=None,

        # HITL integration (NEW)
        hitl_request=None,
        hitl_checkpoint_type=None,
        user_modified_content=None,
        selected_option=None,

        # Architecture design (NEW)
        architecture_design=None,
        files_to_create=[],
        implementation_phases=[],
        parallel_tasks=[],
        requires_architecture_review=False,

        # Agent execution tracking (NEW)
        agent_execution_times={},
        current_agent=None,
        agent_start_time=None,
        estimated_total_time=None,
        completed_agents=[],
        pending_agents=[],

        # Streaming (NEW)
        streaming_content=None,
        streaming_file=None,
        streaming_tokens=0,
    )

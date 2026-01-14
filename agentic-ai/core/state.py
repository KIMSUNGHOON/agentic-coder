"""State Schema for Agentic 2.0

LangGraph state definitions for workflow management:
- AgenticState: Main state schema
- Message tracking
- Task and tool metadata
- Sub-agent coordination
"""

import logging
from typing import Annotated, List, Dict, Any, Optional, TypedDict
from typing_extensions import TypedDict
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum

logger = logging.getLogger(__name__)


class TaskStatus(str, Enum):
    """Status of a task"""
    PENDING = "pending"
    IN_PROGRESS = "in_progress"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"


class WorkflowDomain(str, Enum):
    """Workflow domain types"""
    CODING = "coding"
    RESEARCH = "research"
    DATA = "data"
    GENERAL = "general"


@dataclass
class Message:
    """Represents a message in the conversation"""
    role: str  # "user", "assistant", "system"
    content: str
    timestamp: datetime = field(default_factory=datetime.now)
    metadata: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for serialization"""
        return {
            "role": self.role,
            "content": self.content,
            "timestamp": self.timestamp.isoformat(),
            "metadata": self.metadata,
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "Message":
        """Create from dictionary"""
        return cls(
            role=data["role"],
            content=data["content"],
            timestamp=datetime.fromisoformat(data["timestamp"]),
            metadata=data.get("metadata", {}),
        )


@dataclass
class ToolCall:
    """Represents a tool execution"""
    tool_name: str
    parameters: Dict[str, Any]
    result: Optional[Any] = None
    success: bool = False
    error: Optional[str] = None
    timestamp: datetime = field(default_factory=datetime.now)
    duration_ms: Optional[float] = None

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for serialization"""
        return {
            "tool_name": self.tool_name,
            "parameters": self.parameters,
            "result": self.result,
            "success": self.success,
            "error": self.error,
            "timestamp": self.timestamp.isoformat(),
            "duration_ms": self.duration_ms,
        }


@dataclass
class SubAgentInfo:
    """Information about a spawned sub-agent"""
    agent_id: str
    agent_type: str
    task: str
    status: TaskStatus
    created_at: datetime = field(default_factory=datetime.now)
    completed_at: Optional[datetime] = None
    result: Optional[Any] = None
    error: Optional[str] = None

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for serialization"""
        return {
            "agent_id": self.agent_id,
            "agent_type": self.agent_type,
            "task": self.task,
            "status": self.status.value,
            "created_at": self.created_at.isoformat(),
            "completed_at": self.completed_at.isoformat() if self.completed_at else None,
            "result": self.result,
            "error": self.error,
        }


class AgenticState(TypedDict, total=False):
    """Main state schema for LangGraph workflows

    This state is passed through all nodes in the workflow graph.
    Uses TypedDict for LangGraph compatibility.

    Key sections:
    - messages: Conversation history
    - task: Current task information
    - workflow: Workflow metadata
    - tools: Tool execution tracking
    - sub_agents: Sub-agent coordination
    - context: Shared context data
    """

    # === Conversation ===
    messages: Annotated[List[Dict[str, Any]], "add_messages"]  # Message history
    current_message: Optional[str]  # Current user message being processed

    # === Task Information ===
    task_id: str  # Unique task identifier
    task_description: str  # Human-readable task description
    task_status: str  # TaskStatus enum value
    task_result: Optional[Any]  # Final task result
    task_error: Optional[str]  # Error if task failed

    # === Workflow Metadata ===
    workflow_domain: str  # WorkflowDomain enum value (coding, research, data, general)
    workflow_type: str  # Workflow execution strategy
    iteration: int  # Current iteration number
    max_iterations: int  # Maximum iterations allowed
    start_time: str  # ISO format timestamp
    end_time: Optional[str]  # ISO format timestamp when completed

    # === Tool Execution ===
    tool_calls: List[Dict[str, Any]]  # History of tool calls
    pending_tool_calls: List[Dict[str, Any]]  # Tools waiting to execute
    last_tool_result: Optional[Dict[str, Any]]  # Most recent tool result

    # === Sub-Agent Coordination ===
    sub_agents: List[Dict[str, Any]]  # Active sub-agents
    sub_agent_results: List[Dict[str, Any]]  # Completed sub-agent results
    requires_sub_agents: bool  # Whether task needs sub-agents

    # === Context and Memory ===
    workspace: Optional[str]  # Working directory path
    context: Dict[str, Any]  # Shared context data
    memory: Dict[str, Any]  # Persistent memory across iterations

    # === Routing and Decisions ===
    next_node: Optional[str]  # Next node to execute (for conditional routing)
    should_continue: bool  # Whether to continue iteration
    confidence: float  # Confidence in current classification/decision

    # === Error Handling ===
    errors: List[Dict[str, Any]]  # Error history
    retry_count: int  # Number of retries attempted


# Reducer functions for state updates

def add_messages(existing: List[Dict[str, Any]], new: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    """Append new messages to existing messages

    This is a reducer function for the 'messages' field.
    """
    return existing + new


def add_tool_calls(existing: List[Dict[str, Any]], new: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    """Append new tool calls to existing tool calls"""
    return existing + new


def add_sub_agents(existing: List[Dict[str, Any]], new: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    """Append new sub-agents to existing sub-agents"""
    return existing + new


def merge_context(existing: Dict[str, Any], new: Dict[str, Any]) -> Dict[str, Any]:
    """Merge new context into existing context"""
    merged = existing.copy()
    merged.update(new)
    return merged


# State initialization

def create_initial_state(
    task_description: str,
    task_id: str,
    workflow_domain: WorkflowDomain,
    workspace: Optional[str] = None,
    max_iterations: int = 10,
) -> AgenticState:
    """Create initial state for a new workflow

    Args:
        task_description: Description of the task
        task_id: Unique task identifier
        workflow_domain: Workflow domain (coding, research, data, general)
        workspace: Working directory path (optional)
        max_iterations: Maximum iterations (default: 10)

    Returns:
        Initialized AgenticState
    """
    return AgenticState(
        # Conversation
        messages=[],
        current_message=task_description,

        # Task
        task_id=task_id,
        task_description=task_description,
        task_status=TaskStatus.PENDING.value,
        task_result=None,
        task_error=None,

        # Workflow
        workflow_domain=workflow_domain.value,
        workflow_type="adaptive",
        iteration=0,
        max_iterations=max_iterations,
        start_time=datetime.now().isoformat(),
        end_time=None,

        # Tools
        tool_calls=[],
        pending_tool_calls=[],
        last_tool_result=None,

        # Sub-agents
        sub_agents=[],
        sub_agent_results=[],
        requires_sub_agents=False,

        # Context
        workspace=workspace,
        context={},
        memory={},

        # Routing
        next_node=None,
        should_continue=True,
        confidence=1.0,

        # Errors
        errors=[],
        retry_count=0,
    )


def update_task_status(state: AgenticState, status: TaskStatus) -> AgenticState:
    """Update task status in state

    Args:
        state: Current state
        status: New status

    Returns:
        Updated state
    """
    state["task_status"] = status.value

    if status in [TaskStatus.COMPLETED, TaskStatus.FAILED, TaskStatus.CANCELLED]:
        state["end_time"] = datetime.now().isoformat()
        state["should_continue"] = False

    return state


def add_error(state: AgenticState, error: str, context: Optional[Dict[str, Any]] = None) -> AgenticState:
    """Add error to state

    Args:
        state: Current state
        error: Error message
        context: Additional error context

    Returns:
        Updated state
    """
    error_entry = {
        "message": error,
        "timestamp": datetime.now().isoformat(),
        "iteration": state["iteration"],
        "context": context or {},
    }

    state["errors"].append(error_entry)
    logger.error(f"State error: {error}")

    return state


def increment_iteration(state: AgenticState) -> AgenticState:
    """Increment iteration counter

    Args:
        state: Current state

    Returns:
        Updated state
    """
    state["iteration"] += 1

    # Check iteration limit
    if state["iteration"] >= state["max_iterations"]:
        logger.warning(f"Reached maximum iterations: {state['max_iterations']}")
        state["should_continue"] = False
        state["task_status"] = TaskStatus.FAILED.value
        state["task_error"] = f"Exceeded maximum iterations ({state['max_iterations']})"

    return state


# State validation

def validate_state(state: AgenticState) -> List[str]:
    """Validate state structure

    Args:
        state: State to validate

    Returns:
        List of validation errors (empty if valid)
    """
    errors = []

    # Required fields
    required_fields = [
        "task_id",
        "task_description",
        "task_status",
        "workflow_domain",
        "iteration",
        "max_iterations",
    ]

    for field in required_fields:
        if field not in state:
            errors.append(f"Missing required field: {field}")

    # Type checks
    if "iteration" in state and not isinstance(state["iteration"], int):
        errors.append(f"Invalid type for 'iteration': expected int, got {type(state['iteration'])}")

    if "max_iterations" in state and not isinstance(state["max_iterations"], int):
        errors.append(f"Invalid type for 'max_iterations': expected int")

    # Value checks
    if "iteration" in state and state["iteration"] < 0:
        errors.append(f"Invalid value for 'iteration': must be >= 0")

    if "max_iterations" in state and state["max_iterations"] < 1:
        errors.append(f"Invalid value for 'max_iterations': must be >= 1")

    return errors

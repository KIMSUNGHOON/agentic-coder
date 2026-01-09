"""HITL Data Models

Defines all data structures for the Human-in-the-Loop system.
"""

from enum import Enum
from typing import Any, Dict, List, Optional
from datetime import datetime
from pydantic import BaseModel, Field
import uuid


class HITLCheckpointType(str, Enum):
    """Types of HITL checkpoints"""

    APPROVAL = "approval"      # Simple approve/reject
    REVIEW = "review"          # Review with feedback
    EDIT = "edit"              # Direct content editing
    CHOICE = "choice"          # Select from options
    CONFIRM = "confirm"        # Confirmation for dangerous actions


class HITLStatus(str, Enum):
    """Status of HITL request"""

    PENDING = "pending"
    APPROVED = "approved"
    REJECTED = "rejected"
    MODIFIED = "modified"
    SELECTED = "selected"
    CANCELLED = "cancelled"
    TIMEOUT = "timeout"


class HITLAction(str, Enum):
    """Actions user can take on HITL request"""

    APPROVE = "approve"
    REJECT = "reject"
    EDIT = "edit"
    RETRY = "retry"
    SELECT = "select"
    CONFIRM = "confirm"
    CANCEL = "cancel"


class ChoiceOption(BaseModel):
    """Option for choice-type HITL checkpoint"""

    option_id: str = Field(..., description="Unique identifier for this option")
    title: str = Field(..., description="Display title")
    description: str = Field(..., description="Detailed description")
    preview: Optional[str] = Field(None, description="Preview content (code, text, etc.)")
    pros: List[str] = Field(default_factory=list, description="Advantages of this option")
    cons: List[str] = Field(default_factory=list, description="Disadvantages of this option")
    recommended: bool = Field(False, description="Whether this is the recommended option")
    metadata: Dict[str, Any] = Field(default_factory=dict)


class HITLContent(BaseModel):
    """Content associated with HITL request"""

    # For code review/edit
    code: Optional[str] = Field(None, description="Code content")
    language: Optional[str] = Field(None, description="Programming language")
    filename: Optional[str] = Field(None, description="File name")

    # For workflow plan review
    workflow_plan: Optional[Dict[str, Any]] = Field(None, description="Workflow plan to review")

    # For choices
    options: List[ChoiceOption] = Field(default_factory=list, description="Options for choice type")

    # For diffs
    original: Optional[str] = Field(None, description="Original content")
    modified: Optional[str] = Field(None, description="Modified content")
    diff: Optional[str] = Field(None, description="Unified diff")

    # For confirmation
    action_description: Optional[str] = Field(None, description="Description of dangerous action")
    risks: List[str] = Field(default_factory=list, description="Potential risks")

    # Generic content
    summary: Optional[str] = Field(None, description="Summary of what needs review")
    details: Optional[Dict[str, Any]] = Field(None, description="Additional details")


class HITLRequest(BaseModel):
    """Request for human input at a checkpoint"""

    request_id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    workflow_id: str = Field(..., description="Associated workflow ID")
    stage_id: str = Field(..., description="Current workflow stage ID")
    agent_id: Optional[str] = Field(None, description="Agent that triggered this request")

    checkpoint_type: HITLCheckpointType = Field(..., description="Type of checkpoint")
    title: str = Field(..., description="Display title for UI")
    description: str = Field(..., description="Detailed description of what needs review")

    content: HITLContent = Field(..., description="Content to review/approve")

    # UI hints
    allow_skip: bool = Field(False, description="Whether user can skip this checkpoint")
    timeout_seconds: Optional[int] = Field(None, description="Auto-timeout (None = no timeout)")
    priority: str = Field("normal", description="Priority level: low, normal, high, critical")

    # Timestamps
    created_at: datetime = Field(default_factory=datetime.utcnow)
    expires_at: Optional[datetime] = Field(None)

    # Status tracking
    status: HITLStatus = Field(default=HITLStatus.PENDING)

    # Response details (populated after response is submitted)
    response_action: Optional[str] = Field(None, description="Action taken by user")
    response_feedback: Optional[str] = Field(None, description="User's feedback")

    class Config:
        json_encoders = {
            datetime: lambda v: v.isoformat()
        }


class HITLResponse(BaseModel):
    """User's response to HITL request"""

    request_id: str = Field(..., description="ID of the request being responded to")
    action: HITLAction = Field(..., description="Action taken by user")

    # Feedback
    feedback: Optional[str] = Field(None, description="User's feedback or comments")

    # For edit action
    modified_content: Optional[str] = Field(None, description="User's edited content")

    # For choice action
    selected_option: Optional[str] = Field(None, description="ID of selected option")

    # For retry action
    retry_instructions: Optional[str] = Field(None, description="Instructions for retry")

    # Timestamps
    responded_at: datetime = Field(default_factory=datetime.utcnow)

    class Config:
        json_encoders = {
            datetime: lambda v: v.isoformat()
        }


class HITLEvent(BaseModel):
    """WebSocket event for HITL communication"""

    event_type: str = Field(..., description="Event type: request, response, timeout, cancelled")
    workflow_id: str
    request_id: Optional[str] = None
    data: Dict[str, Any] = Field(default_factory=dict)
    timestamp: datetime = Field(default_factory=datetime.utcnow)

    class Config:
        json_encoders = {
            datetime: lambda v: v.isoformat()
        }


# Predefined HITL request templates
class HITLTemplates:
    """Templates for common HITL requests"""

    @staticmethod
    def workflow_plan_approval(
        workflow_id: str,
        stage_id: str,
        plan: Dict[str, Any],
        agent_id: str = "supervisor"
    ) -> HITLRequest:
        """Create HITL request for workflow plan approval"""
        return HITLRequest(
            workflow_id=workflow_id,
            stage_id=stage_id,
            agent_id=agent_id,
            checkpoint_type=HITLCheckpointType.APPROVAL,
            title="Workflow Plan Review",
            description="Review the proposed workflow plan before execution begins.",
            content=HITLContent(
                workflow_plan=plan,
                summary=f"Proposed {len(plan.get('stages', []))} stage workflow"
            ),
            priority="high"
        )

    @staticmethod
    def code_review(
        workflow_id: str,
        stage_id: str,
        code: str,
        filename: str,
        language: str,
        agent_id: str = "coder"
    ) -> HITLRequest:
        """Create HITL request for code review"""
        return HITLRequest(
            workflow_id=workflow_id,
            stage_id=stage_id,
            agent_id=agent_id,
            checkpoint_type=HITLCheckpointType.REVIEW,
            title=f"Code Review: {filename}",
            description="Review the generated code before applying.",
            content=HITLContent(
                code=code,
                language=language,
                filename=filename,
                summary=f"Generated {len(code.splitlines())} lines of {language} code"
            )
        )

    @staticmethod
    def implementation_choice(
        workflow_id: str,
        stage_id: str,
        options: List[ChoiceOption],
        context: str,
        agent_id: str = "supervisor"
    ) -> HITLRequest:
        """Create HITL request for implementation choice"""
        return HITLRequest(
            workflow_id=workflow_id,
            stage_id=stage_id,
            agent_id=agent_id,
            checkpoint_type=HITLCheckpointType.CHOICE,
            title="Implementation Decision Required",
            description=context,
            content=HITLContent(
                options=options,
                summary=f"Choose from {len(options)} implementation options"
            ),
            priority="high"
        )

    @staticmethod
    def dangerous_action_confirm(
        workflow_id: str,
        stage_id: str,
        action: str,
        risks: List[str],
        agent_id: str = "executor"
    ) -> HITLRequest:
        """Create HITL request for dangerous action confirmation"""
        return HITLRequest(
            workflow_id=workflow_id,
            stage_id=stage_id,
            agent_id=agent_id,
            checkpoint_type=HITLCheckpointType.CONFIRM,
            title="Confirmation Required",
            description=f"The following action requires your confirmation: {action}",
            content=HITLContent(
                action_description=action,
                risks=risks,
                summary="This action may have irreversible effects"
            ),
            priority="critical"
        )

    @staticmethod
    def final_approval(
        workflow_id: str,
        stage_id: str,
        artifacts: List[Dict[str, Any]],
        summary: str,
        agent_id: str = "aggregator"
    ) -> HITLRequest:
        """Create HITL request for final result approval"""
        return HITLRequest(
            workflow_id=workflow_id,
            stage_id=stage_id,
            agent_id=agent_id,
            checkpoint_type=HITLCheckpointType.APPROVAL,
            title="Final Review",
            description="Review and approve the final results before applying changes.",
            content=HITLContent(
                details={"artifacts": artifacts},
                summary=summary
            ),
            priority="high"
        )

    @staticmethod
    def ask_human(
        workflow_id: str,
        stage_id: str,
        question: str,
        reason: str,
        options: Optional[List[str]] = None,
        agent_id: str = "supervisor"
    ) -> HITLRequest:
        """Create HITL request for asking human a question (Tool Use pattern)

        This is the key interface for LLM-driven ask_human tool.
        LLM calls this when it needs clarification or important decisions.

        Args:
            workflow_id: Current workflow ID
            stage_id: Current stage ID
            question: Question to ask the human
            reason: Why the LLM is asking (for context)
            options: Optional list of suggested answers
            agent_id: Agent asking the question

        Returns:
            HITLRequest configured for asking question
        """
        # Build choice options if provided
        choice_options = []
        if options:
            for i, option in enumerate(options):
                choice_options.append(ChoiceOption(
                    option_id=f"option_{i}",
                    title=option,
                    description=f"Select: {option}",
                    recommended=(i == 0)  # First option as default recommendation
                ))

        return HITLRequest(
            workflow_id=workflow_id,
            stage_id=stage_id,
            agent_id=agent_id,
            checkpoint_type=HITLCheckpointType.CHOICE if options else HITLCheckpointType.REVIEW,
            title="Question from AI",
            description=f"{question}\n\n**Why I'm asking:** {reason}",
            content=HITLContent(
                options=choice_options,
                summary=question,
                details={"reason": reason, "agent": agent_id}
            ),
            allow_skip=False,  # Questions require answers
            priority="high"
        )

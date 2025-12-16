"""Pydantic models for API requests and responses."""
from pydantic import BaseModel, Field
from typing import Optional, List, Dict, Any


class ChatMessage(BaseModel):
    """Chat message model."""
    role: str = Field(..., description="Role of the message sender (user/assistant/system)")
    content: str = Field(..., description="Content of the message")


class ArtifactContext(BaseModel):
    """Artifact context for continuing work."""
    filename: str = Field(..., description="Artifact filename")
    language: str = Field(..., description="Programming language")
    content: str = Field(..., description="Artifact content")


class ConversationContext(BaseModel):
    """Context from previous conversation turns."""
    messages: List[ChatMessage] = Field(default_factory=list, description="Previous messages")
    artifacts: List[ArtifactContext] = Field(default_factory=list, description="Generated artifacts")
    last_task_type: Optional[str] = Field(None, description="Last detected task type")
    review_status: Optional[str] = Field(None, description="Last review status")


class ChatRequest(BaseModel):
    """Chat request model."""
    message: str = Field(..., description="User message")
    session_id: str = Field(default="default", description="Session identifier")
    task_type: str = Field(default="coding", description="Task type (reasoning/coding)")
    system_prompt: Optional[str] = Field(None, description="Optional system prompt")
    stream: bool = Field(default=False, description="Whether to stream the response")
    context: Optional[ConversationContext] = Field(None, description="Previous conversation context")


class ChatResponse(BaseModel):
    """Chat response model."""
    response: str = Field(..., description="Agent's response")
    session_id: str = Field(..., description="Session identifier")
    task_type: str = Field(..., description="Task type used")


class AgentStatus(BaseModel):
    """Agent status model."""
    session_id: str = Field(..., description="Session identifier")
    message_count: int = Field(..., description="Number of messages in history")
    history: List[ChatMessage] = Field(..., description="Conversation history")


class ModelInfo(BaseModel):
    """Model information."""
    name: str = Field(..., description="Model name")
    endpoint: str = Field(..., description="Model endpoint")
    type: str = Field(..., description="Model type (reasoning/coding)")


class ModelsResponse(BaseModel):
    """Models list response."""
    models: List[ModelInfo] = Field(..., description="Available models")


class ErrorResponse(BaseModel):
    """Error response model."""
    error: str = Field(..., description="Error message")
    detail: Optional[str] = Field(None, description="Detailed error information")

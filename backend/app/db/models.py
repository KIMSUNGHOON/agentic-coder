"""SQLAlchemy models for conversation persistence."""
import json
from datetime import datetime
from typing import List, Optional, Dict, Any
from sqlalchemy import Column, Integer, String, Text, DateTime, ForeignKey, Boolean, JSON, Index
from sqlalchemy.orm import relationship
from .database import Base


class Conversation(Base):
    """Conversation model - represents a chat/workflow session."""
    __tablename__ = "conversations"

    id = Column(Integer, primary_key=True, index=True)
    session_id = Column(String(100), unique=True, index=True, nullable=False)
    title = Column(String(500), default="New Conversation")
    mode = Column(String(20), default="chat")  # "chat" or "workflow"
    task_type = Column(String(30), default="auto")  # "auto", "question", "codegen"
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    # Session configuration (persisted for multi-user support)
    workspace_path = Column(String(500), nullable=True)  # User's workspace directory
    framework = Column(String(20), default="standard")  # "standard" or "deepagents"

    # Workflow state (if mode == "workflow")
    workflow_state = Column(JSON, nullable=True)  # Store checklist, artifacts, etc.

    # Relationships
    messages = relationship("Message", back_populates="conversation", cascade="all, delete-orphan")
    artifacts = relationship("Artifact", back_populates="conversation", cascade="all, delete-orphan")

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary."""
        return {
            "id": self.id,
            "session_id": self.session_id,
            "title": self.title,
            "mode": self.mode,
            "task_type": self.task_type,
            "created_at": self.created_at.isoformat() if self.created_at else None,
            "updated_at": self.updated_at.isoformat() if self.updated_at else None,
            "message_count": len(self.messages) if self.messages else 0,
            "workflow_state": self.workflow_state,
            "workspace_path": self.workspace_path,
            "framework": self.framework,
        }


class Message(Base):
    """Message model - represents a single message in a conversation."""
    __tablename__ = "messages"

    id = Column(Integer, primary_key=True, index=True)
    conversation_id = Column(Integer, ForeignKey("conversations.id"), nullable=False)
    role = Column(String(20), nullable=False)  # "user", "assistant", "system"
    content = Column(Text, nullable=False)
    agent_name = Column(String(50), nullable=True)  # For workflow: "PlanningAgent", "CodingAgent", etc.
    message_type = Column(String(30), nullable=True)  # "thinking", "artifact", "task_completed", etc.
    meta_info = Column(JSON, nullable=True)  # Additional data (checklist, task_result, etc.)
    created_at = Column(DateTime, default=datetime.utcnow)

    # Relationships
    conversation = relationship("Conversation", back_populates="messages")

    # Indexes for performance
    __table_args__ = (
        # Composite index for listing messages in chronological order
        Index('idx_message_conversation_created', 'conversation_id', 'created_at'),

        # Index for filtering by agent
        Index('idx_message_agent_name', 'agent_name'),

        # Composite index for role-based queries within conversation
        Index('idx_message_conversation_role', 'conversation_id', 'role'),
    )

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary."""
        return {
            "id": self.id,
            "role": self.role,
            "content": self.content,
            "agent_name": self.agent_name,
            "message_type": self.message_type,
            "meta_info": self.meta_info,
            "created_at": self.created_at.isoformat() if self.created_at else None,
        }


class Artifact(Base):
    """Artifact model - represents generated code files."""
    __tablename__ = "artifacts"

    id = Column(Integer, primary_key=True, index=True)
    conversation_id = Column(Integer, ForeignKey("conversations.id"), nullable=False)
    filename = Column(String(255), nullable=False)
    language = Column(String(50), nullable=False)
    content = Column(Text, nullable=False)
    task_num = Column(Integer, nullable=True)  # Which task generated this
    version = Column(Integer, default=1)  # For tracking revisions
    created_at = Column(DateTime, default=datetime.utcnow)

    # Relationships
    conversation = relationship("Conversation", back_populates="artifacts")

    # Indexes for performance
    __table_args__ = (
        # Index for searching by filename
        Index('idx_artifact_filename', 'filename'),

        # Composite index for finding specific files within a conversation
        Index('idx_artifact_conversation_filename', 'conversation_id', 'filename'),

        # Index for ordering artifacts by creation time
        Index('idx_artifact_conversation_created', 'conversation_id', 'created_at'),
    )

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary."""
        return {
            "id": self.id,
            "filename": self.filename,
            "language": self.language,
            "content": self.content,
            "task_num": self.task_num,
            "version": self.version,
            "created_at": self.created_at.isoformat() if self.created_at else None,
        }

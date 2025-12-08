"""SQLAlchemy models for conversation persistence."""
import json
from datetime import datetime
from typing import List, Optional, Dict, Any
from sqlalchemy import Column, Integer, String, Text, DateTime, ForeignKey, Boolean, JSON
from sqlalchemy.orm import relationship
from .database import Base


class Conversation(Base):
    """Conversation model - represents a chat/workflow session."""
    __tablename__ = "conversations"

    id = Column(Integer, primary_key=True, index=True)
    session_id = Column(String(100), unique=True, index=True, nullable=False)
    title = Column(String(500), default="New Conversation")
    mode = Column(String(20), default="chat")  # "chat" or "workflow"
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

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
            "created_at": self.created_at.isoformat() if self.created_at else None,
            "updated_at": self.updated_at.isoformat() if self.updated_at else None,
            "message_count": len(self.messages) if self.messages else 0,
            "workflow_state": self.workflow_state,
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

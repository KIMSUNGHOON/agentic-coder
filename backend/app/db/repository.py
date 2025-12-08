"""Repository for conversation database operations."""
import logging
from datetime import datetime
from typing import List, Optional, Dict, Any
from sqlalchemy.orm import Session
from sqlalchemy import desc
from .models import Conversation, Message, Artifact

logger = logging.getLogger(__name__)


class ConversationRepository:
    """Repository for conversation CRUD operations."""

    def __init__(self, db: Session):
        """Initialize repository with database session."""
        self.db = db

    # Conversation operations
    def create_conversation(
        self,
        session_id: str,
        title: str = "New Conversation",
        mode: str = "chat"
    ) -> Conversation:
        """Create a new conversation."""
        conversation = Conversation(
            session_id=session_id,
            title=title,
            mode=mode
        )
        self.db.add(conversation)
        self.db.commit()
        self.db.refresh(conversation)
        logger.info(f"Created conversation: {session_id}")
        return conversation

    def get_conversation(self, session_id: str) -> Optional[Conversation]:
        """Get conversation by session_id."""
        return self.db.query(Conversation).filter(
            Conversation.session_id == session_id
        ).first()

    def get_conversation_by_id(self, conversation_id: int) -> Optional[Conversation]:
        """Get conversation by ID."""
        return self.db.query(Conversation).filter(
            Conversation.id == conversation_id
        ).first()

    def get_or_create_conversation(
        self,
        session_id: str,
        title: str = "New Conversation",
        mode: str = "chat"
    ) -> Conversation:
        """Get existing conversation or create new one."""
        conversation = self.get_conversation(session_id)
        if not conversation:
            conversation = self.create_conversation(session_id, title, mode)
        return conversation

    def list_conversations(
        self,
        limit: int = 50,
        offset: int = 0,
        mode: Optional[str] = None
    ) -> List[Conversation]:
        """List conversations ordered by updated_at."""
        query = self.db.query(Conversation)
        if mode:
            query = query.filter(Conversation.mode == mode)
        return query.order_by(desc(Conversation.updated_at)).offset(offset).limit(limit).all()

    def update_conversation(
        self,
        session_id: str,
        title: Optional[str] = None,
        workflow_state: Optional[Dict[str, Any]] = None
    ) -> Optional[Conversation]:
        """Update conversation."""
        conversation = self.get_conversation(session_id)
        if conversation:
            if title is not None:
                conversation.title = title
            if workflow_state is not None:
                conversation.workflow_state = workflow_state
            conversation.updated_at = datetime.utcnow()
            self.db.commit()
            self.db.refresh(conversation)
        return conversation

    def delete_conversation(self, session_id: str) -> bool:
        """Delete conversation and all related data."""
        conversation = self.get_conversation(session_id)
        if conversation:
            self.db.delete(conversation)
            self.db.commit()
            logger.info(f"Deleted conversation: {session_id}")
            return True
        return False

    # Message operations
    def add_message(
        self,
        session_id: str,
        role: str,
        content: str,
        agent_name: Optional[str] = None,
        message_type: Optional[str] = None,
        meta_info: Optional[Dict[str, Any]] = None
    ) -> Optional[Message]:
        """Add a message to a conversation."""
        conversation = self.get_conversation(session_id)
        if not conversation:
            conversation = self.create_conversation(session_id)

        message = Message(
            conversation_id=conversation.id,
            role=role,
            content=content,
            agent_name=agent_name,
            message_type=message_type,
            meta_info=meta_info
        )
        self.db.add(message)

        # Update conversation title from first user message
        if role == "user" and len(conversation.messages) == 0:
            # Use first 50 chars of message as title
            conversation.title = content[:50] + ("..." if len(content) > 50 else "")

        conversation.updated_at = datetime.utcnow()
        self.db.commit()
        self.db.refresh(message)
        return message

    def get_messages(
        self,
        session_id: str,
        limit: Optional[int] = None
    ) -> List[Message]:
        """Get messages for a conversation."""
        conversation = self.get_conversation(session_id)
        if not conversation:
            return []

        query = self.db.query(Message).filter(
            Message.conversation_id == conversation.id
        ).order_by(Message.created_at)

        if limit:
            query = query.limit(limit)

        return query.all()

    def clear_messages(self, session_id: str) -> bool:
        """Clear all messages in a conversation."""
        conversation = self.get_conversation(session_id)
        if conversation:
            self.db.query(Message).filter(
                Message.conversation_id == conversation.id
            ).delete()
            self.db.commit()
            return True
        return False

    # Artifact operations
    def add_artifact(
        self,
        session_id: str,
        filename: str,
        language: str,
        content: str,
        task_num: Optional[int] = None
    ) -> Optional[Artifact]:
        """Add an artifact to a conversation."""
        conversation = self.get_conversation(session_id)
        if not conversation:
            return None

        # Check if artifact with same filename exists (for versioning)
        existing = self.db.query(Artifact).filter(
            Artifact.conversation_id == conversation.id,
            Artifact.filename == filename
        ).order_by(desc(Artifact.version)).first()

        version = (existing.version + 1) if existing else 1

        artifact = Artifact(
            conversation_id=conversation.id,
            filename=filename,
            language=language,
            content=content,
            task_num=task_num,
            version=version
        )
        self.db.add(artifact)
        self.db.commit()
        self.db.refresh(artifact)
        return artifact

    def get_artifacts(
        self,
        session_id: str,
        latest_only: bool = True
    ) -> List[Artifact]:
        """Get artifacts for a conversation."""
        conversation = self.get_conversation(session_id)
        if not conversation:
            return []

        if latest_only:
            # Get only the latest version of each file
            from sqlalchemy import func
            subquery = self.db.query(
                Artifact.filename,
                func.max(Artifact.version).label("max_version")
            ).filter(
                Artifact.conversation_id == conversation.id
            ).group_by(Artifact.filename).subquery()

            return self.db.query(Artifact).join(
                subquery,
                (Artifact.filename == subquery.c.filename) &
                (Artifact.version == subquery.c.max_version)
            ).filter(
                Artifact.conversation_id == conversation.id
            ).all()
        else:
            return self.db.query(Artifact).filter(
                Artifact.conversation_id == conversation.id
            ).order_by(Artifact.created_at).all()

    def delete_artifacts(self, session_id: str) -> bool:
        """Delete all artifacts in a conversation."""
        conversation = self.get_conversation(session_id)
        if conversation:
            self.db.query(Artifact).filter(
                Artifact.conversation_id == conversation.id
            ).delete()
            self.db.commit()
            return True
        return False

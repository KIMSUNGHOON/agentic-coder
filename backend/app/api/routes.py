"""API routes for the coding agent."""
import logging
import json
from fastapi import APIRouter, HTTPException, Depends
from fastapi.responses import StreamingResponse
from sqlalchemy.orm import Session

from app.api.models import (
    ChatRequest,
    ChatResponse,
    AgentStatus,
    ModelsResponse,
    ModelInfo,
    ErrorResponse,
    ChatMessage
)
from app.agent.agent_manager import agent_manager
from app.agent.workflow_manager import workflow_manager
from app.core.config import settings
from app.db import get_db, ConversationRepository

logger = logging.getLogger(__name__)
router = APIRouter()


@router.post("/chat", response_model=ChatResponse)
async def chat(request: ChatRequest):
    """Process a chat message.

    Args:
        request: Chat request with message and session info

    Returns:
        Chat response with agent's message
    """
    try:
        # Get or create agent for session
        agent = agent_manager.get_or_create_agent(request.session_id)

        # Process message (non-streaming)
        if not request.stream:
            response = await agent.process_message(
                user_message=request.message,
                task_type=request.task_type,
                system_prompt=request.system_prompt
            )

            return ChatResponse(
                response=response,
                session_id=request.session_id,
                task_type=request.task_type
            )
        else:
            raise HTTPException(
                status_code=400,
                detail="Use /chat/stream endpoint for streaming responses"
            )

    except Exception as e:
        logger.error(f"Error in chat endpoint: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/chat/stream")
async def chat_stream(request: ChatRequest):
    """Stream a chat response.

    Args:
        request: Chat request with message and session info

    Returns:
        Streaming response with agent's message chunks
    """
    try:
        # Get or create agent for session
        agent = agent_manager.get_or_create_agent(request.session_id)

        # Create streaming response
        async def generate():
            try:
                async for chunk in agent.stream_message(
                    user_message=request.message,
                    task_type=request.task_type,
                    system_prompt=request.system_prompt
                ):
                    yield chunk
            except Exception as e:
                logger.error(f"Error streaming response: {e}")
                yield f"\n\nError: {str(e)}"

        return StreamingResponse(
            generate(),
            media_type="text/event-stream"
        )

    except Exception as e:
        logger.error(f"Error in chat stream endpoint: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/agent/status/{session_id}", response_model=AgentStatus)
async def get_agent_status(session_id: str):
    """Get agent status for a session.

    Args:
        session_id: Session identifier

    Returns:
        Agent status with conversation history
    """
    try:
        agent = agent_manager.get_or_create_agent(session_id)
        history = agent.get_history()

        return AgentStatus(
            session_id=session_id,
            message_count=len(history),
            history=[ChatMessage(**msg) for msg in history]
        )

    except Exception as e:
        logger.error(f"Error getting agent status: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.delete("/agent/session/{session_id}")
async def delete_session(session_id: str):
    """Delete an agent session.

    Args:
        session_id: Session identifier

    Returns:
        Success message
    """
    try:
        agent_manager.delete_agent(session_id)
        return {"message": f"Session {session_id} deleted successfully"}

    except Exception as e:
        logger.error(f"Error deleting session: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/agent/clear/{session_id}")
async def clear_history(session_id: str):
    """Clear conversation history for a session.

    Args:
        session_id: Session identifier

    Returns:
        Success message
    """
    try:
        agent = agent_manager.get_or_create_agent(session_id)
        agent.clear_history()
        return {"message": f"History cleared for session {session_id}"}

    except Exception as e:
        logger.error(f"Error clearing history: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/agent/sessions")
async def list_sessions():
    """List all active sessions.

    Returns:
        List of active session IDs
    """
    try:
        sessions = agent_manager.get_active_sessions()
        return {"sessions": sessions, "count": len(sessions)}

    except Exception as e:
        logger.error(f"Error listing sessions: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/models", response_model=ModelsResponse)
async def list_models():
    """List available models.

    Returns:
        List of available models with their info
    """
    models = [
        ModelInfo(
            name=settings.reasoning_model,
            endpoint=settings.vllm_reasoning_endpoint,
            type="reasoning"
        ),
        ModelInfo(
            name=settings.coding_model,
            endpoint=settings.vllm_coding_endpoint,
            type="coding"
        )
    ]

    return ModelsResponse(models=models)


# ==================== Workflow Endpoints ====================


@router.post("/workflow/execute")
async def execute_workflow(request: ChatRequest):
    """Execute coding workflow: Planning -> Coding -> Review.

    This endpoint uses multi-agent workflow to automatically:
    1. Analyze requirements and create a plan (DeepSeek-R1)
    2. Generate code based on the plan (Qwen3-Coder)
    3. Review and improve the code (Qwen3-Coder)

    Args:
        request: Chat request with coding task

    Returns:
        Streaming response with workflow progress
    """
    try:
        # Get or create workflow for session
        workflow = workflow_manager.get_or_create_workflow(request.session_id)

        # Create streaming response
        async def generate():
            try:
                async for update in workflow.execute_stream(
                    user_request=request.message
                ):
                    # Send update as JSON
                    yield json.dumps(update) + "\n"
            except Exception as e:
                logger.error(f"Error in workflow execution: {e}")
                yield json.dumps({
                    "agent": "Workflow",
                    "status": "error",
                    "content": f"Error: {str(e)}"
                }) + "\n"

        return StreamingResponse(
            generate(),
            media_type="application/x-ndjson"
        )

    except Exception as e:
        logger.error(f"Error in workflow endpoint: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/workflow/sessions")
async def list_workflow_sessions():
    """List all active workflow sessions.

    Returns:
        List of active workflow session IDs
    """
    try:
        sessions = workflow_manager.get_active_sessions()
        return {"sessions": sessions, "count": len(sessions)}

    except Exception as e:
        logger.error(f"Error listing workflow sessions: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.delete("/workflow/session/{session_id}")
async def delete_workflow_session(session_id: str):
    """Delete a workflow session.

    Args:
        session_id: Session identifier

    Returns:
        Success message
    """
    try:
        workflow_manager.delete_workflow(session_id)
        return {"message": f"Workflow session {session_id} deleted successfully"}

    except Exception as e:
        logger.error(f"Error deleting workflow session: {e}")
        raise HTTPException(status_code=500, detail=str(e))


# ==================== Conversation Persistence Endpoints ====================


@router.get("/conversations")
async def list_conversations(
    limit: int = 50,
    offset: int = 0,
    mode: str = None,
    db: Session = Depends(get_db)
):
    """List all saved conversations.

    Args:
        limit: Maximum number of conversations to return
        offset: Offset for pagination
        mode: Filter by mode ("chat" or "workflow")

    Returns:
        List of conversations with metadata
    """
    try:
        repo = ConversationRepository(db)
        conversations = repo.list_conversations(limit=limit, offset=offset, mode=mode)
        return {
            "conversations": [conv.to_dict() for conv in conversations],
            "count": len(conversations),
            "limit": limit,
            "offset": offset
        }

    except Exception as e:
        logger.error(f"Error listing conversations: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/conversations/{session_id}")
async def get_conversation(session_id: str, db: Session = Depends(get_db)):
    """Get a specific conversation with all messages.

    Args:
        session_id: Session identifier

    Returns:
        Conversation with messages and artifacts
    """
    try:
        repo = ConversationRepository(db)
        conversation = repo.get_conversation(session_id)

        if not conversation:
            raise HTTPException(status_code=404, detail="Conversation not found")

        messages = repo.get_messages(session_id)
        artifacts = repo.get_artifacts(session_id)

        return {
            **conversation.to_dict(),
            "messages": [msg.to_dict() for msg in messages],
            "artifacts": [art.to_dict() for art in artifacts]
        }

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error getting conversation: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/conversations")
async def create_conversation(
    session_id: str,
    title: str = "New Conversation",
    mode: str = "chat",
    db: Session = Depends(get_db)
):
    """Create a new conversation.

    Args:
        session_id: Session identifier
        title: Conversation title
        mode: "chat" or "workflow"

    Returns:
        Created conversation
    """
    try:
        repo = ConversationRepository(db)

        # Check if conversation already exists
        existing = repo.get_conversation(session_id)
        if existing:
            raise HTTPException(status_code=400, detail="Conversation already exists")

        conversation = repo.create_conversation(session_id, title, mode)
        return conversation.to_dict()

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error creating conversation: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.put("/conversations/{session_id}")
async def update_conversation(
    session_id: str,
    title: str = None,
    workflow_state: dict = None,
    db: Session = Depends(get_db)
):
    """Update a conversation.

    Args:
        session_id: Session identifier
        title: New title
        workflow_state: New workflow state

    Returns:
        Updated conversation
    """
    try:
        repo = ConversationRepository(db)
        conversation = repo.update_conversation(session_id, title, workflow_state)

        if not conversation:
            raise HTTPException(status_code=404, detail="Conversation not found")

        return conversation.to_dict()

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error updating conversation: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.delete("/conversations/{session_id}")
async def delete_conversation(session_id: str, db: Session = Depends(get_db)):
    """Delete a conversation.

    Args:
        session_id: Session identifier

    Returns:
        Success message
    """
    try:
        repo = ConversationRepository(db)
        deleted = repo.delete_conversation(session_id)

        if not deleted:
            raise HTTPException(status_code=404, detail="Conversation not found")

        return {"message": f"Conversation {session_id} deleted successfully"}

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error deleting conversation: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/conversations/{session_id}/messages")
async def add_message(
    session_id: str,
    role: str,
    content: str,
    agent_name: str = None,
    message_type: str = None,
    meta_info: dict = None,
    db: Session = Depends(get_db)
):
    """Add a message to a conversation.

    Args:
        session_id: Session identifier
        role: Message role ("user", "assistant", "system")
        content: Message content
        agent_name: Optional agent name for workflow messages
        message_type: Optional message type
        meta_info: Optional metadata

    Returns:
        Created message
    """
    try:
        repo = ConversationRepository(db)
        message = repo.add_message(
            session_id=session_id,
            role=role,
            content=content,
            agent_name=agent_name,
            message_type=message_type,
            meta_info=meta_info
        )

        if not message:
            raise HTTPException(status_code=404, detail="Conversation not found")

        return message.to_dict()

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error adding message: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/conversations/{session_id}/artifacts")
async def add_artifact(
    session_id: str,
    filename: str,
    language: str,
    content: str,
    task_num: int = None,
    db: Session = Depends(get_db)
):
    """Add an artifact to a conversation.

    Args:
        session_id: Session identifier
        filename: Artifact filename
        language: Programming language
        content: Code content
        task_num: Optional task number

    Returns:
        Created artifact
    """
    try:
        repo = ConversationRepository(db)
        artifact = repo.add_artifact(
            session_id=session_id,
            filename=filename,
            language=language,
            content=content,
            task_num=task_num
        )

        if not artifact:
            raise HTTPException(status_code=404, detail="Conversation not found")

        return artifact.to_dict()

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error adding artifact: {e}")
        raise HTTPException(status_code=500, detail=str(e))


# ==================== Vector Database Endpoints ====================


@router.post("/vector/index")
async def index_code(
    code: str,
    filename: str,
    language: str,
    session_id: str,
    description: str = None
):
    """Index a code snippet in the vector database.

    Args:
        code: Code content
        filename: File name
        language: Programming language
        session_id: Session ID
        description: Optional description

    Returns:
        Document ID
    """
    try:
        from app.services.vector_db import vector_db
        doc_id = vector_db.add_code_snippet(
            code=code,
            filename=filename,
            language=language,
            session_id=session_id,
            description=description
        )
        return {"doc_id": doc_id, "message": "Code indexed successfully"}

    except Exception as e:
        logger.error(f"Error indexing code: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/vector/search")
async def search_code(
    query: str,
    session_id: str = None,
    language: str = None,
    n_results: int = 5
):
    """Search for code snippets.

    Args:
        query: Search query
        session_id: Optional session filter
        language: Optional language filter
        n_results: Maximum results

    Returns:
        List of matching code snippets
    """
    try:
        from app.services.vector_db import vector_db
        results = vector_db.search_code(
            query=query,
            session_id=session_id,
            language=language,
            n_results=n_results
        )
        return {
            "results": [
                {
                    "id": r.id,
                    "content": r.content,
                    "metadata": r.metadata,
                    "distance": r.distance
                }
                for r in results
            ],
            "count": len(results)
        }

    except Exception as e:
        logger.error(f"Error searching code: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/vector/stats")
async def get_vector_stats():
    """Get vector database statistics."""
    try:
        from app.services.vector_db import vector_db
        return vector_db.get_stats()

    except Exception as e:
        logger.error(f"Error getting vector stats: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.delete("/vector/session/{session_id}")
async def delete_vector_session(session_id: str):
    """Delete all indexed code for a session."""
    try:
        from app.services.vector_db import vector_db
        vector_db.delete_by_session(session_id)
        return {"message": f"Deleted vectors for session {session_id}"}

    except Exception as e:
        logger.error(f"Error deleting vectors: {e}")
        raise HTTPException(status_code=500, detail=str(e))


# ==================== LM Cache Endpoints ====================


@router.get("/cache/stats")
async def get_cache_stats():
    """Get LM cache statistics."""
    try:
        from app.services.lm_cache import lm_cache
        return lm_cache.get_stats()

    except Exception as e:
        logger.error(f"Error getting cache stats: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/cache/clear")
async def clear_cache():
    """Clear all cached LLM responses."""
    try:
        from app.services.lm_cache import lm_cache
        count = lm_cache.clear()
        return {"message": f"Cleared {count} cache entries"}

    except Exception as e:
        logger.error(f"Error clearing cache: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/cache/cleanup")
async def cleanup_expired_cache():
    """Remove expired cache entries."""
    try:
        from app.services.lm_cache import lm_cache
        count = lm_cache.cleanup_expired()
        return {"message": f"Cleaned up {count} expired entries"}

    except Exception as e:
        logger.error(f"Error cleaning cache: {e}")
        raise HTTPException(status_code=500, detail=str(e))

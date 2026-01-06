"""API routes for the coding agent."""
import logging
import json
from pathlib import Path
from typing import Dict, Any
from fastapi import APIRouter, HTTPException, Depends, Query, UploadFile, File, Form
from fastapi.responses import StreamingResponse
from typing import List
from sqlalchemy.orm import Session

from app.api.models import (
    ChatRequest,
    ChatResponse,
    AgentStatus,
    ModelsResponse,
    ModelInfo,
    ErrorResponse,
    ChatMessage,
    UnifiedChatResponse,
    ArtifactInfo,
    AnalysisSummary,
    StreamUpdate
)
from app.agent import get_agent_manager, get_workflow_manager, get_framework_info, get_unified_agent_manager
from app.core.config import settings
from app.core.session_store import get_session_store
from app.db import get_db, ConversationRepository
from app.utils.security import sanitize_path, SecurityError
from app.services import WorkflowService

logger = logging.getLogger(__name__)
router = APIRouter()

# Get managers based on configured framework
agent_manager = get_agent_manager()
workflow_manager = get_workflow_manager()

# Thread-safe session storage
session_store = get_session_store()

# Workflow service for business logic
workflow_service = WorkflowService(session_store)


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


# ==================== Unified Chat Endpoints ====================
# These endpoints use the new unified architecture that routes all
# requests through the Supervisor for intelligent handling.


@router.post("/chat/unified", response_model=UnifiedChatResponse)
async def unified_chat(request: ChatRequest):
    """Unified chat endpoint with Supervisor-based routing.

    This is the new recommended endpoint that:
    1. Analyzes requests using Supervisor (Reasoning LLM)
    2. Routes to appropriate handler (QuickQA, Planning, CodeGeneration, etc.)
    3. Returns structured response with artifacts and next actions

    Args:
        request: Chat request with message and session info

    Returns:
        Unified response with structured content, artifacts, and metadata
    """
    try:
        # Get unified agent manager
        unified_manager = get_unified_agent_manager()

        # Process request
        response = await unified_manager.process_request(
            session_id=request.session_id,
            user_message=request.message,
            workspace=request.workspace,
            stream=False
        )

        # Convert to API response model
        return UnifiedChatResponse(
            response_type=response.response_type,
            content=response.content,
            artifacts=[
                ArtifactInfo(
                    filename=a.get("filename", "unknown"),
                    language=a.get("language", "text"),
                    content=a.get("content"),
                    saved_path=a.get("saved_path"),
                    size=len(a.get("content", "")) if a.get("content") else None
                )
                for a in response.artifacts
            ],
            plan_file=response.plan_file,
            analysis=AnalysisSummary(
                complexity=response.analysis.get("complexity") if response.analysis else None,
                task_type=response.analysis.get("task_type") if response.analysis else None,
                required_agents=response.analysis.get("required_agents", []) if response.analysis else [],
                confidence=response.analysis.get("confidence") if response.analysis else None,
                workflow_strategy=response.analysis.get("workflow_strategy") if response.analysis else None
            ) if response.analysis else None,
            next_actions=response.next_actions or [],
            session_id=request.session_id,
            metadata=response.metadata,
            success=response.success,
            error=response.error
        )

    except Exception as e:
        logger.error(f"Error in unified chat endpoint: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/chat/unified/stream")
async def unified_chat_stream(request: ChatRequest):
    """Unified streaming chat endpoint with Supervisor-based routing.

    Streams progress updates as the request is processed through
    Supervisor analysis and handler execution.

    Args:
        request: Chat request with message and session info

    Returns:
        Server-Sent Events stream with progress updates
    """
    try:
        unified_manager = get_unified_agent_manager()

        async def generate():
            try:
                # process_request는 async def이므로 먼저 await 필요
                stream_generator = await unified_manager.process_request(
                    session_id=request.session_id,
                    user_message=request.message,
                    workspace=request.workspace,
                    stream=True
                )
                async for update in stream_generator:
                    yield f"data: {json.dumps(update.to_dict())}\n\n"

                yield "data: [DONE]\n\n"

            except Exception as e:
                logger.error(f"Error in unified stream: {e}")
                error_data = {
                    "agent": "System",
                    "type": "error",
                    "status": "error",
                    "message": str(e)
                }
                yield f"data: {json.dumps(error_data)}\n\n"
                yield "data: [DONE]\n\n"

        return StreamingResponse(
            generate(),
            media_type="text/event-stream"
        )

    except Exception as e:
        logger.error(f"Error in unified chat stream endpoint: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/chat/unified/context/{session_id}")
async def get_unified_context(session_id: str):
    """Get conversation context for a session.

    Args:
        session_id: Session identifier

    Returns:
        Context information including messages and artifacts
    """
    try:
        unified_manager = get_unified_agent_manager()
        context = await unified_manager.get_context(session_id)

        return {
            "session_id": session_id,
            "message_count": len(context.messages),
            "artifact_count": len(context.artifacts),
            "workspace": context.workspace,
            "last_analysis": context.last_analysis,
            "created_at": context.created_at.isoformat(),
            "updated_at": context.updated_at.isoformat()
        }

    except Exception as e:
        logger.error(f"Error getting unified context: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.delete("/chat/unified/context/{session_id}")
async def clear_unified_context(session_id: str):
    """Clear conversation context for a session.

    Args:
        session_id: Session identifier

    Returns:
        Confirmation message
    """
    try:
        unified_manager = get_unified_agent_manager()
        await unified_manager.clear_context(session_id)

        return {"message": f"Context cleared for session: {session_id}"}

    except Exception as e:
        logger.error(f"Error clearing unified context: {e}")
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


@router.get("/frameworks")
async def list_frameworks():
    """List available agent frameworks and their capabilities.

    Returns:
        Framework information including current framework and available options
    """
    try:
        return get_framework_info()

    except Exception as e:
        logger.error(f"Error getting framework info: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/framework/current")
async def get_current_framework():
    """Get the currently active agent framework.

    Returns:
        Current framework name and settings
    """
    return {
        "framework": settings.agent_framework,
        "agent_manager": type(agent_manager).__name__,
        "workflow_manager": type(workflow_manager).__name__
    }


@router.post("/framework/select")
async def select_framework(
    session_id: str,
    framework: str = Query(..., pattern="^(standard|deepagents)$")
):
    """Select workflow framework for a session.

    Args:
        session_id: Session identifier
        framework: "standard" for LangChain or "deepagents" for DeepAgents

    Returns:
        Success status and selected framework
    """
    try:
        await session_store.set_framework(session_id, framework)

        # Clear cached workflows when switching frameworks
        await workflow_service.clear_workflow_cache(session_id)

        return {
            "success": True,
            "session_id": session_id,
            "framework": framework,
            "message": f"Framework set to {framework}"
        }

    except ValueError as e:
        logger.error(f"Invalid framework value: {e}")
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        logger.error(f"Error selecting framework: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/framework/session/{session_id}")
async def get_session_framework(session_id: str):
    """Get the workflow framework for a specific session.

    Args:
        session_id: Session identifier

    Returns:
        Current framework for this session
    """
    framework = await session_store.get_framework(session_id)
    return {
        "session_id": session_id,
        "framework": framework,
        "available_frameworks": ["standard", "deepagents"]
    }


# ==================== Workflow Endpoints ====================


@router.post("/workflow/execute")
async def execute_workflow(request: ChatRequest):
    """Execute coding workflow: Planning -> Coding -> Review.

    This endpoint uses multi-agent workflow to automatically:
    1. Analyze requirements and create a plan (DeepSeek-R1)
    2. Generate code based on the plan (Qwen3-Coder)
    3. Review and improve the code (Qwen3-Coder)

    Supports DUAL FRAMEWORK MODE:
    - "standard": Uses standard LangChain workflow manager
    - "deepagents": Uses DeepAgents framework with TodoList/SubAgent/Summarization middleware

    Supports context from previous conversation turns to enable
    iterative refinement of generated code.

    Args:
        request: Chat request with coding task and optional context

    Returns:
        Streaming response with workflow progress
    """
    import os
    import re
    from datetime import datetime

    try:
        # Use service layer for workspace and workflow management
        workspace = await workflow_service.get_or_create_workspace(
            session_id=request.session_id,
            user_message=request.message,
            base_workspace=request.workspace
        )

        # Get appropriate workflow based on framework selection
        selected_framework = await session_store.get_framework(request.session_id)
        try:
            workflow = await workflow_service.get_workflow(
                session_id=request.session_id,
                workspace=workspace,
                workflow_manager=workflow_manager
            )
        except Exception as e:
            raise HTTPException(
                status_code=503 if "not available" in str(e) else 500,
                detail=str(e)
            )

        # Build context-aware request using service
        context_str = workflow_service.build_context_string(
            messages=request.context.messages if request.context else None,
            artifacts=request.context.artifacts if request.context else None
        )

        # Combine context with user message
        full_request = request.message
        if context_str:
            full_request = f"{context_str}\n<current_request>\n{request.message}\n</current_request>"

        # Helper to write artifact to workspace (async)
        async def write_artifact_to_workspace(artifact: dict) -> dict:
            """Write artifact to workspace and return save status."""
            import aiofiles
            from datetime import datetime
            try:
                filename = artifact.get("filename", "code.py")
                content = artifact.get("content", "")

                # Sanitize path to prevent traversal attacks
                file_path = sanitize_path(filename, workspace, allow_creation=True)

                # Create parent directories if needed
                file_path.parent.mkdir(parents=True, exist_ok=True)

                # Write file asynchronously
                async with aiofiles.open(file_path, 'w', encoding='utf-8') as f:
                    await f.write(content)

                logger.info(f"Auto-saved artifact to: {file_path}")
                return {
                    "saved": True,
                    "saved_path": str(file_path),
                    "saved_at": datetime.now().isoformat(),
                    "error": None
                }
            except SecurityError as e:
                logger.warning(f"Security violation in artifact save: {e}")
                return {
                    "saved": False,
                    "saved_path": None,
                    "saved_at": None,
                    "error": f"Invalid path: {artifact.get('filename', 'unknown')}"
                }
            except Exception as e:
                logger.error(f"Failed to auto-save artifact: {e}")
                return {
                    "saved": False,
                    "saved_path": None,
                    "saved_at": None,
                    "error": str(e)
                }

        # Create streaming response
        async def generate():
            try:
                # Send project information to frontend
                project_name = os.path.basename(workspace)
                base_workspace_path = os.path.dirname(workspace)

                yield json.dumps({
                    "type": "project_info",
                    "project_name": project_name,
                    "workspace": base_workspace_path,
                    "full_path": workspace,
                    "session_id": request.session_id,
                    "message": f"Working on project: {project_name}"
                }) + "\n"

                # Use appropriate execution method based on framework
                # Pass workspace context to both frameworks
                workflow_context = {
                    "session_id": request.session_id,
                    "workspace": workspace
                }

                if selected_framework == "deepagents":
                    # DeepAgents uses execute_stream with context
                    execution_stream = workflow.execute_stream(
                        user_request=full_request,
                        context=workflow_context
                    )
                else:
                    # Standard workflow also uses context for workspace
                    execution_stream = workflow.execute_stream(
                        user_request=full_request,
                        context=workflow_context
                    )

                async for update in execution_stream:
                    # Auto-save artifacts to workspace
                    if update.get("type") == "artifact" and update.get("artifact"):
                        save_result = await write_artifact_to_workspace(update["artifact"])
                        update["artifact"].update(save_result)

                    # Also save artifacts from completed updates
                    if update.get("type") == "completed" and update.get("artifacts"):
                        for artifact in update["artifacts"]:
                            save_result = await write_artifact_to_workspace(artifact)
                            artifact.update(save_result)

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


# ==================== Tool Execution Endpoints ====================


@router.post("/tools/execute")
async def execute_tool(
    tool_name: str,
    params: dict,
    session_id: str = "default"
):
    """Execute a tool with given parameters.

    Args:
        tool_name: Name of the tool to execute
        params: Tool-specific parameters
        session_id: Session identifier for logging

    Returns:
        Tool execution result
    """
    try:
        from app.tools.executor import ToolExecutor

        executor = ToolExecutor()
        result = await executor.execute(tool_name, params, session_id)

        return result.to_dict()

    except Exception as e:
        logger.error(f"Error executing tool {tool_name}: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/tools/execute/batch")
async def execute_tools_batch(
    tool_calls: list[dict],
    session_id: str = "default"
):
    """Execute multiple tools in parallel.

    Args:
        tool_calls: List of {tool_name, params} dictionaries
        session_id: Session identifier

    Returns:
        List of tool execution results
    """
    try:
        from app.tools.executor import ToolExecutor

        executor = ToolExecutor()
        results = await executor.execute_batch(tool_calls, session_id)

        return {
            "results": [r.to_dict() for r in results],
            "count": len(results)
        }

    except Exception as e:
        logger.error(f"Error executing tool batch: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/tools/list")
async def list_tools(category: str = None):
    """List available tools.

    Args:
        category: Optional category filter

    Returns:
        List of tool schemas
    """
    try:
        from app.tools.registry import get_registry
        from app.tools.base import ToolCategory

        registry = get_registry()

        if category:
            try:
                cat_enum = ToolCategory(category)
                tools = registry.list_tools(cat_enum)
            except ValueError:
                raise HTTPException(
                    status_code=400,
                    detail=f"Invalid category: {category}"
                )
        else:
            tools = registry.list_tools()

        return {
            "tools": [tool.get_schema() for tool in tools],
            "count": len(tools)
        }

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error listing tools: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/tools/{tool_name}/schema")
async def get_tool_schema(tool_name: str):
    """Get schema for a specific tool.

    Args:
        tool_name: Name of the tool

    Returns:
        Tool schema
    """
    try:
        from app.tools.registry import get_registry

        registry = get_registry()
        tool = registry.get_tool(tool_name)

        if not tool:
            raise HTTPException(
                status_code=404,
                detail=f"Tool '{tool_name}' not found"
            )

        return tool.get_schema()

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error getting tool schema: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/tools/categories")
async def get_tool_categories():
    """Get list of tool categories.

    Returns:
        List of category names
    """
    try:
        from app.tools.registry import get_registry

        registry = get_registry()
        return {
            "categories": registry.get_categories()
        }

    except Exception as e:
        logger.error(f"Error getting categories: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/tools/stats")
async def get_tool_stats():
    """Get tool registry statistics.

    Returns:
        Tool statistics
    """
    try:
        from app.tools.registry import get_registry

        registry = get_registry()
        return registry.get_statistics()

    except Exception as e:
        logger.error(f"Error getting tool stats: {e}")
        raise HTTPException(status_code=500, detail=str(e))


# ==================== Agent Spawning Endpoints ====================


@router.post("/agents/spawn")
async def spawn_agent(agent_type: str, session_id: str):
    """Spawn a new specialized agent."""
    try:
        from app.agent.registry import get_spawner
        spawner = get_spawner()
        agent = spawner.spawn(agent_type, session_id)
        return {"success": True, "agent_id": f"{agent_type}_{session_id}", "agent": agent.to_dict()}
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        logger.error(f"Error spawning agent: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/agents/types")
async def list_agent_types():
    """List available agent types."""
    try:
        from app.agent.registry import AgentRegistry
        registry = AgentRegistry()
        return {"agent_types": registry.list_agent_types()}
    except Exception as e:
        logger.error(f"Error listing agent types: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/agents/active")
async def list_active_agents(session_id: str = None):
    """List active agents."""
    try:
        from app.agent.registry import get_spawner
        spawner = get_spawner()
        if session_id:
            agents = spawner.get_by_session(session_id)
            return {"agents": [agent.to_dict() for agent in agents]}
        return {"agent_ids": spawner.list_active()}
    except Exception as e:
        logger.error(f"Error listing agents: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/agents/{agent_id}/process")
async def process_agent_task(agent_id: str, task: str, context: dict = None):
    """Process a task with an agent."""
    try:
        from app.agent.registry import get_spawner
        spawner = get_spawner()
        agent = spawner.get_agent(agent_id)
        if not agent:
            raise HTTPException(status_code=404, detail=f"Agent '{agent_id}' not found")
        result = await agent.process(task, context or {})
        return {"success": True, "result": result}
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error processing task: {e}")
        raise HTTPException(status_code=500, detail=str(e))


# ==================== Workspace Endpoints ====================


@router.get("/workspace/list")
async def list_directory(path: str = "/home"):
    """List contents of a directory.

    Args:
        path: Directory path to list

    Returns:
        List of files and directories
    """
    import os
    try:
        if not os.path.exists(path):
            return {"success": False, "error": f"Path does not exist: {path}"}

        if not os.path.isdir(path):
            return {"success": False, "error": f"Not a directory: {path}"}

        contents = []
        for item in os.listdir(path):
            item_path = os.path.join(path, item)
            contents.append({
                "path": item_path,
                "name": item,
                "is_directory": os.path.isdir(item_path)
            })

        return {"success": True, "contents": contents}

    except PermissionError:
        return {"success": False, "error": f"Permission denied: {path}"}
    except Exception as e:
        logger.error(f"Error listing directory: {e}")
        return {"success": False, "error": str(e)}


@router.post("/workspace/set")
async def set_workspace(request: dict):
    """Set workspace directory for a session.

    Args:
        request: Contains session_id and workspace_path

    Returns:
        Success status and current workspace
    """
    BASE_WORKSPACE = settings.default_workspace
    session_id = request.get("session_id", "default")
    workspace_path = request.get("workspace_path", BASE_WORKSPACE)

    try:
        # Sanitize workspace path to prevent path traversal
        validated_path = sanitize_path(workspace_path, BASE_WORKSPACE, allow_creation=True)

        # Create directory if it doesn't exist
        validated_path.mkdir(parents=True, exist_ok=True)

        await session_store.set_workspace(session_id, str(validated_path))

        return {"success": True, "workspace": str(validated_path)}

    except SecurityError as e:
        logger.warning(f"Security violation in set_workspace: {e}")
        return {"success": False, "workspace": None, "error": "Invalid workspace path"}
    except Exception as e:
        logger.error(f"Error setting workspace: {e}")
        return {"success": False, "workspace": workspace_path, "error": str(e)}


@router.get("/workspace/current")
async def get_workspace(session_id: str = "default"):
    """Get current workspace for a session.

    Args:
        session_id: Session identifier

    Returns:
        Current workspace path
    """
    workspace = await session_store.get_workspace(session_id)
    return {"success": True, "workspace": workspace}


@router.post("/workspace/write")
async def write_workspace_file(request: dict):
    """Write a file to the workspace.

    Args:
        request: Contains session_id, filename, and content

    Returns:
        Success status and file path
    """
    session_id = request.get("session_id", "default")
    filename = request.get("filename", "")
    content = request.get("content", "")

    if not filename:
        return {"success": False, "error": "Filename is required"}

    try:
        import aiofiles

        workspace = await session_store.get_workspace(session_id)

        # Sanitize file path to prevent path traversal
        file_path = sanitize_path(filename, workspace, allow_creation=True)

        # Create parent directories if needed
        file_path.parent.mkdir(parents=True, exist_ok=True)

        # Write file asynchronously
        async with aiofiles.open(file_path, 'w', encoding='utf-8') as f:
            await f.write(content)

        logger.info(f"Wrote file: {file_path}")
        return {"success": True, "path": str(file_path)}

    except SecurityError as e:
        logger.warning(f"Security violation in write_workspace_file: {e}")
        return {"success": False, "error": "Invalid file path"}
    except Exception as e:
        logger.error(f"Error writing file: {e}")
        return {"success": False, "error": str(e)}


@router.get("/workspace/read")
async def read_workspace_file(session_id: str = "default", filename: str = ""):
    """Read a file from the workspace.

    Args:
        session_id: Session identifier
        filename: File to read (relative to workspace)

    Returns:
        File content
    """
    if not filename:
        return {"success": False, "error": "Filename is required"}

    try:
        import aiofiles

        workspace = await session_store.get_workspace(session_id)

        # Sanitize file path to prevent path traversal
        file_path = sanitize_path(filename, workspace, allow_creation=False)

        if not file_path.exists():
            return {"success": False, "error": f"File not found: {filename}"}

        # Read file asynchronously
        async with aiofiles.open(file_path, 'r', encoding='utf-8') as f:
            content = await f.read()

        return {"success": True, "content": content}

    except SecurityError as e:
        logger.warning(f"Security violation in read_workspace_file: {e}")
        return {"success": False, "error": "Invalid file path"}
    except Exception as e:
        logger.error(f"Error reading file: {e}")
        return {"success": False, "error": str(e)}


@router.get("/workspace/projects")
async def list_projects(base_workspace: str = None):
    """List all project directories in the base workspace.

    Args:
        base_workspace: Base workspace directory path

    Returns:
        List of project directories with metadata
    """
    import os
    from datetime import datetime

    BASE_ALLOWED = settings.default_workspace
    base_workspace = base_workspace or BASE_ALLOWED

    try:
        # Validate base_workspace path
        validated_base = sanitize_path(base_workspace, BASE_ALLOWED, allow_creation=False)

        if not validated_base.exists():
            return {"success": True, "projects": []}

        projects = []
        for item in validated_base.iterdir():
            if not item.is_dir():
                continue

            # Skip common ignored directories
            if item.name in ['workspace', '.git', 'node_modules', '__pycache__', 'venv']:
                continue

            try:
                # Get directory stats
                stats = item.stat()
                modified_time = datetime.fromtimestamp(stats.st_mtime).isoformat()

                # Count files in project
                file_count = sum(1 for _ in item.rglob('*') if _.is_file())

                projects.append({
                    "name": item.name,
                    "path": str(item),
                    "modified": modified_time,
                    "file_count": file_count
                })
            except Exception as e:
                logger.warning(f"Error reading project {item.name}: {e}")
                continue

        # Sort by modification time (most recent first)
        projects.sort(key=lambda x: x["modified"], reverse=True)

        return {"success": True, "projects": projects}

    except SecurityError as e:
        logger.warning(f"Security violation in list_projects: {e}")
        return {"success": False, "error": "Invalid workspace path"}
    except Exception as e:
        logger.error(f"Error listing projects: {e}")
        return {"success": False, "error": str(e)}


@router.get("/workspace/files")
async def get_workspace_files(workspace_path: str):
    """Get file structure of a workspace directory.

    Args:
        workspace_path: Workspace directory path

    Returns:
        Tree structure of files and directories
    """
    import os

    try:
        if not os.path.exists(workspace_path):
            return {"success": False, "error": "Workspace does not exist"}

        def build_tree(path, max_depth=3, current_depth=0):
            """Recursively build directory tree"""
            if current_depth >= max_depth:
                return None

            items = []
            try:
                for item in os.listdir(path):
                    # Skip hidden files and common ignore patterns
                    if item.startswith('.') or item in ['node_modules', '__pycache__', 'venv', '.git']:
                        continue

                    item_path = os.path.join(path, item)
                    is_dir = os.path.isdir(item_path)

                    item_info = {
                        "name": item,
                        "path": item_path,
                        "is_directory": is_dir
                    }

                    if is_dir:
                        children = build_tree(item_path, max_depth, current_depth + 1)
                        if children:
                            item_info["children"] = children

                    items.append(item_info)
            except PermissionError:
                pass

            return items

        file_tree = build_tree(workspace_path)

        # Also provide file list summary
        files = []
        for root, dirs, filenames in os.walk(workspace_path):
            # Skip hidden and ignored directories
            dirs[:] = [d for d in dirs if not d.startswith('.') and d not in ['node_modules', '__pycache__', 'venv', '.git']]

            for filename in filenames:
                if not filename.startswith('.'):
                    files.append(os.path.join(root, filename).replace(workspace_path + '/', ''))

        return {
            "success": True,
            "workspace": workspace_path,
            "has_files": len(files) > 0,
            "file_count": len(files),
            "files": files[:50],  # Limit to first 50 files
            "tree": file_tree
        }

    except Exception as e:
        logger.error(f"Error getting workspace files: {e}")
        return {"success": False, "error": str(e)}


# ==================== Shell/Terminal Endpoints ====================


@router.post("/shell/execute")
async def execute_shell_command(request: dict):
    """Execute a shell command in the workspace directory.

    Args:
        request: Contains session_id, command, and optional timeout

    Returns:
        Command output (stdout, stderr, return code)
    """
    import asyncio
    import subprocess
    import os

    session_id = request.get("session_id", "default")
    command = request.get("command", "")
    timeout = request.get("timeout", 30)  # Default 30 seconds

    if not command:
        return {"success": False, "error": "No command provided"}

    # Get workspace for this session
    workspace = await session_store.get_workspace(session_id)

    # Security: Block dangerous commands
    dangerous_patterns = [
        "rm -rf /", "rm -rf /*", "mkfs", "dd if=", ":(){ :|:& };:",
        "> /dev/sd", "chmod -R 777 /", "wget", "curl", "nc -e",
        "python -c", "perl -e", "ruby -e"
    ]

    command_lower = command.lower().strip()
    for pattern in dangerous_patterns:
        if pattern in command_lower:
            return {
                "success": False,
                "error": f"Blocked: potentially dangerous command pattern '{pattern}'"
            }

    try:
        # Run command in workspace directory
        process = await asyncio.create_subprocess_shell(
            command,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
            cwd=workspace,
            env={**os.environ, "HOME": workspace}
        )

        try:
            stdout, stderr = await asyncio.wait_for(
                process.communicate(),
                timeout=timeout
            )
        except asyncio.TimeoutError:
            process.kill()
            return {
                "success": False,
                "error": f"Command timed out after {timeout} seconds",
                "stdout": "",
                "stderr": "",
                "return_code": -1
            }

        return {
            "success": process.returncode == 0,
            "stdout": stdout.decode('utf-8', errors='replace'),
            "stderr": stderr.decode('utf-8', errors='replace'),
            "return_code": process.returncode,
            "cwd": workspace
        }

    except Exception as e:
        logger.error(f"Error executing shell command: {e}")
        return {"success": False, "error": str(e)}


@router.get("/shell/history")
async def get_shell_history(session_id: str = "default"):
    """Get command history for a session (placeholder for future implementation)."""
    return {"success": True, "history": [], "message": "History tracking not yet implemented"}


# ==================== Session Management Endpoints ====================


@router.get("/sessions/list")
async def list_all_sessions(db: Session = Depends(get_db)):
    """List all sessions with their workspace information.

    Returns comprehensive session info including:
    - Session ID
    - Title
    - Workspace path
    - Framework
    - Last updated time
    - Message count

    Useful for multi-user dashboard and session management UI.
    """
    from app.db.repository import ConversationRepository
    import os

    try:
        repo = ConversationRepository(db)
        conversations = repo.list_conversations(limit=100)

        sessions = []
        for conv in conversations:
            workspace_path = conv.workspace_path or settings.default_workspace

            # Check if workspace exists and get file count
            file_count = 0
            workspace_exists = False
            if workspace_path:
                workspace_exists = os.path.exists(workspace_path)
                if workspace_exists:
                    try:
                        file_count = sum(1 for _ in os.scandir(workspace_path) if _.is_file())
                    except (PermissionError, OSError):
                        pass

            sessions.append({
                "session_id": conv.session_id,
                "title": conv.title,
                "workspace_path": workspace_path,
                "workspace_exists": workspace_exists,
                "file_count": file_count,
                "framework": conv.framework or "standard",
                "mode": conv.mode,
                "created_at": conv.created_at.isoformat() if conv.created_at else None,
                "updated_at": conv.updated_at.isoformat() if conv.updated_at else None,
                "message_count": len(conv.messages) if conv.messages else 0
            })

        return {
            "success": True,
            "total_sessions": len(sessions),
            "sessions": sessions
        }

    except Exception as e:
        logger.error(f"Error listing sessions: {e}")
        return {"success": False, "error": str(e)}


@router.get("/sessions/{session_id}/files")
async def get_session_files(
    session_id: str,
    include_content: bool = False,
    max_file_size: int = 100000  # Max 100KB per file for content
):
    """Get all files in a session's workspace with optional content.

    Args:
        session_id: Session identifier
        include_content: If True, include file contents (for small files)
        max_file_size: Maximum file size to include content for (bytes)

    Returns:
        List of files with metadata and optional content
    """
    import os
    import mimetypes

    try:
        workspace = await session_store.get_workspace(session_id)

        if not os.path.exists(workspace):
            return {
                "success": False,
                "error": f"Workspace does not exist: {workspace}"
            }

        files = []
        total_size = 0

        # Extensions to include content for
        text_extensions = {'.py', '.js', '.ts', '.tsx', '.jsx', '.css', '.html',
                          '.json', '.yaml', '.yml', '.md', '.txt', '.sh', '.sql',
                          '.xml', '.csv', '.env', '.gitignore', '.dockerfile'}

        for root, dirs, filenames in os.walk(workspace):
            # Skip hidden and common ignore directories
            dirs[:] = [d for d in dirs if not d.startswith('.') and
                       d not in ['node_modules', '__pycache__', 'venv', '.git', 'dist', 'build']]

            for filename in filenames:
                if filename.startswith('.'):
                    continue

                file_path = os.path.join(root, filename)
                rel_path = os.path.relpath(file_path, workspace)

                try:
                    stat = os.stat(file_path)
                    file_size = stat.st_size
                    total_size += file_size

                    _, ext = os.path.splitext(filename)
                    mime_type, _ = mimetypes.guess_type(file_path)

                    file_info = {
                        "filename": filename,
                        "path": rel_path,
                        "full_path": file_path,
                        "size": file_size,
                        "extension": ext,
                        "mime_type": mime_type,
                        "modified": stat.st_mtime,
                        "is_text": ext.lower() in text_extensions
                    }

                    # Optionally include content for small text files
                    if include_content and ext.lower() in text_extensions and file_size <= max_file_size:
                        try:
                            with open(file_path, 'r', encoding='utf-8') as f:
                                file_info["content"] = f.read()
                        except (UnicodeDecodeError, IOError):
                            file_info["content"] = None
                            file_info["error"] = "Could not read file content"

                    files.append(file_info)

                except (PermissionError, OSError) as e:
                    files.append({
                        "filename": filename,
                        "path": rel_path,
                        "error": str(e)
                    })

        # Sort by path
        files.sort(key=lambda x: x.get("path", ""))

        return {
            "success": True,
            "session_id": session_id,
            "workspace": workspace,
            "total_files": len(files),
            "total_size": total_size,
            "files": files
        }

    except Exception as e:
        logger.error(f"Error getting session files: {e}")
        return {"success": False, "error": str(e)}


@router.get("/sessions/{session_id}/file")
async def read_session_file(
    session_id: str,
    file_path: str
):
    """Read a specific file from session's workspace.

    Args:
        session_id: Session identifier
        file_path: Relative path to file within workspace

    Returns:
        File content and metadata
    """
    import os
    import mimetypes

    try:
        workspace = await session_store.get_workspace(session_id)

        # Security: Validate path is within workspace
        full_path = os.path.normpath(os.path.join(workspace, file_path))
        if not full_path.startswith(os.path.normpath(workspace)):
            return {
                "success": False,
                "error": "Access denied: Path is outside workspace"
            }

        if not os.path.exists(full_path):
            return {
                "success": False,
                "error": f"File not found: {file_path}"
            }

        if not os.path.isfile(full_path):
            return {
                "success": False,
                "error": "Path is not a file"
            }

        stat = os.stat(full_path)
        _, ext = os.path.splitext(file_path)
        mime_type, _ = mimetypes.guess_type(full_path)

        # Read content for text files
        content = None
        encoding = None
        binary = False

        text_extensions = {'.py', '.js', '.ts', '.tsx', '.jsx', '.css', '.html',
                          '.json', '.yaml', '.yml', '.md', '.txt', '.sh', '.sql',
                          '.xml', '.csv', '.env', '.gitignore', '.dockerfile', '.toml'}

        if ext.lower() in text_extensions or (mime_type and mime_type.startswith('text/')):
            try:
                with open(full_path, 'r', encoding='utf-8') as f:
                    content = f.read()
                encoding = 'utf-8'
            except UnicodeDecodeError:
                binary = True
        else:
            binary = True

        return {
            "success": True,
            "file_path": file_path,
            "full_path": full_path,
            "workspace": workspace,
            "size": stat.st_size,
            "extension": ext,
            "mime_type": mime_type,
            "modified": stat.st_mtime,
            "encoding": encoding,
            "binary": binary,
            "content": content
        }

    except Exception as e:
        logger.error(f"Error reading session file: {e}")
        return {"success": False, "error": str(e)}


# ==================== Download/Export Endpoints ====================


@router.get("/sessions/{session_id}/download")
async def download_session_workspace(
    session_id: str,
    format: str = Query("zip", pattern="^(zip|tar)$")
):
    """Download session workspace as a ZIP or TAR archive.

    Args:
        session_id: Session identifier
        format: Archive format ('zip' or 'tar')

    Returns:
        Streaming file download
    """
    import os
    import io
    import zipfile
    import tarfile
    from datetime import datetime

    try:
        workspace = await session_store.get_workspace(session_id)

        if not os.path.exists(workspace):
            raise HTTPException(status_code=404, detail=f"Workspace not found: {workspace}")

        # Get project name from workspace path
        project_name = os.path.basename(workspace) or "workspace"
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        archive_name = f"{project_name}_{timestamp}"

        # Directories and files to skip
        skip_dirs = {'.git', 'node_modules', '__pycache__', 'venv', '.venv', 'dist', 'build', '.next'}
        skip_files = {'.DS_Store', 'Thumbs.db'}

        if format == "zip":
            # Create ZIP archive in memory
            zip_buffer = io.BytesIO()

            with zipfile.ZipFile(zip_buffer, 'w', zipfile.ZIP_DEFLATED) as zip_file:
                for root, dirs, files in os.walk(workspace):
                    # Skip excluded directories
                    dirs[:] = [d for d in dirs if d not in skip_dirs and not d.startswith('.')]

                    for file in files:
                        if file in skip_files or file.startswith('.'):
                            continue

                        file_path = os.path.join(root, file)
                        arc_name = os.path.relpath(file_path, workspace)

                        try:
                            zip_file.write(file_path, arc_name)
                        except (PermissionError, OSError) as e:
                            logger.warning(f"Skipping file {file_path}: {e}")

            zip_buffer.seek(0)

            return StreamingResponse(
                zip_buffer,
                media_type="application/zip",
                headers={
                    "Content-Disposition": f'attachment; filename="{archive_name}.zip"'
                }
            )

        else:  # tar format
            tar_buffer = io.BytesIO()

            with tarfile.open(fileobj=tar_buffer, mode='w:gz') as tar_file:
                for root, dirs, files in os.walk(workspace):
                    dirs[:] = [d for d in dirs if d not in skip_dirs and not d.startswith('.')]

                    for file in files:
                        if file in skip_files or file.startswith('.'):
                            continue

                        file_path = os.path.join(root, file)
                        arc_name = os.path.relpath(file_path, workspace)

                        try:
                            tar_file.add(file_path, arcname=arc_name)
                        except (PermissionError, OSError) as e:
                            logger.warning(f"Skipping file {file_path}: {e}")

            tar_buffer.seek(0)

            return StreamingResponse(
                tar_buffer,
                media_type="application/gzip",
                headers={
                    "Content-Disposition": f'attachment; filename="{archive_name}.tar.gz"'
                }
            )

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error creating archive: {e}")
        raise HTTPException(status_code=500, detail=str(e))


# ==================== File Upload Endpoints ====================


@router.post("/workspace/upload")
async def upload_file_to_workspace(
    file: UploadFile = File(...),
    session_id: str = Form("default"),
    sub_path: str = Form("")
):
    """Upload a single file to the session's workspace.

    Args:
        file: The file to upload
        session_id: Session identifier
        sub_path: Optional subdirectory within workspace

    Returns:
        Upload result with file path
    """
    import os
    import aiofiles

    try:
        workspace = await session_store.get_workspace(session_id)

        # Construct target path
        if sub_path:
            target_dir = os.path.join(workspace, sub_path)
        else:
            target_dir = workspace

        # Validate target path is within workspace
        target_dir = os.path.normpath(target_dir)
        if not target_dir.startswith(os.path.normpath(workspace)):
            return {
                "success": False,
                "error": "Invalid target path: outside workspace"
            }

        # Create directory if needed
        os.makedirs(target_dir, exist_ok=True)

        # Sanitize filename
        safe_filename = os.path.basename(file.filename) if file.filename else "uploaded_file"
        # Remove potentially dangerous characters
        safe_filename = "".join(c for c in safe_filename if c.isalnum() or c in '._-')
        if not safe_filename:
            safe_filename = "uploaded_file"

        file_path = os.path.join(target_dir, safe_filename)

        # Write file
        content = await file.read()
        async with aiofiles.open(file_path, 'wb') as f:
            await f.write(content)

        logger.info(f"Uploaded file: {file_path} ({len(content)} bytes)")

        return {
            "success": True,
            "filename": safe_filename,
            "path": file_path,
            "relative_path": os.path.relpath(file_path, workspace),
            "size": len(content),
            "workspace": workspace
        }

    except Exception as e:
        logger.error(f"Error uploading file: {e}")
        return {"success": False, "error": str(e)}


@router.post("/workspace/upload-multiple")
async def upload_multiple_files(
    files: List[UploadFile] = File(...),
    session_id: str = Form("default"),
    sub_path: str = Form("")
):
    """Upload multiple files to the session's workspace.

    Args:
        files: List of files to upload
        session_id: Session identifier
        sub_path: Optional subdirectory within workspace

    Returns:
        Upload results for all files
    """
    import os
    import aiofiles

    try:
        workspace = await session_store.get_workspace(session_id)

        # Construct target path
        if sub_path:
            target_dir = os.path.join(workspace, sub_path)
        else:
            target_dir = workspace

        # Validate target path
        target_dir = os.path.normpath(target_dir)
        if not target_dir.startswith(os.path.normpath(workspace)):
            return {
                "success": False,
                "error": "Invalid target path: outside workspace"
            }

        os.makedirs(target_dir, exist_ok=True)

        results = []
        total_size = 0

        for file in files:
            try:
                # Sanitize filename
                safe_filename = os.path.basename(file.filename) if file.filename else f"file_{len(results)}"
                safe_filename = "".join(c for c in safe_filename if c.isalnum() or c in '._-')
                if not safe_filename:
                    safe_filename = f"file_{len(results)}"

                file_path = os.path.join(target_dir, safe_filename)

                # Write file
                content = await file.read()
                async with aiofiles.open(file_path, 'wb') as f:
                    await f.write(content)

                total_size += len(content)

                results.append({
                    "success": True,
                    "filename": safe_filename,
                    "original_filename": file.filename,
                    "path": file_path,
                    "relative_path": os.path.relpath(file_path, workspace),
                    "size": len(content)
                })

                logger.info(f"Uploaded file: {file_path}")

            except Exception as e:
                results.append({
                    "success": False,
                    "filename": file.filename,
                    "error": str(e)
                })

        successful = sum(1 for r in results if r.get("success"))

        return {
            "success": successful == len(files),
            "total_files": len(files),
            "successful": successful,
            "failed": len(files) - successful,
            "total_size": total_size,
            "workspace": workspace,
            "target_dir": target_dir,
            "files": results
        }

    except Exception as e:
        logger.error(f"Error uploading files: {e}")
        return {"success": False, "error": str(e)}


@router.post("/workspace/upload-directory")
async def upload_directory_structure(
    files: List[UploadFile] = File(...),
    session_id: str = Form("default"),
    base_path: str = Form("")
):
    """Upload files maintaining their directory structure.

    Frontend should send files with their relative paths in the filename.
    For example: "src/components/App.tsx"

    Args:
        files: List of files with relative path prefixes
        session_id: Session identifier
        base_path: Base path within workspace to put files

    Returns:
        Upload results with directory structure preserved
    """
    import os
    import aiofiles

    try:
        workspace = await session_store.get_workspace(session_id)

        # Base target directory
        if base_path:
            target_base = os.path.join(workspace, base_path)
        else:
            target_base = workspace

        target_base = os.path.normpath(target_base)
        if not target_base.startswith(os.path.normpath(workspace)):
            return {
                "success": False,
                "error": "Invalid base path: outside workspace"
            }

        results = []
        directories_created = set()
        total_size = 0

        for file in files:
            try:
                # Use original filename which may include path separators
                original_path = file.filename or f"file_{len(results)}"

                # Normalize path separators and sanitize
                normalized_path = original_path.replace('\\', '/')

                # Prevent path traversal
                if '..' in normalized_path:
                    results.append({
                        "success": False,
                        "filename": original_path,
                        "error": "Path traversal not allowed"
                    })
                    continue

                # Construct full path
                file_path = os.path.normpath(os.path.join(target_base, normalized_path))

                # Security check
                if not file_path.startswith(os.path.normpath(target_base)):
                    results.append({
                        "success": False,
                        "filename": original_path,
                        "error": "Path outside target directory"
                    })
                    continue

                # Create parent directories
                parent_dir = os.path.dirname(file_path)
                if parent_dir not in directories_created:
                    os.makedirs(parent_dir, exist_ok=True)
                    directories_created.add(parent_dir)

                # Write file
                content = await file.read()
                async with aiofiles.open(file_path, 'wb') as f:
                    await f.write(content)

                total_size += len(content)

                results.append({
                    "success": True,
                    "original_path": original_path,
                    "saved_path": file_path,
                    "relative_path": os.path.relpath(file_path, workspace),
                    "size": len(content)
                })

            except Exception as e:
                results.append({
                    "success": False,
                    "filename": file.filename,
                    "error": str(e)
                })

        successful = sum(1 for r in results if r.get("success"))

        return {
            "success": successful == len(files),
            "total_files": len(files),
            "successful": successful,
            "failed": len(files) - successful,
            "total_size": total_size,
            "directories_created": len(directories_created),
            "workspace": workspace,
            "target_base": target_base,
            "files": results
        }

    except Exception as e:
        logger.error(f"Error uploading directory structure: {e}")
        return {"success": False, "error": str(e)}


# ==================== File Read Endpoint ====================


@router.get("/files/read")
async def read_file_content(path: str):
    """Read file content by absolute path.

    Security: Only allows reading from configured workspace.

    Args:
        path: Absolute path to file

    Returns:
        File content and metadata
    """
    import os

    BASE_WORKSPACE = Path(settings.default_workspace)

    try:
        # Validate path is within allowed base
        validated_path = sanitize_path(path, BASE_WORKSPACE, allow_creation=False)

        if not validated_path.exists():
            raise HTTPException(status_code=404, detail="File not found")

        if not validated_path.is_file():
            raise HTTPException(status_code=400, detail="Path is not a file")

        # Read file content
        content = validated_path.read_text(encoding='utf-8')

        return {
            "success": True,
            "path": str(validated_path),
            "content": content,
            "size": validated_path.stat().st_size
        }

    except SecurityError as e:
        logger.warning(f"Security violation in read_file_content: {e}")
        raise HTTPException(status_code=403, detail="Access denied")
    except UnicodeDecodeError:
        raise HTTPException(status_code=400, detail="File is not a text file")
    except Exception as e:
        logger.error(f"Error reading file: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/workspace/download")
async def download_workspace_path(
    workspace_path: str,
    format: str = Query("zip", pattern="^(zip|tar)$")
):
    """Download any workspace directory as archive.

    Args:
        workspace_path: Full path to workspace directory
        format: Archive format ('zip' or 'tar')

    Returns:
        Streaming file download
    """
    import os
    import io
    import zipfile
    import tarfile
    from datetime import datetime

    # Security: Validate path is within allowed base
    BASE_WORKSPACE = Path(settings.default_workspace)

    try:
        validated_path = sanitize_path(workspace_path, BASE_WORKSPACE, allow_creation=False)
    except SecurityError as e:
        raise HTTPException(status_code=403, detail=str(e))

    if not validated_path.exists():
        raise HTTPException(status_code=404, detail="Workspace not found")

    if not validated_path.is_dir():
        raise HTTPException(status_code=400, detail="Path is not a directory")

    project_name = validated_path.name or "workspace"
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    archive_name = f"{project_name}_{timestamp}"

    skip_dirs = {'.git', 'node_modules', '__pycache__', 'venv', '.venv', 'dist', 'build', '.next'}
    skip_files = {'.DS_Store', 'Thumbs.db'}

    try:
        if format == "zip":
            zip_buffer = io.BytesIO()

            with zipfile.ZipFile(zip_buffer, 'w', zipfile.ZIP_DEFLATED) as zip_file:
                for root, dirs, files in os.walk(str(validated_path)):
                    dirs[:] = [d for d in dirs if d not in skip_dirs and not d.startswith('.')]

                    for file in files:
                        if file in skip_files or file.startswith('.'):
                            continue

                        file_path = os.path.join(root, file)
                        arc_name = os.path.relpath(file_path, str(validated_path))

                        try:
                            zip_file.write(file_path, arc_name)
                        except (PermissionError, OSError):
                            pass

            zip_buffer.seek(0)

            return StreamingResponse(
                zip_buffer,
                media_type="application/zip",
                headers={
                    "Content-Disposition": f'attachment; filename="{archive_name}.zip"'
                }
            )

        else:
            tar_buffer = io.BytesIO()

            with tarfile.open(fileobj=tar_buffer, mode='w:gz') as tar_file:
                for root, dirs, files in os.walk(str(validated_path)):
                    dirs[:] = [d for d in dirs if d not in skip_dirs and not d.startswith('.')]

                    for file in files:
                        if file in skip_files or file.startswith('.'):
                            continue

                        file_path = os.path.join(root, file)
                        arc_name = os.path.relpath(file_path, str(validated_path))

                        try:
                            tar_file.add(file_path, arcname=arc_name)
                        except (PermissionError, OSError):
                            pass

            tar_buffer.seek(0)

            return StreamingResponse(
                tar_buffer,
                media_type="application/gzip",
                headers={
                    "Content-Disposition": f'attachment; filename="{archive_name}.tar.gz"'
                }
            )

    except Exception as e:
        logger.error(f"Error creating archive: {e}")
        raise HTTPException(status_code=500, detail=str(e))

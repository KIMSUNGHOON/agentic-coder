"""Cache Management API Routes

FastAPI endpoints for cache and context management.
Provides functionality to clear LLM cache, session context, and workspace context.
"""

import logging
from typing import Optional
from fastapi import APIRouter, HTTPException, Depends
from pydantic import BaseModel

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/cache", tags=["cache"])


class ClearCacheResponse(BaseModel):
    """Response for cache clear operations"""
    success: bool
    cleared_count: int
    message: str


class CacheStatsResponse(BaseModel):
    """Response for cache statistics"""
    backend: str
    entry_count: int
    ttl_hours: int
    used_memory: Optional[str] = None
    cache_dir: Optional[str] = None


class ClearContextRequest(BaseModel):
    """Request to clear context"""
    clear_messages: bool = True
    clear_workflow_state: bool = True
    clear_workspace_context: bool = False


# ==================== LLM Cache Management ====================

@router.get("/stats")
async def get_cache_stats() -> CacheStatsResponse:
    """Get LLM cache statistics

    Returns:
        Cache statistics including entry count and memory usage
    """
    try:
        from app.services.lm_cache import lm_cache

        stats = lm_cache.get_stats()
        return CacheStatsResponse(
            backend=stats.get("backend", "unknown"),
            entry_count=stats.get("entry_count", 0),
            ttl_hours=stats.get("ttl_hours", 24),
            used_memory=stats.get("used_memory"),
            cache_dir=stats.get("cache_dir"),
        )
    except Exception as e:
        logger.error(f"Error getting cache stats: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/clear")
async def clear_lm_cache() -> ClearCacheResponse:
    """Clear all LLM response cache

    This clears the global LLM response cache.
    Useful when you want fresh responses from the LLM.

    Returns:
        Number of cache entries cleared
    """
    try:
        from app.services.lm_cache import lm_cache

        count = lm_cache.clear()
        logger.info(f"Cleared {count} LLM cache entries")

        return ClearCacheResponse(
            success=True,
            cleared_count=count,
            message=f"Successfully cleared {count} cache entries"
        )
    except Exception as e:
        logger.error(f"Error clearing cache: {e}")
        raise HTTPException(status_code=500, detail=str(e))


# ==================== Session Context Management ====================

@router.post("/sessions/{session_id}/clear")
async def clear_session_context(
    session_id: str,
    request: ClearContextRequest = ClearContextRequest()
) -> ClearCacheResponse:
    """Clear session context and conversation history

    This clears:
    - Conversation messages (if clear_messages=True)
    - Workflow state (if clear_workflow_state=True)
    - Workspace .ai_context.json (if clear_workspace_context=True)

    Args:
        session_id: Session ID to clear
        request: Options for what to clear

    Returns:
        Summary of what was cleared
    """
    try:
        from app.db.database import get_db
        from app.db.models import Conversation, Message

        db = next(get_db())
        cleared_count = 0
        messages = []

        # Find conversation
        conversation = db.query(Conversation).filter(
            Conversation.session_id == session_id
        ).first()

        if not conversation:
            raise HTTPException(status_code=404, detail=f"Session {session_id} not found")

        # Clear messages
        if request.clear_messages:
            msg_count = db.query(Message).filter(
                Message.conversation_id == conversation.id
            ).delete()
            cleared_count += msg_count
            messages.append(f"Cleared {msg_count} messages")

        # Clear workflow state
        if request.clear_workflow_state and conversation.workflow_state:
            conversation.workflow_state = None
            cleared_count += 1
            messages.append("Cleared workflow state")

        db.commit()

        # Clear workspace context file
        if request.clear_workspace_context and conversation.workspace_path:
            import os
            context_file = os.path.join(conversation.workspace_path, ".ai_context.json")
            if os.path.exists(context_file):
                os.remove(context_file)
                cleared_count += 1
                messages.append("Cleared workspace context file")

        logger.info(f"Cleared session context for {session_id}: {', '.join(messages)}")

        return ClearCacheResponse(
            success=True,
            cleared_count=cleared_count,
            message="; ".join(messages) if messages else "Nothing to clear"
        )

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error clearing session context: {e}")
        raise HTTPException(status_code=500, detail=str(e))


# ==================== Workspace Context Management ====================

@router.post("/workspace/clear")
async def clear_workspace_context(workspace_path: str) -> ClearCacheResponse:
    """Clear workspace context file (.ai_context.json)

    This clears the AI context file that stores:
    - Workflow history
    - Project information
    - Recommended next tasks

    Args:
        workspace_path: Path to workspace directory

    Returns:
        Success status
    """
    import os

    try:
        # Validate path
        if not workspace_path or not os.path.isabs(workspace_path):
            raise HTTPException(status_code=400, detail="Invalid workspace path")

        if not os.path.isdir(workspace_path):
            raise HTTPException(status_code=404, detail="Workspace directory not found")

        context_file = os.path.join(workspace_path, ".ai_context.json")

        if os.path.exists(context_file):
            os.remove(context_file)
            logger.info(f"Cleared workspace context: {context_file}")
            return ClearCacheResponse(
                success=True,
                cleared_count=1,
                message=f"Cleared context file from {workspace_path}"
            )
        else:
            return ClearCacheResponse(
                success=True,
                cleared_count=0,
                message="No context file found to clear"
            )

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error clearing workspace context: {e}")
        raise HTTPException(status_code=500, detail=str(e))


# ==================== Combined Clear All ====================

@router.post("/clear-all")
async def clear_all_cache() -> ClearCacheResponse:
    """Clear all caches (LLM cache and expired entries)

    Use this for a complete cache reset.

    Returns:
        Total number of entries cleared
    """
    try:
        from app.services.lm_cache import lm_cache

        # Clear LLM cache
        lm_count = lm_cache.clear()

        # Cleanup expired entries (if any remain)
        expired_count = lm_cache.cleanup_expired()

        total = lm_count + expired_count

        logger.info(f"Cleared all cache: {lm_count} LLM entries, {expired_count} expired entries")

        return ClearCacheResponse(
            success=True,
            cleared_count=total,
            message=f"Cleared {lm_count} LLM cache entries, {expired_count} expired entries"
        )

    except Exception as e:
        logger.error(f"Error clearing all cache: {e}")
        raise HTTPException(status_code=500, detail=str(e))

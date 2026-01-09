"""Session API Routes for Remote Client

FastAPI endpoints for remote client session management.
Provides RESTful session-based API for remote CLI access.
"""

import logging
import uuid
import os
from typing import Optional, AsyncGenerator
from fastapi import APIRouter, HTTPException
from fastapi.responses import StreamingResponse
from pydantic import BaseModel
import json

from app.core.config import settings
from app.agent.langgraph.dynamic_workflow import dynamic_workflow

logger = logging.getLogger(__name__)

router = APIRouter(prefix="", tags=["sessions"])  # No prefix - will be added at /api level


# ============================================================================
# Request/Response Models
# ============================================================================

class SessionCreateRequest(BaseModel):
    """Request to create a new session"""
    workspace: Optional[str] = None  # Optional workspace override


class SessionCreateResponse(BaseModel):
    """Response from session creation"""
    session_id: str
    workspace: str
    message: str


class SessionExecuteRequest(BaseModel):
    """Request to execute code in a session"""
    user_request: str
    execution_mode: str = "auto"  # "auto", "quick", "full"
    enable_debug: bool = False


# ============================================================================
# Session Store (in-memory for now)
# ============================================================================

class SessionStore:
    """Simple in-memory session storage"""

    def __init__(self):
        self.sessions = {}

    def create_session(self, workspace: Optional[str] = None) -> dict:
        """Create a new session

        Args:
            workspace: Optional custom workspace path

        Returns:
            Session info dictionary
        """
        session_id = f"session-{uuid.uuid4().hex[:12]}"

        # Generate workspace path: $DEFAULT_WORKSPACE/session_id
        if workspace:
            workspace_path = os.path.abspath(workspace)
        else:
            base_workspace = os.getenv("DEFAULT_WORKSPACE", os.getcwd())
            workspace_path = os.path.join(base_workspace, session_id)

        # Create workspace directory
        os.makedirs(workspace_path, exist_ok=True)

        session_info = {
            "session_id": session_id,
            "workspace": workspace_path,
            "created_at": None,  # Could add timestamp
            "status": "active"
        }

        self.sessions[session_id] = session_info
        logger.info(f"✅ Created session {session_id}")
        logger.info(f"   Workspace: {workspace_path}")

        return session_info

    def get_session(self, session_id: str) -> Optional[dict]:
        """Get session info by ID

        Args:
            session_id: Session identifier

        Returns:
            Session info or None if not found
        """
        return self.sessions.get(session_id)


# Global session store
session_store = SessionStore()


# ============================================================================
# API Endpoints
# ============================================================================

@router.post("/sessions", response_model=SessionCreateResponse)
async def create_session(request: SessionCreateRequest):
    """Create a new coding session

    Creates an isolated workspace for the session and returns session ID.

    Args:
        request: Session creation request with optional workspace

    Returns:
        Session information including ID and workspace path
    """
    try:
        session_info = session_store.create_session(request.workspace)

        return SessionCreateResponse(
            session_id=session_info["session_id"],
            workspace=session_info["workspace"],
            message="Session created successfully"
        )

    except Exception as e:
        logger.error(f"Failed to create session: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to create session: {str(e)}")


@router.get("/sessions/{session_id}")
async def get_session(session_id: str):
    """Get session information

    Args:
        session_id: Session identifier

    Returns:
        Session information
    """
    session_info = session_store.get_session(session_id)

    if not session_info:
        raise HTTPException(status_code=404, detail=f"Session {session_id} not found")

    return session_info


@router.post("/sessions/{session_id}/execute")
async def execute_in_session(session_id: str, request: SessionExecuteRequest):
    """Execute a request in the session with Server-Sent Events (SSE) streaming

    This endpoint streams workflow execution updates in real-time using SSE.

    Args:
        session_id: Session identifier
        request: Execution request with user's coding task

    Returns:
        StreamingResponse with SSE events
    """
    # Verify session exists
    session_info = session_store.get_session(session_id)
    if not session_info:
        raise HTTPException(status_code=404, detail=f"Session {session_id} not found")

    workspace = session_info["workspace"]

    logger.info(f"🚀 Executing request in session {session_id}")
    logger.info(f"   Request: {request.user_request[:100]}")
    logger.info(f"   Workspace: {workspace}")
    logger.info(f"   Mode: {request.execution_mode}")

    async def event_stream() -> AsyncGenerator[str, None]:
        """Generate SSE events from workflow execution

        SSE Format:
            event: <event_type>
            data: <json_data>
        """
        try:
            # Prepare workflow input
            workflow_input = {
                "user_request": request.user_request,
                "workspace_root": workspace,
                "task_type": "general",
                "execution_mode": request.execution_mode,
                "enable_debug": request.enable_debug
            }

            # Stream workflow execution
            async for chunk in dynamic_workflow.astream(workflow_input):
                # Each chunk is a dict with node outputs
                for node_name, node_output in chunk.items():
                    if isinstance(node_output, dict):
                        # Determine event type from node output
                        event_type = "update"

                        if "supervisor_decision" in node_output:
                            event_type = "supervisor"
                        elif "tool_name" in node_output:
                            event_type = "tool"
                        elif "response" in node_output:
                            event_type = "response"
                        elif "error" in node_output:
                            event_type = "error"

                        # Format as SSE
                        event_data = {
                            "node": node_name,
                            "data": node_output
                        }

                        yield f"event: {event_type}\n"
                        yield f"data: {json.dumps(event_data)}\n\n"

            # Send completion event
            completion_data = {
                "session_id": session_id,
                "status": "completed"
            }
            yield f"event: complete\n"
            yield f"data: {json.dumps(completion_data)}\n\n"

        except Exception as e:
            logger.error(f"Error during execution: {e}")
            error_data = {
                "error": str(e),
                "session_id": session_id
            }
            yield f"event: error\n"
            yield f"data: {json.dumps(error_data)}\n\n"

    return StreamingResponse(
        event_stream(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no"  # Disable nginx buffering
        }
    )


@router.delete("/sessions/{session_id}")
async def delete_session(session_id: str):
    """Delete a session

    Args:
        session_id: Session identifier

    Returns:
        Confirmation message
    """
    session_info = session_store.get_session(session_id)

    if not session_info:
        raise HTTPException(status_code=404, detail=f"Session {session_id} not found")

    # Remove from store
    del session_store.sessions[session_id]

    logger.info(f"🗑️  Deleted session {session_id}")

    return {
        "message": f"Session {session_id} deleted",
        "session_id": session_id
    }

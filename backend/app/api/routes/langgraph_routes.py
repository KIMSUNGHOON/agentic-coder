"""LangGraph API Routes

FastAPI endpoints for unified LangGraph workflow execution.
Supports enhanced workflow with streaming, HITL, and progress tracking.
"""

import logging
from typing import AsyncGenerator
from fastapi import APIRouter, HTTPException
from fastapi.responses import StreamingResponse
from pydantic import BaseModel
import json

# Import both workflows for flexibility
from app.agent.langgraph.unified_workflow import unified_workflow
from app.agent.langgraph.enhanced_workflow import enhanced_workflow

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/langgraph", tags=["langgraph"])


class WorkflowRequest(BaseModel):
    """Request to execute workflow"""
    user_request: str
    workspace_root: str
    task_type: str = "general"
    execution_mode: str = "auto"  # "auto", "quick" (Q&A only), "full" (full pipeline)
    enable_debug: bool = True
    use_enhanced: bool = True  # Use enhanced workflow by default
    system_prompt: str = ""  # Optional custom system prompt for context


class ApprovalRequest(BaseModel):
    """Request to approve/reject changes"""
    session_id: str
    approved: bool
    message: str = ""


@router.post("/execute")
async def execute_workflow(request: WorkflowRequest):
    """Execute LangGraph workflow with real-time streaming

    This endpoint starts the workflow and streams results including:
    - Agent thinking/reasoning
    - Code generation progress
    - Quality gate results
    - HITL checkpoints
    - Execution times per agent
    - ETA updates

    Supports different execution modes:
    - "auto": Automatically detect if full pipeline is needed
    - "quick": Q&A mode - uses Supervisor only for fast responses
    - "full": Full code generation pipeline with all agents

    CRITICAL: This endpoint performs REAL file operations in "full" mode.

    Args:
        request: Workflow execution request

    Returns:
        Streaming response with workflow updates
    """
    logger.info(f"🚀 Starting workflow execution")
    logger.info(f"   Request: {request.user_request[:100]}")
    logger.info(f"   Workspace: {request.workspace_root}")
    logger.info(f"   Execution Mode: {request.execution_mode}")
    logger.info(f"   Enhanced Mode: {request.use_enhanced}")

    # Determine actual execution mode
    execution_mode = request.execution_mode
    if execution_mode == "auto":
        # Simple heuristic: if request contains code-related keywords, use full pipeline
        code_keywords = ["코드", "구현", "개발", "프로젝트", "앱", "애플리케이션", "함수", "클래스",
                        "code", "implement", "develop", "create", "build", "app", "application",
                        "function", "class", "api", "서비스", "service", "make", "만들"]
        if any(kw in request.user_request.lower() for kw in code_keywords):
            execution_mode = "full"
        else:
            execution_mode = "quick"
        logger.info(f"   Auto-detected mode: {execution_mode}")

    async def event_stream() -> AsyncGenerator[str, None]:
        """Stream workflow events to client"""
        try:
            if execution_mode == "quick":
                # Quick Q&A mode - use Supervisor only
                async for update in quick_qa_response(
                    request.user_request,
                    request.workspace_root,
                    request.system_prompt
                ):
                    enriched_update = {
                        **update,
                        "workflow_type": "quick_qa",
                        "execution_mode": execution_mode,
                    }
                    event_data = json.dumps(enriched_update, default=str)
                    yield f"data: {event_data}\n\n"
            else:
                # Full pipeline mode
                workflow = enhanced_workflow if request.use_enhanced else unified_workflow

                async for update in workflow.execute(
                    user_request=request.user_request,
                    workspace_root=request.workspace_root,
                    task_type=request.task_type,
                    enable_debug=request.enable_debug,
                    system_prompt=request.system_prompt
                ):
                    enriched_update = {
                        **update,
                        "workflow_type": "enhanced" if request.use_enhanced else "unified",
                        "execution_mode": execution_mode,
                    }
                    event_data = json.dumps(enriched_update, default=str)
                    yield f"data: {event_data}\n\n"

        except Exception as e:
            logger.error(f"❌ Error in workflow execution: {e}", exc_info=True)
            error_data = json.dumps({
                "node": "ERROR",
                "status": "error",
                "agent_title": "❌ Error",
                "agent_description": "Workflow failed",
                "updates": {"error": str(e)},
            })
            yield f"data: {error_data}\n\n"

    return StreamingResponse(
        event_stream(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "X-Accel-Buffering": "no",
            "Connection": "keep-alive"
        }
    )


async def quick_qa_response(user_request: str, workspace_root: str, system_prompt: str = "") -> AsyncGenerator[dict, None]:
    """Quick Q&A mode - uses Supervisor for fast responses without full pipeline

    This mode is optimized for:
    - General questions about coding concepts
    - Quick explanations
    - Simple queries that don't require code generation
    """
    import time
    from core.supervisor import SupervisorAgent

    start_time = time.time()

    # Emit starting status
    yield {
        "node": "supervisor",
        "status": "starting",
        "agent_title": "🧠 Supervisor",
        "agent_description": "Quick Response Mode",
        "updates": {"message": "Processing your question..."}
    }

    try:
        supervisor = SupervisorAgent(use_api=True)

        # Emit thinking status
        yield {
            "node": "supervisor",
            "status": "thinking",
            "agent_title": "🧠 Supervisor",
            "agent_description": "Analyzing question",
            "updates": {"message": "Analyzing your question..."}
        }

        # Build context with optional system prompt
        context = {
            "workspace_root": workspace_root,
            "mode": "quick_qa"
        }
        if system_prompt:
            context["system_prompt"] = system_prompt

        # Get quick response from supervisor (synchronous method returns Dict)
        analysis = supervisor.analyze_request(user_request, context=context)

        execution_time = time.time() - start_time

        # Extract values from dict (analyze_request returns a dict, not an object)
        task_type = analysis.get('task_type', 'general')
        complexity = analysis.get('complexity', 'medium')
        reasoning = analysis.get('reasoning', analysis.get('workflow_strategy', 'No detailed analysis available.'))

        # Format response
        response_content = f"""## 분석 결과

**질문 유형:** {task_type}
**복잡도:** {complexity}

### 응답

{reasoning}

---
*Quick Q&A 모드로 응답했습니다. 코드 생성이 필요하면 "코드 생성" 모드를 선택하세요.*
"""

        # Emit completed status with response
        yield {
            "node": "supervisor",
            "status": "completed",
            "agent_title": "🧠 Supervisor",
            "agent_description": "Response Ready",
            "updates": {
                "message": "Response generated",
                "streaming_content": response_content,
                "execution_time": execution_time,
                "analysis": {
                    "task_type": task_type,
                    "complexity": complexity,
                    "reasoning": reasoning,
                }
            }
        }

        # Emit workflow completion
        yield {
            "node": "workflow",
            "status": "completed",
            "agent_title": "✅ Complete",
            "agent_description": "Quick Q&A Complete",
            "updates": {
                "message": "Quick response generated",
                "execution_time": execution_time,
                "is_final": True,
            }
        }

    except Exception as e:
        logger.error(f"Error in quick Q&A: {e}", exc_info=True)
        yield {
            "node": "supervisor",
            "status": "error",
            "agent_title": "❌ Error",
            "agent_description": "Failed to generate response",
            "updates": {"error": str(e)}
        }


@router.post("/approve")
async def approve_changes(request: ApprovalRequest):
    """Process human approval decision

    Used for HITL checkpoints in the workflow.

    Args:
        request: Approval request

    Returns:
        Approval status
    """
    logger.info(f"🧑 Processing approval: {request.approved}")

    try:
        from app.hitl import get_hitl_manager

        hitl_manager = get_hitl_manager()

        # Submit the response
        from app.hitl.models import HITLResponse, HITLAction

        response = HITLResponse(
            request_id=request.session_id,
            action=HITLAction.APPROVE if request.approved else HITLAction.REJECT,
            feedback=request.message,
        )

        success = await hitl_manager.submit_response(response)

        return {
            "success": success,
            "session_id": request.session_id,
            "approved": request.approved,
            "message": request.message
        }

    except Exception as e:
        logger.error(f"❌ Error processing approval: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/status/{session_id}")
async def get_workflow_status(session_id: str):
    """Get current workflow status

    Args:
        session_id: Session ID

    Returns:
        Current workflow status including progress
    """
    logger.info(f"📊 Getting status for session: {session_id}")

    # In production, query the workflow state from checkpointer
    return {
        "session_id": session_id,
        "status": "running",
        "current_node": "coder",
        "progress": 0.5,
        "agents_completed": [],
        "agents_pending": [],
        "estimated_time_remaining": None
    }


@router.get("/debug/{session_id}")
async def get_debug_logs(session_id: str):
    """Get debug logs for a session

    Args:
        session_id: Session ID

    Returns:
        Debug logs with token usage
    """
    logger.info(f"🔍 Getting debug logs for session: {session_id}")

    return {
        "session_id": session_id,
        "logs": [],
        "total_tokens": 0,
        "token_breakdown": {}
    }


@router.get("/agents")
async def get_available_agents():
    """Get list of available agents and their descriptions

    Returns:
        Agent information for UI display
    """
    from app.agent.langgraph.enhanced_workflow import AGENT_INFO

    return {
        "agents": AGENT_INFO,
        "workflow_types": {
            "enhanced": "Full workflow with Architect, parallel execution, and HITL",
            "unified": "Standard sequential workflow"
        }
    }

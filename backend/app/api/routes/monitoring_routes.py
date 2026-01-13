"""
Monitoring API Routes

Provides endpoints for monitoring and statistics:
- Session statistics
- Workspace usage
- Tool usage analytics
- Session cleanup
"""

from fastapi import APIRouter, Query, HTTPException
from typing import Optional
import os
from pathlib import Path

router = APIRouter(prefix="/monitoring", tags=["monitoring"])


@router.get("/sessions")
async def list_all_sessions(
    workspace: Optional[str] = Query(None, description="Base workspace path")
):
    """List all sessions with basic statistics

    Returns list of sessions with:
    - Session ID
    - Created/updated timestamps
    - Message count
    - Workspace size
    """
    from cli.session_manager import SessionManager

    if workspace is None:
        workspace = os.getenv("DEFAULT_WORKSPACE", ".")

    base_path = Path(workspace).resolve()
    session_dir = base_path / ".agentic-coder" / "sessions"

    if not session_dir.exists():
        return {"sessions": [], "total": 0}

    sessions = []
    total_size_mb = 0

    for session_file in session_dir.glob("session-*.json"):
        try:
            import json
            with open(session_file, 'r', encoding='utf-8') as f:
                data = json.load(f)

            metadata = data.get("metadata", {})
            session_id = data.get("session_id", session_file.stem)

            # Calculate workspace size
            workspace_path = base_path / session_id
            workspace_size = 0
            if workspace_path.exists():
                for root, dirs, files in os.walk(workspace_path):
                    for file in files:
                        try:
                            workspace_size += os.path.getsize(os.path.join(root, file))
                        except (OSError, FileNotFoundError):
                            pass

            size_mb = round(workspace_size / (1024 * 1024), 2)
            total_size_mb += size_mb

            sessions.append({
                "session_id": session_id,
                "created_at": metadata.get("created_at", "Unknown"),
                "updated_at": metadata.get("updated_at", "Unknown"),
                "message_count": metadata.get("message_count", 0),
                "workspace_size_mb": size_mb,
                "model": metadata.get("model", "Unknown")
            })

        except Exception:
            continue

    # Sort by updated_at (most recent first)
    sessions.sort(key=lambda s: s.get("updated_at", ""), reverse=True)

    return {
        "sessions": sessions,
        "total": len(sessions),
        "total_size_mb": round(total_size_mb, 2)
    }


@router.get("/sessions/{session_id}/statistics")
async def get_session_statistics(
    session_id: str,
    workspace: Optional[str] = Query(None, description="Base workspace path")
):
    """Get detailed statistics for a specific session

    Returns:
    - Tool usage statistics
    - Workspace usage
    - File operations
    - Session duration
    - Error count
    """
    from cli.session_manager import SessionManager

    if workspace is None:
        workspace = os.getenv("DEFAULT_WORKSPACE", ".")

    try:
        # Load session
        session_mgr = SessionManager(workspace=workspace, session_id=session_id)

        # Get statistics summary
        stats = session_mgr.get_statistics_summary()

        return {
            "success": True,
            "statistics": stats
        }

    except FileNotFoundError:
        raise HTTPException(status_code=404, detail=f"Session '{session_id}' not found")
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/workspace/usage")
async def get_workspace_usage(
    workspace: Optional[str] = Query(None, description="Base workspace path")
):
    """Get overall workspace usage across all sessions

    Returns:
    - Total size
    - Session count
    - Largest sessions
    - Largest files
    """
    if workspace is None:
        workspace = os.getenv("DEFAULT_WORKSPACE", ".")

    base_path = Path(workspace).resolve()

    total_size = 0
    session_sizes = []

    # Iterate through session directories
    for session_dir in base_path.glob("session-*"):
        if session_dir.is_dir():
            session_size = 0
            file_count = 0

            for root, dirs, files in os.walk(session_dir):
                for file in files:
                    try:
                        size = os.path.getsize(os.path.join(root, file))
                        session_size += size
                        file_count += 1
                    except (OSError, FileNotFoundError):
                        pass

            if session_size > 0:
                session_sizes.append({
                    "session_id": session_dir.name,
                    "size_mb": round(session_size / (1024 * 1024), 2),
                    "file_count": file_count
                })
                total_size += session_size

    # Sort by size (largest first)
    session_sizes.sort(key=lambda x: x["size_mb"], reverse=True)

    return {
        "total_size_mb": round(total_size / (1024 * 1024), 2),
        "session_count": len(session_sizes),
        "largest_sessions": session_sizes[:10],
        "workspace_path": str(base_path)
    }


@router.get("/tools/usage")
async def get_tool_usage_statistics(
    workspace: Optional[str] = Query(None, description="Base workspace path")
):
    """Get aggregated tool usage statistics across all sessions

    Returns:
    - Most used tools
    - Success/failure rates
    - Total usage counts
    """
    from cli.session_manager import SessionManager

    if workspace is None:
        workspace = os.getenv("DEFAULT_WORKSPACE", ".")

    base_path = Path(workspace).resolve()
    session_dir = base_path / ".agentic-coder" / "sessions"

    if not session_dir.exists():
        return {"tools": [], "total_usage": 0}

    # Aggregate tool usage across all sessions
    aggregated_tools = {}
    total_usage = 0

    for session_file in session_dir.glob("session-*.json"):
        try:
            import json
            with open(session_file, 'r', encoding='utf-8') as f:
                data = json.load(f)

            metadata = data.get("metadata", {})
            statistics = metadata.get("statistics", {})
            tool_usage = statistics.get("tool_usage", {})

            for tool_name, counts in tool_usage.items():
                if tool_name not in aggregated_tools:
                    aggregated_tools[tool_name] = {"success": 0, "failure": 0}

                aggregated_tools[tool_name]["success"] += counts.get("success", 0)
                aggregated_tools[tool_name]["failure"] += counts.get("failure", 0)
                total_usage += counts.get("success", 0) + counts.get("failure", 0)

        except Exception:
            continue

    # Convert to list and calculate totals
    tools = [
        {
            "tool": name,
            "success": counts["success"],
            "failure": counts["failure"],
            "total": counts["success"] + counts["failure"],
            "success_rate": round(counts["success"] / (counts["success"] + counts["failure"]) * 100, 2)
                if (counts["success"] + counts["failure"]) > 0 else 0
        }
        for name, counts in aggregated_tools.items()
    ]

    # Sort by total usage (descending)
    tools.sort(key=lambda x: x["total"], reverse=True)

    return {
        "tools": tools,
        "total_usage": total_usage,
        "unique_tools": len(tools)
    }


@router.post("/cleanup/sessions")
async def cleanup_sessions(
    max_age_days: int = Query(30, description="Maximum session age in days"),
    max_size_mb: int = Query(1000, description="Maximum total workspace size in MB"),
    dry_run: bool = Query(True, description="If true, only simulate cleanup"),
    workspace: Optional[str] = Query(None, description="Base workspace path")
):
    """Clean up old or large sessions

    Args:
        max_age_days: Delete sessions older than this (default: 30 days)
        max_size_mb: Delete oldest sessions if total exceeds this (default: 1000 MB)
        dry_run: If true, only report what would be deleted (default: true)
        workspace: Base workspace path

    Returns:
        Cleanup statistics and deleted session details
    """
    from cli.session_manager import SessionManager

    if workspace is None:
        workspace = os.getenv("DEFAULT_WORKSPACE", ".")

    result = SessionManager.cleanup_old_sessions(
        base_workspace=workspace,
        max_age_days=max_age_days,
        max_size_mb=max_size_mb,
        dry_run=dry_run
    )

    return result


@router.get("/health/detailed")
async def get_detailed_health():
    """Get detailed health status including monitoring metrics

    Returns comprehensive system health:
    - Session count and total size
    - Tool usage summary
    - Workspace health
    - Recent errors
    """
    from cli.session_manager import SessionManager

    workspace = os.getenv("DEFAULT_WORKSPACE", ".")

    # Get workspace usage
    workspace_usage = await get_workspace_usage(workspace=workspace)

    # Get tool usage
    tool_usage = await get_tool_usage_statistics(workspace=workspace)

    # Get session list
    sessions = await list_all_sessions(workspace=workspace)

    # Get cleanup preview
    cleanup_preview = SessionManager.cleanup_old_sessions(
        base_workspace=workspace,
        max_age_days=30,
        max_size_mb=1000,
        dry_run=True
    )

    return {
        "status": "healthy",
        "workspace": {
            "total_size_mb": workspace_usage["total_size_mb"],
            "session_count": workspace_usage["session_count"]
        },
        "tools": {
            "total_usage": tool_usage["total_usage"],
            "unique_tools": tool_usage["unique_tools"],
            "top_5": tool_usage["tools"][:5]
        },
        "sessions": {
            "total": sessions["total"],
            "total_size_mb": sessions["total_size_mb"]
        },
        "cleanup": {
            "sessions_to_cleanup": cleanup_preview["sessions_to_delete"],
            "reclaimable_mb": sum(d["size_mb"] for d in cleanup_preview.get("details", []))
        }
    }

"""Debug Middleware for observability and debugging

Captures LLM interactions, tool calls, and agent thinking processes.
"""

import logging
from typing import Dict, Any, Optional
from datetime import datetime
from functools import wraps
from app.agent.langgraph.schemas.state import DebugLog

logger = logging.getLogger(__name__)


class DebugMiddleware:
    """Middleware for capturing debug information during workflow execution

    This middleware intercepts:
    - LLM prompts and responses
    - Tool calls and results
    - Agent thinking processes
    - Token usage statistics
    """

    def __init__(self, enable_debug: bool = True):
        """Initialize debug middleware

        Args:
            enable_debug: Whether to collect debug logs
        """
        self.enable_debug = enable_debug
        self.logs: list[DebugLog] = []

    def log_event(
        self,
        node: str,
        agent: str,
        event_type: str,
        content: str,
        metadata: Optional[Dict[str, Any]] = None,
        token_usage: Optional[Dict[str, int]] = None
    ) -> DebugLog:
        """Log a debug event

        Args:
            node: Node name (e.g., "refiner", "reviewer")
            agent: Agent name (e.g., "RefinerAgent", "ReviewerAgent")
            event_type: Type of event (thinking, tool_call, prompt, result, error)
            content: Event content
            metadata: Additional metadata
            token_usage: Token usage stats

        Returns:
            Created debug log entry
        """
        if not self.enable_debug:
            return None

        log_entry = DebugLog(
            timestamp=datetime.utcnow().isoformat(),
            node=node,
            agent=agent,
            event_type=event_type,
            content=content,
            metadata=metadata or {},
            token_usage=token_usage
        )

        self.logs.append(log_entry)
        logger.debug(f"[{node}/{agent}] {event_type}: {content[:100]}")

        return log_entry

    def log_thinking(self, node: str, agent: str, thinking: str):
        """Log agent thinking process"""
        return self.log_event(node, agent, "thinking", thinking)

    def log_prompt(self, node: str, agent: str, prompt: str):
        """Log LLM prompt"""
        return self.log_event(node, agent, "prompt", prompt)

    def log_tool_call(self, node: str, agent: str, tool_name: str, args: Dict):
        """Log tool call"""
        return self.log_event(
            node,
            agent,
            "tool_call",
            f"Calling {tool_name}",
            metadata={"tool": tool_name, "args": args}
        )

    def log_result(
        self,
        node: str,
        agent: str,
        result: str,
        token_usage: Optional[Dict[str, int]] = None
    ):
        """Log agent result"""
        return self.log_event(
            node,
            agent,
            "result",
            result,
            token_usage=token_usage
        )

    def log_error(self, node: str, agent: str, error: str):
        """Log error"""
        return self.log_event(node, agent, "error", error)

    def get_logs(self) -> list[DebugLog]:
        """Get all collected logs"""
        return self.logs

    def clear_logs(self):
        """Clear all logs"""
        self.logs.clear()

    def get_logs_for_node(self, node: str) -> list[DebugLog]:
        """Get logs for specific node

        Args:
            node: Node name

        Returns:
            List of debug logs for that node
        """
        return [log for log in self.logs if log["node"] == node]

    def get_summary(self) -> Dict[str, Any]:
        """Get summary of debug logs

        Returns:
            Summary statistics
        """
        summary = {
            "total_logs": len(self.logs),
            "by_node": {},
            "by_event_type": {},
            "total_tokens": 0
        }

        for log in self.logs:
            # Count by node
            node = log["node"]
            summary["by_node"][node] = summary["by_node"].get(node, 0) + 1

            # Count by event type
            event_type = log["event_type"]
            summary["by_event_type"][event_type] = summary["by_event_type"].get(event_type, 0) + 1

            # Sum tokens
            if log.get("token_usage"):
                summary["total_tokens"] += log["token_usage"].get("total_tokens", 0)

        return summary


def debug_node(node_name: str):
    """Decorator to automatically log node execution

    Usage:
        @debug_node("refiner")
        def refiner_node(state):
            ...

    Args:
        node_name: Name of the node

    Returns:
        Decorated function
    """
    def decorator(func):
        @wraps(func)
        def wrapper(state: Dict, *args, **kwargs):
            # Check if debug enabled
            enable_debug = state.get("enable_debug", False)
            if not enable_debug:
                return func(state, *args, **kwargs)

            # Log node entry
            logger.info(f"🔍 [DEBUG] Entering node: {node_name}")

            try:
                # Execute node
                result = func(state, *args, **kwargs)

                # Log node exit
                logger.info(f"✅ [DEBUG] Exiting node: {node_name}")

                return result

            except Exception as e:
                # Log error
                logger.error(f"❌ [DEBUG] Error in node {node_name}: {e}")
                raise

        return wrapper
    return decorator


# Global debug middleware instance
_debug_middleware = DebugMiddleware()


def get_debug_middleware() -> DebugMiddleware:
    """Get global debug middleware instance"""
    return _debug_middleware


def enable_debug():
    """Enable debug logging"""
    _debug_middleware.enable_debug = True


def disable_debug():
    """Disable debug logging"""
    _debug_middleware.enable_debug = False

"""Tool Logger for Agentic 2.0

Tracks tool calls:
- Tool execution logging
- Parameters and results
- Duration tracking
- Success/failure rates
"""

import json
from typing import Dict, Any, List, Optional
from dataclasses import dataclass, field, asdict
from datetime import datetime
from pathlib import Path


@dataclass
class ToolCall:
    """Tool call record"""

    call_id: str
    tool_name: str
    agent_name: str
    timestamp: datetime
    parameters: Dict[str, Any]
    result: Optional[Any] = None
    success: bool = True
    error: Optional[str] = None
    duration_seconds: float = 0.0
    context: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary"""
        d = asdict(self)
        d["timestamp"] = self.timestamp.isoformat()
        return d


class ToolLogger:
    """Tracks tool calls for observability

    Features:
    - Record all tool calls
    - Capture parameters and results
    - Track success/failure
    - Duration measurement
    - Export to JSONL

    Example:
        >>> logger = ToolLogger(log_file="logs/tools.jsonl")
        >>> call_id = logger.start_call(
        ...     tool_name="read_file",
        ...     agent_name="code_reader",
        ...     parameters={"file_path": "/path/to/file.py"}
        ... )
        >>> logger.end_call(call_id, result="file contents", success=True, duration=0.5)
    """

    def __init__(
        self,
        log_file: Optional[str] = None,
        auto_save: bool = True
    ):
        """Initialize tool logger

        Args:
            log_file: Path to JSONL log file for tool calls
            auto_save: Auto-save tool calls to file (default: True)
        """
        self.log_file = log_file
        self.auto_save = auto_save
        self.tool_calls: List[ToolCall] = []
        self._call_counter = 0
        self._active_calls: Dict[str, ToolCall] = {}

        # Create log file if specified
        if self.log_file:
            log_path = Path(self.log_file)
            log_path.parent.mkdir(parents=True, exist_ok=True)

    def start_call(
        self,
        tool_name: str,
        agent_name: str,
        parameters: Dict[str, Any],
        context: Optional[Dict[str, Any]] = None
    ) -> str:
        """Start tracking a tool call

        Args:
            tool_name: Name of the tool
            agent_name: Name of the agent calling the tool
            parameters: Tool parameters
            context: Additional context

        Returns:
            Call ID for tracking
        """
        self._call_counter += 1
        call_id = f"call_{self._call_counter:06d}"

        tool_call = ToolCall(
            call_id=call_id,
            tool_name=tool_name,
            agent_name=agent_name,
            timestamp=datetime.now(),
            parameters=parameters,
            context=context or {},
        )

        self._active_calls[call_id] = tool_call
        return call_id

    def end_call(
        self,
        call_id: str,
        result: Any = None,
        success: bool = True,
        error: Optional[str] = None,
        duration: float = 0.0
    ):
        """End tracking a tool call

        Args:
            call_id: Call ID from start_call
            result: Tool result
            success: Whether call succeeded
            error: Error message if failed
            duration: Duration in seconds
        """
        if call_id not in self._active_calls:
            return

        tool_call = self._active_calls[call_id]
        tool_call.result = result
        tool_call.success = success
        tool_call.error = error
        tool_call.duration_seconds = duration

        # Move to completed calls
        self.tool_calls.append(tool_call)
        del self._active_calls[call_id]

        # Auto-save to file
        if self.auto_save and self.log_file:
            self._save_call(tool_call)

    def log_call(
        self,
        tool_name: str,
        agent_name: str,
        parameters: Dict[str, Any],
        result: Any = None,
        success: bool = True,
        error: Optional[str] = None,
        duration: float = 0.0,
        context: Optional[Dict[str, Any]] = None
    ) -> ToolCall:
        """Log a completed tool call (convenience method)

        Args:
            tool_name: Name of the tool
            agent_name: Name of the agent
            parameters: Tool parameters
            result: Tool result
            success: Whether call succeeded
            error: Error message if failed
            duration: Duration in seconds
            context: Additional context

        Returns:
            ToolCall object
        """
        self._call_counter += 1
        call_id = f"call_{self._call_counter:06d}"

        tool_call = ToolCall(
            call_id=call_id,
            tool_name=tool_name,
            agent_name=agent_name,
            timestamp=datetime.now(),
            parameters=parameters,
            result=result,
            success=success,
            error=error,
            duration_seconds=duration,
            context=context or {},
        )

        self.tool_calls.append(tool_call)

        # Auto-save to file
        if self.auto_save and self.log_file:
            self._save_call(tool_call)

        return tool_call

    def get_calls(
        self,
        tool_name: Optional[str] = None,
        agent_name: Optional[str] = None,
        success_only: bool = False,
        limit: Optional[int] = None
    ) -> List[ToolCall]:
        """Get tool calls with optional filtering

        Args:
            tool_name: Filter by tool name
            agent_name: Filter by agent name
            success_only: Only return successful calls
            limit: Limit number of results

        Returns:
            List of ToolCall objects
        """
        filtered = self.tool_calls

        if tool_name:
            filtered = [c for c in filtered if c.tool_name == tool_name]

        if agent_name:
            filtered = [c for c in filtered if c.agent_name == agent_name]

        if success_only:
            filtered = [c for c in filtered if c.success]

        if limit:
            filtered = filtered[-limit:]

        return filtered

    def get_stats(self) -> Dict[str, Any]:
        """Get tool call statistics

        Returns:
            Dict with statistics
        """
        if not self.tool_calls:
            return {
                "total_calls": 0,
                "by_tool": {},
                "by_agent": {},
                "success_rate": 0.0,
                "avg_duration": 0.0,
            }

        # Count by tool
        by_tool: Dict[str, int] = {}
        for call in self.tool_calls:
            by_tool[call.tool_name] = by_tool.get(call.tool_name, 0) + 1

        # Count by agent
        by_agent: Dict[str, int] = {}
        for call in self.tool_calls:
            by_agent[call.agent_name] = by_agent.get(call.agent_name, 0) + 1

        # Success rate
        successes = sum(1 for c in self.tool_calls if c.success)
        success_rate = successes / len(self.tool_calls) if self.tool_calls else 0.0

        # Average duration
        total_duration = sum(c.duration_seconds for c in self.tool_calls)
        avg_duration = total_duration / len(self.tool_calls) if self.tool_calls else 0.0

        return {
            "total_calls": len(self.tool_calls),
            "by_tool": by_tool,
            "by_agent": by_agent,
            "success_rate": success_rate,
            "avg_duration": avg_duration,
        }

    def _save_call(self, tool_call: ToolCall):
        """Save single tool call to file"""
        if not self.log_file:
            return

        with open(self.log_file, "a") as f:
            f.write(json.dumps(tool_call.to_dict()) + "\n")

    def export_all(self, output_file: str):
        """Export all tool calls to file

        Args:
            output_file: Output file path
        """
        output_path = Path(output_file)
        output_path.parent.mkdir(parents=True, exist_ok=True)

        with open(output_file, "w") as f:
            for call in self.tool_calls:
                f.write(json.dumps(call.to_dict()) + "\n")

    def clear(self):
        """Clear all tool calls"""
        self.tool_calls.clear()
        self._call_counter = 0
        self._active_calls.clear()

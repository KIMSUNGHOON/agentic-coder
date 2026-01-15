"""Structured Logger for Agentic 2.0

JSONL structured logging:
- JSON-formatted log entries
- Multiple log levels
- Contextual information
- File and console output
"""

import json
import logging
from typing import Dict, Any, Optional
from datetime import datetime
from enum import Enum
from pathlib import Path


class LogLevel(str, Enum):
    """Log levels"""
    DEBUG = "DEBUG"
    INFO = "INFO"
    WARNING = "WARNING"
    ERROR = "ERROR"
    CRITICAL = "CRITICAL"


class StructuredLogger:
    """Structured logger with JSONL output

    Features:
    - JSON-formatted logs
    - Multiple outputs (file, console)
    - Contextual metadata
    - Automatic timestamping
    - Session and task tracking

    Example:
        >>> logger = StructuredLogger(log_file="logs/agent.jsonl")
        >>> logger.info("Task started", task_id="task_123", action="start")
        >>> logger.log_workflow("coding", iteration=1, status="running")
    """

    def __init__(
        self,
        log_file: Optional[str] = None,
        console_output: bool = True,
        include_timestamp: bool = True,
        include_level: bool = True,
    ):
        """Initialize structured logger

        Args:
            log_file: Path to JSONL log file (optional)
            console_output: Whether to output to console (default: True)
            include_timestamp: Include timestamp in logs (default: True)
            include_level: Include log level in logs (default: True)
        """
        self.log_file = log_file
        self.console_output = console_output
        self.include_timestamp = include_timestamp
        self.include_level = include_level

        # Create log file if specified
        if self.log_file:
            log_path = Path(self.log_file)
            log_path.parent.mkdir(parents=True, exist_ok=True)

        # Python logger for console
        self.python_logger = logging.getLogger(__name__)
        if not self.python_logger.handlers:
            handler = logging.StreamHandler()
            handler.setFormatter(logging.Formatter("%(message)s"))
            self.python_logger.addHandler(handler)
            self.python_logger.setLevel(logging.INFO)

    def log(
        self,
        level: LogLevel,
        message: str,
        **context: Any
    ):
        """Log a structured message

        Args:
            level: Log level
            message: Log message
            **context: Additional context as key-value pairs
        """
        # Build log entry
        entry: Dict[str, Any] = {
            "message": message,
        }

        if self.include_timestamp:
            entry["timestamp"] = datetime.now().isoformat()

        if self.include_level:
            entry["level"] = level.value

        # Add context
        entry.update(context)

        # Write to file as JSONL
        if self.log_file:
            with open(self.log_file, "a") as f:
                f.write(json.dumps(entry) + "\n")

        # Output to console
        if self.console_output:
            # Format for readability
            console_msg = f"[{level.value}] {message}"
            if context:
                console_msg += f" | {json.dumps(context)}"

            # Use appropriate log level
            if level == LogLevel.DEBUG:
                self.python_logger.debug(console_msg)
            elif level == LogLevel.INFO:
                self.python_logger.info(console_msg)
            elif level == LogLevel.WARNING:
                self.python_logger.warning(console_msg)
            elif level == LogLevel.ERROR:
                self.python_logger.error(console_msg)
            elif level == LogLevel.CRITICAL:
                self.python_logger.critical(console_msg)

    def debug(self, message: str, **context: Any):
        """Log debug message"""
        self.log(LogLevel.DEBUG, message, **context)

    def info(self, message: str, **context: Any):
        """Log info message"""
        self.log(LogLevel.INFO, message, **context)

    def warning(self, message: str, **context: Any):
        """Log warning message"""
        self.log(LogLevel.WARNING, message, **context)

    def error(self, message: str, **context: Any):
        """Log error message"""
        self.log(LogLevel.ERROR, message, **context)

    def critical(self, message: str, **context: Any):
        """Log critical message"""
        self.log(LogLevel.CRITICAL, message, **context)

    def log_workflow(
        self,
        workflow_domain: str,
        event: str,
        **context: Any
    ):
        """Log workflow event

        Args:
            workflow_domain: Workflow domain (coding, research, etc.)
            event: Event name (started, completed, failed, etc.)
            **context: Additional context
        """
        self.info(
            f"Workflow {event}",
            event_type="workflow",
            workflow_domain=workflow_domain,
            event=event,
            **context
        )

    def log_agent(
        self,
        agent_name: str,
        agent_type: str,
        event: str,
        **context: Any
    ):
        """Log agent event

        Args:
            agent_name: Agent name
            agent_type: Agent type
            event: Event name
            **context: Additional context
        """
        self.info(
            f"Agent {agent_name} {event}",
            event_type="agent",
            agent_name=agent_name,
            agent_type=agent_type,
            event=event,
            **context
        )

    def log_task(
        self,
        task_id: str,
        event: str,
        **context: Any
    ):
        """Log task event

        Args:
            task_id: Task ID
            event: Event name
            **context: Additional context
        """
        self.info(
            f"Task {task_id} {event}",
            event_type="task",
            task_id=task_id,
            event=event,
            **context
        )

    def log_error_with_trace(
        self,
        message: str,
        error: Exception,
        **context: Any
    ):
        """Log error with stack trace

        Args:
            message: Error message
            error: Exception object
            **context: Additional context
        """
        import traceback

        self.error(
            message,
            error_type=type(error).__name__,
            error_message=str(error),
            traceback=traceback.format_exc(),
            **context
        )


# Global logger instance
_global_logger: Optional[StructuredLogger] = None


def get_logger(
    log_file: Optional[str] = None,
    console_output: bool = True
) -> StructuredLogger:
    """Get or create global logger instance

    Args:
        log_file: Path to log file (only used if creating new logger)
        console_output: Console output (only used if creating new logger)

    Returns:
        StructuredLogger instance
    """
    global _global_logger

    if _global_logger is None:
        _global_logger = StructuredLogger(
            log_file=log_file,
            console_output=console_output
        )

    return _global_logger

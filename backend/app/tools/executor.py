"""
Tool Executor - Safe execution engine for tools with timeout and safety checks
"""

import asyncio
from typing import Dict, Optional
import logging

from .base import BaseTool, ToolResult
from .registry import ToolRegistry

logger = logging.getLogger(__name__)


class ToolExecutor:
    """
    Executor for running tools safely with timeouts and resource limits.

    Features:
    - Timeout protection
    - Parameter validation
    - Error handling
    - Execution logging
    """

    def __init__(self, timeout: int = 30, max_memory_mb: int = 512):
        """
        Initialize tool executor.

        Args:
            timeout: Maximum execution time in seconds (default: 30)
            max_memory_mb: Maximum memory limit in MB (default: 512)
        """
        self.timeout = timeout
        self.max_memory_mb = max_memory_mb
        self.registry = ToolRegistry()

    async def execute(
        self,
        tool_name: str,
        params: Dict,
        session_id: str
    ) -> ToolResult:
        """
        Execute a tool with safety checks.

        Args:
            tool_name: Name of the tool to execute
            params: Parameters for the tool
            session_id: Session identifier for logging

        Returns:
            ToolResult: Result of the execution
        """
        logger.info(f"[{session_id}] Executing tool '{tool_name}' with params: {params}")

        # Get tool from registry
        tool = self.registry.get_tool(tool_name)
        if not tool:
            logger.error(f"[{session_id}] Tool '{tool_name}' not found")
            return ToolResult(
                success=False,
                output=None,
                error=f"Tool '{tool_name}' not found"
            )

        # Validate parameters
        try:
            if not tool.validate_params(**params):
                logger.error(f"[{session_id}] Invalid parameters for tool '{tool_name}'")
                return ToolResult(
                    success=False,
                    output=None,
                    error="Invalid parameters"
                )
        except Exception as e:
            logger.error(f"[{session_id}] Parameter validation failed: {str(e)}")
            return ToolResult(
                success=False,
                output=None,
                error=f"Parameter validation error: {str(e)}"
            )

        # Execute with timeout
        try:
            result = await asyncio.wait_for(
                tool._execute_with_timing(**params),
                timeout=self.timeout
            )

            logger.info(
                f"[{session_id}] Tool '{tool_name}' executed successfully "
                f"in {result.execution_time:.2f}s"
            )
            return result

        except asyncio.TimeoutError:
            logger.error(f"[{session_id}] Tool '{tool_name}' timed out after {self.timeout}s")
            return ToolResult(
                success=False,
                output=None,
                error=f"Tool execution exceeded {self.timeout}s timeout"
            )

        except Exception as e:
            logger.error(f"[{session_id}] Tool '{tool_name}' execution failed: {str(e)}")
            return ToolResult(
                success=False,
                output=None,
                error=f"Execution error: {str(e)}"
            )

    async def execute_batch(
        self,
        tool_calls: list[Dict],
        session_id: str
    ) -> list[ToolResult]:
        """
        Execute multiple tools in parallel.

        Args:
            tool_calls: List of {tool_name, params} dictionaries
            session_id: Session identifier

        Returns:
            List of ToolResults in the same order
        """
        tasks = [
            self.execute(call["tool_name"], call["params"], session_id)
            for call in tool_calls
        ]

        results = await asyncio.gather(*tasks, return_exceptions=True)

        # Convert exceptions to ToolResults
        processed_results = []
        for result in results:
            if isinstance(result, Exception):
                processed_results.append(ToolResult(
                    success=False,
                    output=None,
                    error=str(result)
                ))
            else:
                processed_results.append(result)

        return processed_results

    def get_available_tools(self) -> list[str]:
        """
        Get list of available tool names.

        Returns:
            List of tool names
        """
        return [tool.name for tool in self.registry.list_tools()]

    def get_tool_schema(self, tool_name: str) -> Optional[Dict]:
        """
        Get schema for a specific tool.

        Args:
            tool_name: Name of the tool

        Returns:
            Tool schema or None if not found
        """
        tool = self.registry.get_tool(tool_name)
        return tool.get_schema() if tool else None

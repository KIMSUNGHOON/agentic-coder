"""
Base classes and types for the Tool Execution System
"""

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import Any, Dict, Optional
from enum import Enum
import time


class ToolCategory(Enum):
    """Categories of tools available in the system"""
    FILE = "file"
    CODE = "code"
    GIT = "git"
    WEB = "web"
    SEARCH = "search"


@dataclass
class ToolResult:
    """Result from a tool execution"""
    success: bool
    output: Any
    error: Optional[str] = None
    execution_time: float = 0.0
    metadata: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> Dict:
        """Convert to dictionary for JSON serialization"""
        return {
            "success": self.success,
            "output": self.output,
            "error": self.error,
            "execution_time": self.execution_time,
            "metadata": self.metadata
        }


class BaseTool(ABC):
    """
    Base class for all tools in the system.

    All tools must inherit from this class and implement:
    - execute(): Main execution logic
    - validate_params(): Parameter validation
    """

    def __init__(self, name: str, category: ToolCategory):
        self.name = name
        self.category = category
        self.description = ""
        self.parameters = {}

    @abstractmethod
    async def execute(self, **kwargs) -> ToolResult:
        """
        Execute the tool with given parameters.

        Args:
            **kwargs: Tool-specific parameters

        Returns:
            ToolResult: Result of the execution
        """
        pass

    @abstractmethod
    def validate_params(self, **kwargs) -> bool:
        """
        Validate parameters before execution.

        Args:
            **kwargs: Parameters to validate

        Returns:
            bool: True if valid, False otherwise
        """
        pass

    def get_schema(self) -> Dict:
        """
        Return JSON schema for tool parameters.

        Returns:
            Dict: Tool schema including name, category, description, parameters
        """
        return {
            "name": self.name,
            "category": self.category.value,
            "description": self.description,
            "parameters": self.parameters
        }

    async def _execute_with_timing(self, **kwargs) -> ToolResult:
        """
        Internal method to execute with timing.

        Args:
            **kwargs: Parameters for execution

        Returns:
            ToolResult: Result with execution time
        """
        start_time = time.time()
        result = await self.execute(**kwargs)
        result.execution_time = time.time() - start_time
        return result

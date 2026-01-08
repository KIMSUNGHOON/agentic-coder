"""
Tool Registry - Central registry for all available tools
"""

from typing import Dict, List, Optional
import logging

from .base import BaseTool, ToolCategory
from .file_tools import ReadFileTool, WriteFileTool, SearchFilesTool, ListDirectoryTool
from .code_tools import ExecutePythonTool, RunTestsTool, LintCodeTool
from .git_tools import GitStatusTool, GitDiffTool, GitLogTool, GitBranchTool, GitCommitTool
from .web_tools import WebSearchTool
from .search_tools import CodeSearchTool

logger = logging.getLogger(__name__)


class ToolRegistry:
    """
    Singleton registry for all tools in the system.

    Manages tool registration, discovery, and retrieval.
    """

    _instance = None

    def __new__(cls):
        if cls._instance is None:
            cls._instance = super().__new__(cls)
            cls._instance._initialized = False
        return cls._instance

    def __init__(self):
        if self._initialized:
            return

        self._tools: Dict[str, BaseTool] = {}
        self._register_default_tools()
        self._initialized = True

        logger.info(f"Tool Registry initialized with {len(self._tools)} tools")

    def _register_default_tools(self):
        """Register all default tools"""
        default_tools = [
            # File tools
            ReadFileTool(),
            WriteFileTool(),
            SearchFilesTool(),
            ListDirectoryTool(),

            # Code tools
            ExecutePythonTool(),
            RunTestsTool(),
            LintCodeTool(),

            # Git tools
            GitStatusTool(),
            GitDiffTool(),
            GitLogTool(),
            GitBranchTool(),
            GitCommitTool(),  # Phase 1: NEW

            # Web tools (Phase 1: NEW)
            WebSearchTool(),

            # Search tools (Phase 1: NEW)
            CodeSearchTool(),
        ]

        for tool in default_tools:
            self.register(tool)

    def register(self, tool: BaseTool):
        """
        Register a new tool.

        Args:
            tool: Tool instance to register
        """
        if tool.name in self._tools:
            logger.warning(f"Tool '{tool.name}' already registered, overwriting")

        self._tools[tool.name] = tool
        logger.debug(f"Registered tool: {tool.name} ({tool.category.value})")

    def unregister(self, tool_name: str) -> bool:
        """
        Unregister a tool.

        Args:
            tool_name: Name of the tool to unregister

        Returns:
            True if unregistered, False if not found
        """
        if tool_name in self._tools:
            del self._tools[tool_name]
            logger.debug(f"Unregistered tool: {tool_name}")
            return True
        return False

    def get_tool(self, name: str) -> Optional[BaseTool]:
        """
        Get a tool by name.

        Args:
            name: Tool name

        Returns:
            Tool instance or None if not found
        """
        return self._tools.get(name)

    def list_tools(self, category: Optional[ToolCategory] = None) -> List[BaseTool]:
        """
        List all tools, optionally filtered by category.

        Args:
            category: Optional category filter

        Returns:
            List of tools
        """
        if category:
            return [t for t in self._tools.values() if t.category == category]
        return list(self._tools.values())

    def get_tool_names(self, category: Optional[ToolCategory] = None) -> List[str]:
        """
        Get list of tool names.

        Args:
            category: Optional category filter

        Returns:
            List of tool names
        """
        tools = self.list_tools(category)
        return [t.name for t in tools]

    def get_schemas(self, category: Optional[ToolCategory] = None) -> List[Dict]:
        """
        Get schemas for all tools.

        Args:
            category: Optional category filter

        Returns:
            List of tool schemas
        """
        tools = self.list_tools(category)
        return [tool.get_schema() for tool in tools]

    def get_categories(self) -> List[str]:
        """
        Get list of all tool categories.

        Returns:
            List of category names
        """
        categories = set(tool.category.value for tool in self._tools.values())
        return sorted(list(categories))

    def get_statistics(self) -> Dict:
        """
        Get registry statistics.

        Returns:
            Dictionary with statistics
        """
        stats = {
            "total_tools": len(self._tools),
            "by_category": {}
        }

        for category in ToolCategory:
            count = len([t for t in self._tools.values() if t.category == category])
            if count > 0:
                stats["by_category"][category.value] = count

        return stats


# Global registry instance
_global_registry = None


def get_registry() -> ToolRegistry:
    """
    Get the global tool registry instance.

    Returns:
        Global ToolRegistry instance
    """
    global _global_registry
    if _global_registry is None:
        _global_registry = ToolRegistry()
    return _global_registry

"""
Tool Registry - Central registry for all available tools

Phase 2: Network Mode Support
- Online/Offline mode filtering
- Tool availability based on network requirements
"""

from typing import Dict, List, Optional
import logging
import os

from .base import BaseTool, ToolCategory, NetworkType
from .file_tools import ReadFileTool, WriteFileTool, SearchFilesTool, ListDirectoryTool
from .code_tools import ExecutePythonTool, RunTestsTool, LintCodeTool
from .git_tools import GitStatusTool, GitDiffTool, GitLogTool, GitBranchTool, GitCommitTool
from .web_tools import WebSearchTool, HttpRequestTool, DownloadFileTool
from .search_tools import CodeSearchTool

logger = logging.getLogger(__name__)


class ToolRegistry:
    """
    Singleton registry for all tools in the system.

    Manages tool registration, discovery, and retrieval.

    Phase 2: Network Mode Support
    - Supports online/offline mode based on NETWORK_MODE environment variable
    - Filters tools based on network requirements in offline mode
    - EXTERNAL_API tools blocked in offline mode
    - EXTERNAL_DOWNLOAD tools allowed in offline mode (wget/curl)
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
        self._network_mode = self._get_network_mode()
        self._register_default_tools()
        self._initialized = True

        logger.info(f"Tool Registry initialized: mode={self._network_mode}, tools={len(self._tools)}")

        # Log disabled tools in offline mode
        if self._network_mode == "offline":
            disabled = [t.name for t in self._tools.values()
                       if not t.is_available_in_mode(self._network_mode)]
            if disabled:
                logger.warning(f"Offline mode: {len(disabled)} tools disabled: {disabled}")

    def _get_network_mode(self) -> str:
        """
        Get network mode from environment.

        Returns:
            'online' or 'offline'
        """
        mode = os.getenv("NETWORK_MODE", "online").lower()

        if mode not in ["online", "offline"]:
            logger.warning(f"Invalid NETWORK_MODE '{mode}', defaulting to 'online'")
            mode = "online"

        return mode

    def get_network_mode(self) -> str:
        """
        Get current network mode.

        Returns:
            Current network mode ('online' or 'offline')
        """
        return self._network_mode

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

            # Web tools (Phase 2: NEW - Network Types)
            HttpRequestTool(),    # EXTERNAL_API - blocked in offline mode
            DownloadFileTool(),   # EXTERNAL_DOWNLOAD - allowed in offline mode

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

    def get_tool(self, name: str, check_availability: bool = True) -> Optional[BaseTool]:
        """
        Get a tool by name, checking network availability.

        Args:
            name: Tool name
            check_availability: If True, check if tool is available in current network mode

        Returns:
            Tool instance or None if not found or unavailable
        """
        tool = self._tools.get(name)

        if tool and check_availability:
            if not tool.is_available_in_mode(self._network_mode):
                logger.warning(
                    f"Tool '{name}' requested but unavailable in {self._network_mode} mode. "
                    f"{tool.get_unavailable_message()}"
                )
                return None

        return tool

    def list_tools(
        self,
        category: Optional[ToolCategory] = None,
        include_unavailable: bool = False
    ) -> List[BaseTool]:
        """
        List all tools, filtered by network mode and optionally by category.

        Args:
            category: Optional category filter
            include_unavailable: If True, include tools unavailable in current mode

        Returns:
            List of tools available in current network mode
        """
        tools = list(self._tools.values())

        # Filter by category
        if category:
            tools = [t for t in tools if t.category == category]

        # Filter by network mode (unless include_unavailable is True)
        if not include_unavailable:
            tools = [t for t in tools if t.is_available_in_mode(self._network_mode)]

        return tools

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
        Get registry statistics including network mode info.

        Returns:
            Dictionary with statistics
        """
        stats = {
            "total_tools": len(self._tools),
            "network_mode": self._network_mode,
            "available_tools": 0,
            "disabled_tools": 0,
            "by_category": {},
            "by_network_type": {
                NetworkType.LOCAL.value: 0,
                NetworkType.INTERNAL.value: 0,
                NetworkType.EXTERNAL_API.value: 0,
                NetworkType.EXTERNAL_DOWNLOAD.value: 0
            }
        }

        for tool in self._tools.values():
            # Category stats
            cat = tool.category.value
            if cat not in stats["by_category"]:
                stats["by_category"][cat] = 0
            stats["by_category"][cat] += 1

            # Network type stats
            stats["by_network_type"][tool.network_type.value] += 1

            # Availability stats
            if tool.is_available_in_mode(self._network_mode):
                stats["available_tools"] += 1
            else:
                stats["disabled_tools"] += 1

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

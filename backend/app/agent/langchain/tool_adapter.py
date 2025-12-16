"""LangChain Tool Adapter - Bridge between native tools and LangChain."""
import logging
from typing import Dict, List, Any, Optional, Type
from langchain_core.tools import BaseTool as LangChainBaseTool, ToolException
from langchain_core.callbacks import CallbackManagerForToolRun
from pydantic import BaseModel, Field
import asyncio

from app.tools.registry import ToolRegistry, get_registry
from app.tools.base import BaseTool as NativeTool, ToolResult

logger = logging.getLogger(__name__)


class LangChainToolAdapter(LangChainBaseTool):
    """Adapter that wraps native tools for use with LangChain agents."""

    native_tool: NativeTool = Field(exclude=True)
    session_id: str = "default"

    class Config:
        arbitrary_types_allowed = True

    def __init__(self, native_tool: NativeTool, session_id: str = "default"):
        """Initialize adapter with a native tool.

        Args:
            native_tool: Native tool instance to wrap
            session_id: Session identifier for logging
        """
        super().__init__(
            name=native_tool.name,
            description=native_tool.description or f"Execute {native_tool.name} tool",
            native_tool=native_tool,
            session_id=session_id
        )

    def _run(
        self,
        tool_input: str = "",
        run_manager: Optional[CallbackManagerForToolRun] = None,
        **kwargs
    ) -> str:
        """Synchronous execution (runs async in sync context)."""
        try:
            loop = asyncio.get_event_loop()
            if loop.is_running():
                import concurrent.futures
                with concurrent.futures.ThreadPoolExecutor() as executor:
                    future = executor.submit(
                        asyncio.run,
                        self._arun(tool_input, **kwargs)
                    )
                    return future.result()
            else:
                return loop.run_until_complete(self._arun(tool_input, **kwargs))
        except Exception as e:
            logger.error(f"Error in tool {self.name}: {e}")
            raise ToolException(str(e))

    async def _arun(
        self,
        tool_input: str = "",
        run_manager: Optional[CallbackManagerForToolRun] = None,
        **kwargs
    ) -> str:
        """Asynchronous execution."""
        try:
            # Parse tool_input if it's a string (JSON)
            params = kwargs
            if tool_input:
                import json
                try:
                    parsed = json.loads(tool_input)
                    if isinstance(parsed, dict):
                        params.update(parsed)
                except json.JSONDecodeError:
                    # If not JSON, treat as primary parameter
                    schema = self.native_tool.get_schema()
                    if schema.get("parameters"):
                        # Find required parameter
                        for param_name, param_info in schema["parameters"].items():
                            if param_info.get("required", False):
                                params[param_name] = tool_input
                                break

            logger.info(f"[{self.session_id}] Executing tool '{self.name}' with params: {params}")

            # Execute native tool
            result: ToolResult = await self.native_tool._execute_with_timing(**params)

            if result.success:
                # Format output as string for LangChain
                output = result.output
                if isinstance(output, (dict, list)):
                    import json
                    return json.dumps(output, indent=2, ensure_ascii=False)
                return str(output)
            else:
                raise ToolException(result.error or "Tool execution failed")

        except ToolException:
            raise
        except Exception as e:
            logger.error(f"Error executing tool {self.name}: {e}")
            raise ToolException(str(e))


class LangChainToolRegistry:
    """Registry that provides LangChain-compatible tools."""

    def __init__(self, session_id: str = "default"):
        """Initialize registry with session ID.

        Args:
            session_id: Session identifier for tool execution
        """
        self.native_registry = get_registry()
        self.session_id = session_id
        self._adapted_tools: Dict[str, LangChainToolAdapter] = {}

    def get_tool(self, name: str) -> Optional[LangChainToolAdapter]:
        """Get a LangChain-adapted tool by name.

        Args:
            name: Tool name

        Returns:
            LangChain tool adapter or None
        """
        if name not in self._adapted_tools:
            native_tool = self.native_registry.get_tool(name)
            if native_tool:
                self._adapted_tools[name] = LangChainToolAdapter(
                    native_tool=native_tool,
                    session_id=self.session_id
                )
        return self._adapted_tools.get(name)

    def get_tools(self, names: Optional[List[str]] = None) -> List[LangChainToolAdapter]:
        """Get multiple LangChain-adapted tools.

        Args:
            names: List of tool names. If None, returns all tools.

        Returns:
            List of LangChain tool adapters
        """
        if names is None:
            names = self.native_registry.get_tool_names()

        tools = []
        for name in names:
            tool = self.get_tool(name)
            if tool:
                tools.append(tool)
        return tools

    def get_all_tools(self) -> List[LangChainToolAdapter]:
        """Get all available tools as LangChain tools.

        Returns:
            List of all LangChain tool adapters
        """
        return self.get_tools()

    def get_tools_by_category(self, category: str) -> List[LangChainToolAdapter]:
        """Get tools filtered by category.

        Args:
            category: Tool category (file, code, git, web, search)

        Returns:
            List of tools in the category
        """
        from app.tools.base import ToolCategory
        try:
            cat = ToolCategory(category)
            native_tools = self.native_registry.list_tools(cat)
            names = [t.name for t in native_tools]
            return self.get_tools(names)
        except ValueError:
            logger.warning(f"Unknown category: {category}")
            return []


def get_langchain_tools(
    session_id: str = "default",
    tool_names: Optional[List[str]] = None
) -> List[LangChainToolAdapter]:
    """Convenience function to get LangChain tools.

    Args:
        session_id: Session identifier
        tool_names: Optional list of specific tools to get

    Returns:
        List of LangChain tool adapters
    """
    registry = LangChainToolRegistry(session_id)
    return registry.get_tools(tool_names)

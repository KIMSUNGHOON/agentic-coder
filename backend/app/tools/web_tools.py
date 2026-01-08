"""
Web Tools - Internet search and web operations
"""

import logging
import os
from typing import Optional, List, Dict, Any

from .base import BaseTool, ToolCategory, ToolResult

logger = logging.getLogger(__name__)


class WebSearchTool(BaseTool):
    """Search the web using Tavily API"""

    def __init__(self, api_key: Optional[str] = None):
        """Initialize web search tool

        Args:
            api_key: Tavily API key. If not provided, reads from TAVILY_API_KEY env var
        """
        super().__init__("web_search", ToolCategory.WEB)
        self.description = "Search the web for information using Tavily search API"
        self.parameters = {
            "query": {
                "type": "string",
                "description": "Search query",
                "required": True
            },
            "max_results": {
                "type": "integer",
                "description": "Maximum number of results to return",
                "default": 5,
                "required": False
            },
            "search_depth": {
                "type": "string",
                "description": "Search depth: 'basic' or 'advanced'",
                "default": "basic",
                "required": False
            }
        }

        # Get API key from parameter or environment
        self.api_key = api_key or os.getenv("TAVILY_API_KEY")

        # Lazy import Tavily client
        self._client = None

    def _get_client(self):
        """Lazy initialization of Tavily client"""
        if self._client is None:
            if not self.api_key:
                raise ValueError(
                    "Tavily API key not found. Set TAVILY_API_KEY environment variable "
                    "or pass api_key parameter. Get your key at https://tavily.com"
                )

            try:
                from tavily import TavilyClient
                self._client = TavilyClient(api_key=self.api_key)
                logger.info("✅ Tavily client initialized")
            except ImportError:
                raise ImportError(
                    "tavily-python package not installed. "
                    "Install with: pip install tavily-python"
                )
        return self._client

    def validate_params(self, **kwargs) -> bool:
        """Validate search parameters"""
        if "query" not in kwargs or not kwargs["query"]:
            logger.error("Query parameter is required")
            return False

        if "max_results" in kwargs:
            max_results = kwargs["max_results"]
            if not isinstance(max_results, int) or max_results < 1 or max_results > 20:
                logger.error("max_results must be an integer between 1 and 20")
                return False

        if "search_depth" in kwargs:
            depth = kwargs["search_depth"]
            if depth not in ["basic", "advanced"]:
                logger.error("search_depth must be 'basic' or 'advanced'")
                return False

        return True

    async def execute(
        self,
        query: str,
        max_results: int = 5,
        search_depth: str = "basic",
        **kwargs
    ) -> ToolResult:
        """Execute web search

        Args:
            query: Search query string
            max_results: Maximum number of results (1-20)
            search_depth: Search depth 'basic' or 'advanced'

        Returns:
            ToolResult with search results
        """
        try:
            logger.info(f"🔍 Searching web for: '{query}' (max_results={max_results})")

            # Get Tavily client
            client = self._get_client()

            # Perform search (Tavily is synchronous, run in executor)
            import asyncio
            loop = asyncio.get_event_loop()

            search_results = await loop.run_in_executor(
                None,
                lambda: client.search(
                    query=query,
                    max_results=max_results,
                    search_depth=search_depth
                )
            )

            # Extract relevant information
            results = []
            for item in search_results.get("results", []):
                results.append({
                    "title": item.get("title", ""),
                    "url": item.get("url", ""),
                    "content": item.get("content", ""),
                    "score": item.get("score", 0.0)
                })

            # Format output message
            result_count = len(results)
            message = f"Found {result_count} web search results for '{query}'"

            logger.info(f"✅ Web search completed: {result_count} results")

            return ToolResult(
                success=True,
                output={
                    "query": query,
                    "result_count": result_count,
                    "results": results,
                    "search_depth": search_depth
                },
                message=message,
                metadata={
                    "tool": self.name,
                    "max_results": max_results,
                    "search_depth": search_depth
                }
            )

        except ValueError as e:
            # API key or configuration error
            error_msg = f"Configuration error: {str(e)}"
            logger.error(f"❌ {error_msg}")
            return ToolResult(
                success=False,
                output=None,
                error=error_msg
            )

        except ImportError as e:
            # Tavily package not installed
            error_msg = f"Import error: {str(e)}"
            logger.error(f"❌ {error_msg}")
            return ToolResult(
                success=False,
                output=None,
                error=error_msg
            )

        except Exception as e:
            # API error or network error
            error_msg = f"Web search failed: {str(e)}"
            logger.error(f"❌ {error_msg}", exc_info=True)
            return ToolResult(
                success=False,
                output=None,
                error=error_msg
            )

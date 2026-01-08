"""
Search Tools - Semantic search and code discovery
"""

import logging
import os
from pathlib import Path
from typing import Optional, List, Dict, Any

from .base import BaseTool, ToolCategory, ToolResult, NetworkType

logger = logging.getLogger(__name__)


class CodeSearchTool(BaseTool):
    """Semantic search across codebase using ChromaDB and RAG"""

    def __init__(self, chroma_path: Optional[str] = None):
        """Initialize code search tool

        Args:
            chroma_path: Path to ChromaDB storage. Defaults to ./chroma_db
        """
        super().__init__("code_search", ToolCategory.SEARCH)

        # Phase 2: Network requirement - LOCAL (uses local ChromaDB)
        # No network access needed - operates on local vector database
        self.requires_network = False
        self.network_type = NetworkType.LOCAL

        self.description = "Semantic search across codebase using RAG (ChromaDB vector database) - works offline"
        self.parameters = {
            "query": {
                "type": "string",
                "description": "Natural language search query (e.g., 'authentication logic', 'file upload handler')",
                "required": True
            },
            "n_results": {
                "type": "integer",
                "description": "Number of code snippets to return",
                "default": 5,
                "required": False
            },
            "repo_filter": {
                "type": "string",
                "description": "Optional repository name filter",
                "required": False
            },
            "file_type_filter": {
                "type": "string",
                "description": "Optional file type filter (e.g., 'python', 'javascript')",
                "required": False
            }
        }

        # ChromaDB configuration
        self.chroma_path = chroma_path or os.getenv("CHROMA_DB_PATH", "./chroma_db")

        # Lazy initialization
        self._client = None
        self._embedder = None

    def _get_embedder(self):
        """Lazy initialization of ChromaDB client and embedder"""
        if self._embedder is None:
            try:
                import chromadb
                from app.utils.repository_embedder import RepositoryEmbedder

                # Initialize ChromaDB client
                self._client = chromadb.PersistentClient(path=self.chroma_path)
                logger.info(f"📚 ChromaDB client initialized at: {self.chroma_path}")

                # Initialize embedder
                self._embedder = RepositoryEmbedder(
                    chroma_client=self._client,
                    collection_name="code_repositories"
                )
                self._embedder.initialize_collection()

                logger.info("✅ Code search embedder initialized")

            except ImportError as e:
                raise ImportError(
                    f"Required packages not installed: {str(e)}. "
                    "Install with: pip install chromadb"
                )
            except Exception as e:
                raise RuntimeError(f"Failed to initialize ChromaDB: {str(e)}")

        return self._embedder

    def validate_params(self, **kwargs) -> bool:
        """Validate search parameters"""
        if "query" not in kwargs or not kwargs["query"]:
            logger.error("Query parameter is required")
            return False

        if "n_results" in kwargs:
            n_results = kwargs["n_results"]
            if not isinstance(n_results, int) or n_results < 1 or n_results > 50:
                logger.error("n_results must be an integer between 1 and 50")
                return False

        return True

    async def execute(
        self,
        query: str,
        n_results: int = 5,
        repo_filter: Optional[str] = None,
        file_type_filter: Optional[str] = None,
        **kwargs
    ) -> ToolResult:
        """Execute semantic code search

        Args:
            query: Natural language search query
            n_results: Number of results to return (1-50)
            repo_filter: Optional repository name filter
            file_type_filter: Optional file type filter

        Returns:
            ToolResult with search results
        """
        try:
            logger.info(f"🔍 Searching code for: '{query}' (n_results={n_results})")

            # Get embedder
            embedder = self._get_embedder()

            # Perform search (synchronous, run in executor)
            import asyncio
            loop = asyncio.get_event_loop()

            search_results = await loop.run_in_executor(
                None,
                lambda: embedder.search(
                    query=query,
                    n_results=n_results,
                    repo_filter=repo_filter,
                    file_type_filter=file_type_filter
                )
            )

            # Format results
            results = []
            for item in search_results:
                results.append({
                    "file_path": item.get("file_path", ""),
                    "file_type": item.get("file_type", ""),
                    "chunk_index": item.get("chunk_index", 0),
                    "content": item.get("content", ""),
                    "score": item.get("score", 0.0),
                    "repo": item.get("repo", "")
                })

            result_count = len(results)
            message = f"Found {result_count} relevant code snippets for '{query}'"

            # Log summary
            if result_count > 0:
                logger.info(f"✅ Code search completed: {result_count} results")
                logger.debug(f"   Top result: {results[0]['file_path']} (score: {results[0]['score']:.3f})")
            else:
                logger.warning(f"⚠️  No code snippets found for query: '{query}'")

            return ToolResult(
                success=True,
                output={
                    "query": query,
                    "result_count": result_count,
                    "results": results,
                    "message": message
                },
                metadata={
                    "tool": self.name,
                    "n_results": n_results,
                    "repo_filter": repo_filter,
                    "file_type_filter": file_type_filter,
                    "chroma_path": self.chroma_path
                }
            )

        except ImportError as e:
            error_msg = f"Import error: {str(e)}"
            logger.error(f"❌ {error_msg}")
            return ToolResult(
                success=False,
                output=None,
                error=error_msg
            )

        except RuntimeError as e:
            error_msg = f"ChromaDB initialization failed: {str(e)}"
            logger.error(f"❌ {error_msg}")
            return ToolResult(
                success=False,
                output=None,
                error=error_msg
            )

        except Exception as e:
            error_msg = f"Code search failed: {str(e)}"
            logger.error(f"❌ {error_msg}", exc_info=True)
            return ToolResult(
                success=False,
                output=None,
                error=error_msg
            )


class DocumentSearchTool(BaseTool):
    """Search documentation and markdown files (future extension)"""

    def __init__(self):
        super().__init__("doc_search", ToolCategory.SEARCH)

        # Phase 2: Network requirement - LOCAL (future: local file search)
        self.requires_network = False
        self.network_type = NetworkType.LOCAL

        self.description = "Search documentation and markdown files - works offline"
        self.parameters = {
            "query": {
                "type": "string",
                "description": "Documentation search query",
                "required": True
            }
        }

    def validate_params(self, **kwargs) -> bool:
        """Validate parameters"""
        return "query" in kwargs and bool(kwargs["query"])

    async def execute(self, query: str, **kwargs) -> ToolResult:
        """Execute documentation search (placeholder for future implementation)"""
        return ToolResult(
            success=False,
            output=None,
            error="DocumentSearchTool not yet implemented. Use CodeSearchTool with file_type_filter='markdown'"
        )

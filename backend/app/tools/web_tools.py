"""
Web Tools - Internet search and web operations

Phase 2 Tools:
- WebSearchTool: Search the web using Tavily API (EXTERNAL_API)
- HttpRequestTool: Make HTTP requests to REST APIs (EXTERNAL_API)
- DownloadFileTool: Download files from URLs (EXTERNAL_DOWNLOAD)
"""

import logging
import os
import asyncio
import subprocess
import pathlib
from typing import Optional, List, Dict, Any

from .base import BaseTool, ToolCategory, ToolResult, NetworkType

logger = logging.getLogger(__name__)


class WebSearchTool(BaseTool):
    """Search the web using Tavily API"""

    def __init__(self, api_key: Optional[str] = None):
        """Initialize web search tool

        Args:
            api_key: Tavily API key. If not provided, reads from TAVILY_API_KEY env var
        """
        super().__init__("web_search", ToolCategory.WEB)

        # Phase 2: Network requirement - requires external API access
        # Tavily API is an interactive external API that may send query data
        self.requires_network = True
        self.network_type = NetworkType.EXTERNAL_API

        self.description = "Search the web for information using Tavily search API (requires online mode)"
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


class HttpRequestTool(BaseTool):
    """
    Make HTTP requests to REST APIs.

    Phase 2: EXTERNAL_API - blocked in offline mode
    This tool sends data to external APIs and may leak local information.
    """

    def __init__(self):
        super().__init__("http_request", ToolCategory.WEB)

        # Phase 2: Network requirement - EXTERNAL_API (blocked in offline mode)
        self.requires_network = True
        self.network_type = NetworkType.EXTERNAL_API

        self.description = "Make HTTP requests to REST APIs (requires online mode)"
        self.parameters = {
            "url": {
                "type": "string",
                "description": "URL to send the request to",
                "required": True
            },
            "method": {
                "type": "string",
                "description": "HTTP method: GET, POST, PUT, DELETE, PATCH",
                "default": "GET",
                "required": False
            },
            "headers": {
                "type": "object",
                "description": "HTTP headers as key-value pairs",
                "default": {},
                "required": False
            },
            "body": {
                "type": "string",
                "description": "Request body (for POST, PUT, PATCH)",
                "default": None,
                "required": False
            },
            "timeout": {
                "type": "integer",
                "description": "Request timeout in seconds",
                "default": 30,
                "required": False
            }
        }

        self._session = None

    def validate_params(self, **kwargs) -> bool:
        """Validate HTTP request parameters"""
        if "url" not in kwargs or not kwargs["url"]:
            logger.error("URL parameter is required")
            return False

        url = kwargs["url"]
        if not url.startswith(("http://", "https://")):
            logger.error("URL must start with http:// or https://")
            return False

        if "method" in kwargs:
            method = kwargs["method"].upper()
            if method not in ["GET", "POST", "PUT", "DELETE", "PATCH", "HEAD", "OPTIONS"]:
                logger.error(f"Invalid HTTP method: {method}")
                return False

        if "timeout" in kwargs:
            timeout = kwargs["timeout"]
            if not isinstance(timeout, (int, float)) or timeout <= 0 or timeout > 300:
                logger.error("Timeout must be a positive number up to 300 seconds")
                return False

        return True

    async def execute(
        self,
        url: str,
        method: str = "GET",
        headers: Optional[Dict[str, str]] = None,
        body: Optional[str] = None,
        timeout: int = 30,
        **kwargs
    ) -> ToolResult:
        """Execute HTTP request

        Args:
            url: Target URL
            method: HTTP method
            headers: Request headers
            body: Request body
            timeout: Request timeout

        Returns:
            ToolResult with response data
        """
        try:
            import aiohttp
        except ImportError:
            return ToolResult(
                success=False,
                output=None,
                error="aiohttp package not installed. Install with: pip install aiohttp"
            )

        method = method.upper()
        headers = headers or {}

        logger.info(f"🌐 HTTP {method} request to: {url}")

        try:
            timeout_obj = aiohttp.ClientTimeout(total=timeout)

            async with aiohttp.ClientSession(timeout=timeout_obj) as session:
                # Prepare request kwargs
                request_kwargs = {
                    "headers": headers
                }

                # Add body for methods that support it
                if body and method in ["POST", "PUT", "PATCH"]:
                    # Try to detect content type
                    if "Content-Type" not in headers:
                        if body.strip().startswith(("{", "[")):
                            headers["Content-Type"] = "application/json"
                    request_kwargs["data"] = body

                # Make request
                async with session.request(method, url, **request_kwargs) as response:
                    # Read response
                    try:
                        response_text = await response.text()
                    except Exception:
                        response_text = "(binary content)"

                    # Try to parse as JSON
                    response_json = None
                    try:
                        import json
                        response_json = json.loads(response_text)
                    except (json.JSONDecodeError, ValueError):
                        pass

                    result_output = {
                        "status_code": response.status,
                        "status_text": response.reason,
                        "headers": dict(response.headers),
                        "body": response_json if response_json else response_text,
                        "is_json": response_json is not None
                    }

                    success = 200 <= response.status < 400
                    message = f"HTTP {method} {url} -> {response.status} {response.reason}"

                    logger.info(f"{'✅' if success else '⚠️'} {message}")

                    return ToolResult(
                        success=success,
                        output=result_output,
                        message=message,
                        metadata={
                            "tool": self.name,
                            "method": method,
                            "url": url,
                            "status_code": response.status
                        }
                    )

        except asyncio.TimeoutError:
            error_msg = f"Request timeout after {timeout} seconds"
            logger.error(f"❌ {error_msg}")
            return ToolResult(
                success=False,
                output=None,
                error=error_msg
            )

        except aiohttp.ClientError as e:
            error_msg = f"HTTP request failed: {str(e)}"
            logger.error(f"❌ {error_msg}")
            return ToolResult(
                success=False,
                output=None,
                error=error_msg
            )

        except Exception as e:
            error_msg = f"HTTP request error: {str(e)}"
            logger.error(f"❌ {error_msg}", exc_info=True)
            return ToolResult(
                success=False,
                output=None,
                error=error_msg
            )


class DownloadFileTool(BaseTool):
    """
    Download files from URLs using wget or curl.

    Phase 2: EXTERNAL_DOWNLOAD - allowed in offline mode
    This tool only downloads data (data IN), it does not send local data externally.
    Safe for use in secure/air-gapped networks.
    """

    def __init__(self):
        super().__init__("download_file", ToolCategory.WEB)

        # Phase 2: Network requirement - EXTERNAL_DOWNLOAD (allowed in offline mode)
        # Downloads are one-way: data comes IN, local data doesn't go OUT
        self.requires_network = True
        self.network_type = NetworkType.EXTERNAL_DOWNLOAD

        self.description = "Download files from URLs using wget/curl (allowed in offline mode - one-way download)"
        self.parameters = {
            "url": {
                "type": "string",
                "description": "URL of the file to download",
                "required": True
            },
            "output_path": {
                "type": "string",
                "description": "Local path to save the downloaded file",
                "required": True
            },
            "timeout": {
                "type": "integer",
                "description": "Download timeout in seconds",
                "default": 60,
                "required": False
            },
            "overwrite": {
                "type": "boolean",
                "description": "Overwrite existing file if it exists",
                "default": False,
                "required": False
            }
        }

    def validate_params(self, **kwargs) -> bool:
        """Validate download parameters"""
        if "url" not in kwargs or not kwargs["url"]:
            logger.error("URL parameter is required")
            return False

        url = kwargs["url"]
        if not url.startswith(("http://", "https://", "ftp://")):
            logger.error("URL must start with http://, https://, or ftp://")
            return False

        if "output_path" not in kwargs or not kwargs["output_path"]:
            logger.error("output_path parameter is required")
            return False

        if "timeout" in kwargs:
            timeout = kwargs["timeout"]
            if not isinstance(timeout, (int, float)) or timeout <= 0 or timeout > 3600:
                logger.error("Timeout must be a positive number up to 3600 seconds")
                return False

        return True

    def _find_downloader(self) -> Optional[str]:
        """Find available download tool (wget or curl)"""
        for cmd in ["wget", "curl"]:
            try:
                result = subprocess.run(
                    [cmd, "--version"],
                    capture_output=True,
                    timeout=5
                )
                if result.returncode == 0:
                    return cmd
            except (subprocess.SubprocessError, FileNotFoundError):
                continue
        return None

    async def execute(
        self,
        url: str,
        output_path: str,
        timeout: int = 60,
        overwrite: bool = False,
        **kwargs
    ) -> ToolResult:
        """Execute file download

        Args:
            url: URL to download from
            output_path: Local path to save file
            timeout: Download timeout
            overwrite: Whether to overwrite existing file

        Returns:
            ToolResult with download status
        """
        try:
            output_file = pathlib.Path(output_path).resolve()

            # Check if file exists
            if output_file.exists() and not overwrite:
                return ToolResult(
                    success=False,
                    output=None,
                    error=f"File already exists: {output_path}. Set overwrite=True to replace."
                )

            # Create parent directory if needed
            output_file.parent.mkdir(parents=True, exist_ok=True)

            # Find available downloader
            downloader = self._find_downloader()
            if not downloader:
                return ToolResult(
                    success=False,
                    output=None,
                    error="Neither wget nor curl found. Please install one of them."
                )

            logger.info(f"📥 Downloading: {url} -> {output_path} (using {downloader})")

            # Build command
            if downloader == "wget":
                cmd = [
                    "wget",
                    "--quiet",
                    "--timeout", str(timeout),
                    "--tries", "3",
                    "-O", str(output_file),
                    url
                ]
            else:  # curl
                cmd = [
                    "curl",
                    "--silent",
                    "--show-error",
                    "--location",  # Follow redirects
                    "--max-time", str(timeout),
                    "--retry", "3",
                    "-o", str(output_file),
                    url
                ]

            # Execute download
            process = await asyncio.create_subprocess_exec(
                *cmd,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE
            )

            try:
                stdout, stderr = await asyncio.wait_for(
                    process.communicate(),
                    timeout=timeout + 10  # Extra buffer for process
                )
            except asyncio.TimeoutError:
                process.kill()
                await process.wait()
                return ToolResult(
                    success=False,
                    output=None,
                    error=f"Download timeout after {timeout} seconds"
                )

            if process.returncode != 0:
                error_text = stderr.decode("utf-8", errors="replace").strip()
                # Clean up partial download
                if output_file.exists():
                    output_file.unlink()
                return ToolResult(
                    success=False,
                    output=None,
                    error=f"Download failed: {error_text or 'Unknown error'}"
                )

            # Verify file was created
            if not output_file.exists():
                return ToolResult(
                    success=False,
                    output=None,
                    error="Download completed but file was not created"
                )

            # Get file info
            file_size = output_file.stat().st_size
            file_size_mb = file_size / (1024 * 1024)

            message = f"Downloaded {file_size_mb:.2f} MB to {output_path}"
            logger.info(f"✅ {message}")

            return ToolResult(
                success=True,
                output={
                    "url": url,
                    "output_path": str(output_file),
                    "file_size_bytes": file_size,
                    "file_size_mb": round(file_size_mb, 2),
                    "downloader": downloader
                },
                message=message,
                metadata={
                    "tool": self.name,
                    "url": url,
                    "output_path": str(output_file)
                }
            )

        except Exception as e:
            error_msg = f"Download error: {str(e)}"
            logger.error(f"❌ {error_msg}", exc_info=True)
            return ToolResult(
                success=False,
                output=None,
                error=error_msg
            )

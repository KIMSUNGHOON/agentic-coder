"""
File Operation Tools - Safe file system interactions
"""

import os
import pathlib
from typing import List
import aiofiles
import logging

from .base import BaseTool, ToolCategory, ToolResult

logger = logging.getLogger(__name__)


class ReadFileTool(BaseTool):
    """Read contents of a file"""

    def __init__(self):
        super().__init__("read_file", ToolCategory.FILE)
        self.description = "Read contents of a file with size limits"
        self.parameters = {
            "path": {
                "type": "string",
                "required": True,
                "description": "Path to the file to read"
            },
            "max_size_mb": {
                "type": "number",
                "default": 10,
                "description": "Maximum file size in MB"
            }
        }

    def validate_params(self, path: str, **kwargs) -> bool:
        return isinstance(path, str) and len(path) > 0

    async def execute(self, path: str, max_size_mb: int = 10) -> ToolResult:
        try:
            file_path = pathlib.Path(path).resolve()

            # Security checks
            if not file_path.exists():
                return ToolResult(False, None, f"File not found: {path}")

            if not file_path.is_file():
                return ToolResult(False, None, f"Not a file: {path}")

            # Size check
            size_bytes = file_path.stat().st_size
            size_mb = size_bytes / (1024 * 1024)
            if size_mb > max_size_mb:
                return ToolResult(
                    False,
                    None,
                    f"File too large: {size_mb:.2f}MB (limit: {max_size_mb}MB)"
                )

            # Read file asynchronously
            async with aiofiles.open(file_path, 'r', encoding='utf-8') as f:
                content = await f.read()

            lines = content.splitlines()

            return ToolResult(
                success=True,
                output=content,
                metadata={
                    "size_mb": round(size_mb, 2),
                    "lines": len(lines),
                    "path": str(file_path)
                }
            )

        except UnicodeDecodeError:
            return ToolResult(False, None, "File is not a valid text file (binary?)")
        except PermissionError:
            return ToolResult(False, None, f"Permission denied: {path}")
        except Exception as e:
            logger.error(f"Error reading file {path}: {str(e)}")
            return ToolResult(False, None, str(e))


class WriteFileTool(BaseTool):
    """Write content to a file"""

    def __init__(self):
        super().__init__("write_file", ToolCategory.FILE)
        self.description = "Write content to a file with safety checks"
        self.parameters = {
            "path": {
                "type": "string",
                "required": True,
                "description": "Path to the file to write"
            },
            "content": {
                "type": "string",
                "required": True,
                "description": "Content to write"
            },
            "create_dirs": {
                "type": "boolean",
                "default": True,
                "description": "Create parent directories if they don't exist"
            }
        }

    def validate_params(self, path: str, content: str, **kwargs) -> bool:
        return isinstance(path, str) and isinstance(content, str)

    async def execute(
        self,
        path: str,
        content: str,
        create_dirs: bool = True
    ) -> ToolResult:
        try:
            file_path = pathlib.Path(path).resolve()

            # Create parent directories if needed
            if create_dirs:
                file_path.parent.mkdir(parents=True, exist_ok=True)

            # Check if parent directory exists
            if not file_path.parent.exists():
                return ToolResult(
                    False,
                    None,
                    f"Parent directory does not exist: {file_path.parent}"
                )

            # Write file asynchronously
            async with aiofiles.open(file_path, 'w', encoding='utf-8') as f:
                await f.write(content)

            return ToolResult(
                success=True,
                output=f"File written: {path}",
                metadata={
                    "bytes": len(content.encode('utf-8')),
                    "lines": len(content.splitlines()),
                    "path": str(file_path)
                }
            )

        except PermissionError:
            return ToolResult(False, None, f"Permission denied: {path}")
        except Exception as e:
            logger.error(f"Error writing file {path}: {str(e)}")
            return ToolResult(False, None, str(e))


class SearchFilesTool(BaseTool):
    """Search for files by pattern"""

    def __init__(self):
        super().__init__("search_files", ToolCategory.FILE)
        self.description = "Search for files matching a glob pattern"
        self.parameters = {
            "pattern": {
                "type": "string",
                "required": True,
                "description": "Glob pattern to match (e.g., '*.py', '**/*.ts')"
            },
            "path": {
                "type": "string",
                "default": ".",
                "description": "Base path to search from"
            },
            "max_results": {
                "type": "number",
                "default": 100,
                "description": "Maximum number of results to return"
            }
        }

    def validate_params(self, pattern: str, **kwargs) -> bool:
        return isinstance(pattern, str) and len(pattern) > 0

    async def execute(
        self,
        pattern: str,
        path: str = ".",
        max_results: int = 100
    ) -> ToolResult:
        try:
            base_path = pathlib.Path(path).resolve()

            if not base_path.exists():
                return ToolResult(False, None, f"Base path does not exist: {path}")

            if not base_path.is_dir():
                return ToolResult(False, None, f"Base path is not a directory: {path}")

            # Search for files
            all_matches = list(base_path.rglob(pattern))
            file_matches = [p for p in all_matches if p.is_file()]

            # Limit results
            limited_matches = file_matches[:max_results]
            file_list = [str(p.relative_to(base_path)) for p in limited_matches]

            return ToolResult(
                success=True,
                output=file_list,
                metadata={
                    "count": len(file_list),
                    "total_found": len(file_matches),
                    "truncated": len(file_matches) > max_results,
                    "base_path": str(base_path)
                }
            )

        except Exception as e:
            logger.error(f"Error searching files with pattern '{pattern}': {str(e)}")
            return ToolResult(False, None, str(e))


class ListDirectoryTool(BaseTool):
    """List contents of a directory"""

    def __init__(self):
        super().__init__("list_directory", ToolCategory.FILE)
        self.description = "List files and directories in a path"
        self.parameters = {
            "path": {
                "type": "string",
                "default": ".",
                "description": "Directory path to list"
            },
            "recursive": {
                "type": "boolean",
                "default": False,
                "description": "List recursively"
            },
            "max_depth": {
                "type": "number",
                "default": 3,
                "description": "Maximum recursion depth"
            }
        }

    def validate_params(self, **kwargs) -> bool:
        return True

    async def execute(
        self,
        path: str = ".",
        recursive: bool = False,
        max_depth: int = 3
    ) -> ToolResult:
        try:
            dir_path = pathlib.Path(path).resolve()

            if not dir_path.exists():
                return ToolResult(False, None, f"Directory not found: {path}")

            if not dir_path.is_dir():
                return ToolResult(False, None, f"Not a directory: {path}")

            entries = []

            if recursive:
                for item in dir_path.rglob("*"):
                    depth = len(item.relative_to(dir_path).parts)
                    if depth <= max_depth:
                        entries.append({
                            "name": item.name,
                            "path": str(item.relative_to(dir_path)),
                            "type": "file" if item.is_file() else "directory",
                            "size": item.stat().st_size if item.is_file() else None
                        })
            else:
                for item in dir_path.iterdir():
                    entries.append({
                        "name": item.name,
                        "path": item.name,
                        "type": "file" if item.is_file() else "directory",
                        "size": item.stat().st_size if item.is_file() else None
                    })

            return ToolResult(
                success=True,
                output=entries,
                metadata={
                    "count": len(entries),
                    "path": str(dir_path)
                }
            )

        except PermissionError:
            return ToolResult(False, None, f"Permission denied: {path}")
        except Exception as e:
            logger.error(f"Error listing directory {path}: {str(e)}")
            return ToolResult(False, None, str(e))

"""Filesystem Tools for Agentic 2.0

Cross-platform file system operations with safety controls:
- Read/write/list/search files
- Path resolution (workspace-aware)
- Safety checks via ToolSafetyManager
- Cross-platform compatibility (Windows/macOS/Linux)
"""

import asyncio
import aiofiles
import logging
from pathlib import Path
from typing import List, Dict, Any, Optional
from dataclasses import dataclass

from core.tool_safety import ToolSafetyManager, SafetyViolation

logger = logging.getLogger(__name__)


@dataclass
class ToolResult:
    """Result of a tool execution"""
    success: bool
    output: Any
    error: Optional[str] = None
    metadata: Optional[Dict[str, Any]] = None


class FileSystemTools:
    """File system operations with safety controls

    Features:
    - Read/write/list/search files
    - Workspace-aware path resolution
    - Safety validation before operations
    - Cross-platform path handling

    Example:
        >>> safety = ToolSafetyManager(...)
        >>> fs = FileSystemTools(safety, workspace="/project")
        >>> result = await fs.read_file("README.md")
        >>> print(result.output)
    """

    def __init__(
        self,
        safety_manager: ToolSafetyManager,
        workspace: Optional[str] = None,
    ):
        """Initialize FileSystemTools

        Args:
            safety_manager: ToolSafetyManager for validation
            workspace: Default workspace directory
        """
        self.safety = safety_manager
        self.workspace = Path(workspace).resolve() if workspace else Path.cwd()

        logger.info(f"📁 FileSystemTools initialized (workspace: {self.workspace})")

    def _resolve_path(self, path: str) -> Path:
        """Resolve path (absolute or relative to workspace)

        Args:
            path: File path to resolve

        Returns:
            Resolved absolute Path
        """
        path_obj = Path(path)

        if path_obj.is_absolute():
            return path_obj.resolve()
        else:
            # Relative path uses workspace
            return (self.workspace / path).resolve()

    async def read_file(
        self,
        path: str,
        max_size_mb: float = 10.0,
    ) -> ToolResult:
        """Read file contents

        Args:
            path: File path to read
            max_size_mb: Maximum file size in MB (default: 10)

        Returns:
            ToolResult with file contents or error
        """
        try:
            # Check safety
            violation = self.safety.check_file_access(path, "read")
            if violation:
                return ToolResult(
                    success=False,
                    output=None,
                    error=f"Safety violation: {violation.message}",
                    metadata={"violation": violation.violation_type.value}
                )

            # Resolve path
            file_path = self._resolve_path(path)

            # Existence checks
            if not file_path.exists():
                return ToolResult(
                    success=False,
                    output=None,
                    error=f"File not found: {path}"
                )

            if not file_path.is_file():
                return ToolResult(
                    success=False,
                    output=None,
                    error=f"Not a file: {path}"
                )

            # Size check
            size_bytes = file_path.stat().st_size
            size_mb = size_bytes / (1024 * 1024)

            if size_mb > max_size_mb:
                return ToolResult(
                    success=False,
                    output=None,
                    error=f"File too large: {size_mb:.2f}MB (limit: {max_size_mb}MB)"
                )

            # Read file
            async with aiofiles.open(file_path, 'r', encoding='utf-8') as f:
                content = await f.read()

            lines = content.splitlines()

            logger.info(f"✅ Read file: {path} ({size_mb:.2f}MB, {len(lines)} lines)")

            return ToolResult(
                success=True,
                output=content,
                metadata={
                    "path": str(file_path),
                    "size_mb": round(size_mb, 2),
                    "lines": len(lines),
                }
            )

        except UnicodeDecodeError:
            return ToolResult(
                success=False,
                output=None,
                error="File is not valid UTF-8 text (binary file?)"
            )
        except PermissionError:
            return ToolResult(
                success=False,
                output=None,
                error=f"Permission denied: {path}"
            )
        except Exception as e:
            logger.error(f"Error reading file {path}: {e}")
            return ToolResult(success=False, output=None, error=str(e))

    async def write_file(
        self,
        path: str,
        content: str,
        create_dirs: bool = True,
    ) -> ToolResult:
        """Write content to file

        Args:
            path: File path to write
            content: Content to write
            create_dirs: Create parent directories if needed (default: True)

        Returns:
            ToolResult with success status
        """
        try:
            # Check safety
            violation = self.safety.check_file_access(path, "write")
            if violation:
                return ToolResult(
                    success=False,
                    output=None,
                    error=f"Safety violation: {violation.message}",
                    metadata={"violation": violation.violation_type.value}
                )

            # Resolve path
            file_path = self._resolve_path(path)

            # Create parent directories
            if create_dirs:
                file_path.parent.mkdir(parents=True, exist_ok=True)
            elif not file_path.parent.exists():
                return ToolResult(
                    success=False,
                    output=None,
                    error=f"Parent directory does not exist: {file_path.parent}"
                )

            # Write file
            async with aiofiles.open(file_path, 'w', encoding='utf-8') as f:
                await f.write(content)

            size_bytes = len(content.encode('utf-8'))
            size_kb = size_bytes / 1024
            lines = len(content.splitlines())

            logger.info(f"✅ Wrote file: {path} ({size_kb:.2f}KB, {lines} lines)")

            return ToolResult(
                success=True,
                output=f"File written: {path}",
                metadata={
                    "path": str(file_path),
                    "bytes": size_bytes,
                    "lines": lines,
                }
            )

        except PermissionError:
            return ToolResult(
                success=False,
                output=None,
                error=f"Permission denied: {path}"
            )
        except Exception as e:
            logger.error(f"Error writing file {path}: {e}")
            return ToolResult(success=False, output=None, error=str(e))

    async def list_directory(
        self,
        path: str = ".",
        recursive: bool = False,
        max_depth: int = 3,
    ) -> ToolResult:
        """List directory contents

        Args:
            path: Directory path (default: "." = workspace)
            recursive: List recursively (default: False)
            max_depth: Maximum recursion depth (default: 3)

        Returns:
            ToolResult with list of entries
        """
        try:
            # Check safety
            violation = self.safety.check_file_access(path, "read")
            if violation:
                return ToolResult(
                    success=False,
                    output=None,
                    error=f"Safety violation: {violation.message}",
                    metadata={"violation": violation.violation_type.value}
                )

            # Resolve path
            dir_path = self._resolve_path(path)

            # Existence checks
            if not dir_path.exists():
                return ToolResult(
                    success=False,
                    output=None,
                    error=f"Directory not found: {path}"
                )

            if not dir_path.is_dir():
                return ToolResult(
                    success=False,
                    output=None,
                    error=f"Not a directory: {path}"
                )

            # List entries
            entries = []

            if recursive:
                for item in dir_path.rglob("*"):
                    try:
                        depth = len(item.relative_to(dir_path).parts)
                        if depth <= max_depth:
                            entries.append({
                                "name": item.name,
                                "path": str(item.relative_to(dir_path)),
                                "type": "file" if item.is_file() else "directory",
                                "size": item.stat().st_size if item.is_file() else None
                            })
                    except (PermissionError, OSError):
                        # Skip items we can't access
                        continue
            else:
                for item in dir_path.iterdir():
                    try:
                        entries.append({
                            "name": item.name,
                            "path": item.name,
                            "type": "file" if item.is_file() else "directory",
                            "size": item.stat().st_size if item.is_file() else None
                        })
                    except (PermissionError, OSError):
                        # Skip items we can't access
                        continue

            logger.info(f"✅ Listed directory: {path} ({len(entries)} entries)")

            return ToolResult(
                success=True,
                output=entries,
                metadata={
                    "path": str(dir_path),
                    "count": len(entries),
                    "recursive": recursive,
                }
            )

        except PermissionError:
            return ToolResult(
                success=False,
                output=None,
                error=f"Permission denied: {path}"
            )
        except Exception as e:
            logger.error(f"Error listing directory {path}: {e}")
            return ToolResult(success=False, output=None, error=str(e))

    async def search_files(
        self,
        pattern: str,
        path: str = ".",
        max_results: int = 100,
    ) -> ToolResult:
        """Search for files matching pattern

        Args:
            pattern: Glob pattern (e.g., "*.py", "**/*.ts")
            path: Base path to search from (default: "." = workspace)
            max_results: Maximum number of results (default: 100)

        Returns:
            ToolResult with list of matching files
        """
        try:
            # Check safety
            violation = self.safety.check_file_access(path, "read")
            if violation:
                return ToolResult(
                    success=False,
                    output=None,
                    error=f"Safety violation: {violation.message}",
                    metadata={"violation": violation.violation_type.value}
                )

            # Resolve path
            base_path = self._resolve_path(path)

            # Existence checks
            if not base_path.exists():
                return ToolResult(
                    success=False,
                    output=None,
                    error=f"Base path does not exist: {path}"
                )

            if not base_path.is_dir():
                return ToolResult(
                    success=False,
                    output=None,
                    error=f"Base path is not a directory: {path}"
                )

            # Search for files
            all_matches = []
            try:
                all_matches = list(base_path.rglob(pattern))
            except (PermissionError, OSError):
                # Continue with partial results if permission denied
                pass

            # Filter to files only
            file_matches = [p for p in all_matches if p.is_file()]

            # Limit results
            limited_matches = file_matches[:max_results]
            file_list = [str(p.relative_to(base_path)) for p in limited_matches]

            logger.info(
                f"✅ Search completed: {pattern} in {path} "
                f"({len(file_list)} results, {len(file_matches)} total)"
            )

            return ToolResult(
                success=True,
                output=file_list,
                metadata={
                    "pattern": pattern,
                    "base_path": str(base_path),
                    "count": len(file_list),
                    "total_found": len(file_matches),
                    "truncated": len(file_matches) > max_results,
                }
            )

        except Exception as e:
            logger.error(f"Error searching files with pattern '{pattern}': {e}")
            return ToolResult(success=False, output=None, error=str(e))

    async def file_exists(self, path: str) -> ToolResult:
        """Check if file exists

        Args:
            path: File path to check

        Returns:
            ToolResult with boolean output
        """
        try:
            file_path = self._resolve_path(path)
            exists = file_path.exists() and file_path.is_file()

            return ToolResult(
                success=True,
                output=exists,
                metadata={"path": str(file_path)}
            )
        except Exception as e:
            logger.error(f"Error checking file existence {path}: {e}")
            return ToolResult(success=False, output=None, error=str(e))

    async def directory_exists(self, path: str) -> ToolResult:
        """Check if directory exists

        Args:
            path: Directory path to check

        Returns:
            ToolResult with boolean output
        """
        try:
            dir_path = self._resolve_path(path)
            exists = dir_path.exists() and dir_path.is_dir()

            return ToolResult(
                success=True,
                output=exists,
                metadata={"path": str(dir_path)}
            )
        except Exception as e:
            logger.error(f"Error checking directory existence {path}: {e}")
            return ToolResult(success=False, output=None, error=str(e))

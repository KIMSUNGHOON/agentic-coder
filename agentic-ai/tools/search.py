"""Search Tools for Agentic 2.0

Content search operations:
- Grep-like file content search
- Regex pattern matching
- Multi-file search
- Cross-platform support
"""

import asyncio
import aiofiles
import re
import logging
from pathlib import Path
from typing import List, Dict, Any, Optional
from dataclasses import dataclass

from core.tool_safety import ToolSafetyManager

logger = logging.getLogger(__name__)


@dataclass
class ToolResult:
    """Result of a tool execution"""
    success: bool
    output: Any
    error: Optional[str] = None
    metadata: Optional[Dict[str, Any]] = None


@dataclass
class SearchMatch:
    """Represents a search match"""
    file_path: str
    line_number: int
    line_content: str
    match_start: int
    match_end: int


class SearchTools:
    """Content search operations with safety controls

    Features:
    - Grep-like content search
    - Regex pattern matching
    - Multi-file search
    - Case-sensitive/insensitive
    - Line context

    Example:
        >>> safety = ToolSafetyManager(...)
        >>> search = SearchTools(safety, workspace="/project")
        >>> result = await search.grep("TODO", "*.py")
        >>> print(result.output)
    """

    def __init__(
        self,
        safety_manager: ToolSafetyManager,
        workspace: Optional[str] = None,
    ):
        """Initialize SearchTools

        Args:
            safety_manager: ToolSafetyManager for validation
            workspace: Default workspace directory
        """
        self.safety = safety_manager
        self.workspace = Path(workspace).resolve() if workspace else Path.cwd()

        logger.info(f"🔍 SearchTools initialized (workspace: {self.workspace})")

    def _resolve_path(self, path: str) -> Path:
        """Resolve path (absolute or relative to workspace)

        Args:
            path: Path to resolve

        Returns:
            Resolved absolute Path
        """
        path_obj = Path(path)

        if path_obj.is_absolute():
            return path_obj.resolve()
        else:
            return (self.workspace / path).resolve()

    async def grep(
        self,
        pattern: str,
        file_pattern: str = "*",
        path: str = ".",
        case_sensitive: bool = True,
        regex: bool = False,
        max_matches: int = 100,
        context_lines: int = 0,
    ) -> ToolResult:
        """Search for pattern in files (grep-like)

        Args:
            pattern: Search pattern (string or regex)
            file_pattern: File glob pattern (default: "*" = all files)
            path: Base path to search (default: "." = workspace)
            case_sensitive: Case-sensitive matching (default: True)
            regex: Treat pattern as regex (default: False)
            max_matches: Maximum matches to return (default: 100)
            context_lines: Lines of context around match (default: 0)

        Returns:
            ToolResult with list of matches
        """
        try:
            # Safety check
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

            logger.info(
                f"🔍 Searching for '{pattern}' in {file_pattern} "
                f"(path: {path}, case_sensitive: {case_sensitive})"
            )

            # Compile pattern
            if regex:
                flags = 0 if case_sensitive else re.IGNORECASE
                compiled_pattern = re.compile(pattern, flags)
            else:
                # Escape pattern for literal match
                escaped_pattern = re.escape(pattern)
                flags = 0 if case_sensitive else re.IGNORECASE
                compiled_pattern = re.compile(escaped_pattern, flags)

            # Find matching files
            matching_files = list(base_path.rglob(file_pattern))
            file_paths = [p for p in matching_files if p.is_file()]

            # Search in files
            all_matches = []
            files_searched = 0

            for file_path in file_paths:
                if len(all_matches) >= max_matches:
                    break

                # Check file safety
                violation = self.safety.check_file_access(str(file_path), "read")
                if violation:
                    continue

                try:
                    # Read file and search
                    async with aiofiles.open(file_path, 'r', encoding='utf-8', errors='ignore') as f:
                        lines = await f.readlines()

                    files_searched += 1

                    for line_num, line in enumerate(lines, start=1):
                        match = compiled_pattern.search(line)
                        if match:
                            relative_path = str(file_path.relative_to(base_path))

                            match_info = {
                                "file": relative_path,
                                "line": line_num,
                                "content": line.rstrip('\n'),
                                "match_start": match.start(),
                                "match_end": match.end(),
                            }

                            # Add context lines if requested
                            if context_lines > 0:
                                before_lines = []
                                after_lines = []

                                for i in range(1, context_lines + 1):
                                    # Before context
                                    if line_num - i > 0:
                                        before_lines.insert(0, lines[line_num - i - 1].rstrip('\n'))

                                    # After context
                                    if line_num + i <= len(lines):
                                        after_lines.append(lines[line_num + i - 1].rstrip('\n'))

                                match_info["context_before"] = before_lines
                                match_info["context_after"] = after_lines

                            all_matches.append(match_info)

                            if len(all_matches) >= max_matches:
                                break

                except (PermissionError, OSError, UnicodeDecodeError):
                    # Skip files we can't read
                    continue

            truncated = len(all_matches) >= max_matches

            logger.info(
                f"✅ Search completed: {len(all_matches)} matches in {files_searched} files "
                f"({'truncated' if truncated else 'complete'})"
            )

            return ToolResult(
                success=True,
                output=all_matches,
                metadata={
                    "pattern": pattern,
                    "base_path": str(base_path),
                    "matches": len(all_matches),
                    "files_searched": files_searched,
                    "truncated": truncated,
                }
            )

        except Exception as e:
            logger.error(f"Error searching for pattern: {e}")
            return ToolResult(success=False, output=None, error=str(e))

    async def find_in_file(
        self,
        file_path: str,
        pattern: str,
        case_sensitive: bool = True,
        regex: bool = False,
        max_matches: int = 100,
    ) -> ToolResult:
        """Search for pattern in a single file

        Args:
            file_path: File to search
            pattern: Search pattern
            case_sensitive: Case-sensitive matching (default: True)
            regex: Treat pattern as regex (default: False)
            max_matches: Maximum matches to return (default: 100)

        Returns:
            ToolResult with list of matches
        """
        try:
            # Safety check
            violation = self.safety.check_file_access(file_path, "read")
            if violation:
                return ToolResult(
                    success=False,
                    output=None,
                    error=f"Safety violation: {violation.message}",
                    metadata={"violation": violation.violation_type.value}
                )

            # Resolve path
            resolved_path = self._resolve_path(file_path)

            if not resolved_path.exists():
                return ToolResult(
                    success=False,
                    output=None,
                    error=f"File not found: {file_path}"
                )

            if not resolved_path.is_file():
                return ToolResult(
                    success=False,
                    output=None,
                    error=f"Not a file: {file_path}"
                )

            logger.info(f"🔍 Searching in file: {file_path}")

            # Compile pattern
            if regex:
                flags = 0 if case_sensitive else re.IGNORECASE
                compiled_pattern = re.compile(pattern, flags)
            else:
                escaped_pattern = re.escape(pattern)
                flags = 0 if case_sensitive else re.IGNORECASE
                compiled_pattern = re.compile(escaped_pattern, flags)

            # Read and search file
            async with aiofiles.open(resolved_path, 'r', encoding='utf-8', errors='ignore') as f:
                lines = await f.readlines()

            matches = []

            for line_num, line in enumerate(lines, start=1):
                match = compiled_pattern.search(line)
                if match:
                    matches.append({
                        "line": line_num,
                        "content": line.rstrip('\n'),
                        "match_start": match.start(),
                        "match_end": match.end(),
                    })

                    if len(matches) >= max_matches:
                        break

            logger.info(f"✅ Found {len(matches)} matches in {file_path}")

            return ToolResult(
                success=True,
                output=matches,
                metadata={
                    "file": str(resolved_path),
                    "matches": len(matches),
                    "total_lines": len(lines),
                }
            )

        except Exception as e:
            logger.error(f"Error searching file: {e}")
            return ToolResult(success=False, output=None, error=str(e))

    async def count_occurrences(
        self,
        pattern: str,
        file_pattern: str = "*",
        path: str = ".",
        case_sensitive: bool = True,
    ) -> ToolResult:
        """Count occurrences of pattern in files

        Args:
            pattern: Search pattern
            file_pattern: File glob pattern (default: "*")
            path: Base path to search (default: ".")
            case_sensitive: Case-sensitive matching (default: True)

        Returns:
            ToolResult with count by file
        """
        try:
            # Reuse grep with unlimited matches
            result = await self.grep(
                pattern=pattern,
                file_pattern=file_pattern,
                path=path,
                case_sensitive=case_sensitive,
                regex=False,
                max_matches=999999,  # High limit for counting
            )

            if not result.success:
                return result

            # Count matches per file
            matches_by_file = {}
            for match in result.output:
                file_path = match["file"]
                matches_by_file[file_path] = matches_by_file.get(file_path, 0) + 1

            total_matches = sum(matches_by_file.values())

            logger.info(
                f"✅ Counted {total_matches} occurrences in {len(matches_by_file)} files"
            )

            return ToolResult(
                success=True,
                output={
                    "total_matches": total_matches,
                    "files_with_matches": len(matches_by_file),
                    "by_file": matches_by_file,
                },
                metadata={
                    "pattern": pattern,
                    "total": total_matches,
                }
            )

        except Exception as e:
            logger.error(f"Error counting occurrences: {e}")
            return ToolResult(success=False, output=None, error=str(e))

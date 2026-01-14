"""Git Tools for Agentic 2.0

Cross-platform Git operations with safety controls:
- Status, diff, log operations
- Command execution via subprocess
- Cross-platform compatibility
"""

import asyncio
import logging
import shutil
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


class GitTools:
    """Git operations with safety controls

    Features:
    - Standard Git operations (status, diff, log, etc.)
    - Command validation via ToolSafetyManager
    - Cross-platform support
    - Async execution

    Example:
        >>> safety = ToolSafetyManager(...)
        >>> git = GitTools(safety)
        >>> result = await git.status()
        >>> print(result.output)
    """

    def __init__(self, safety_manager: ToolSafetyManager):
        """Initialize GitTools

        Args:
            safety_manager: ToolSafetyManager for validation
        """
        self.safety = safety_manager

        # Check if git is available
        self.git_available = shutil.which("git") is not None

        if self.git_available:
            logger.info("🔧 GitTools initialized (git found)")
        else:
            logger.warning("⚠️  GitTools initialized (git NOT found)")

    async def _run_git_command(
        self,
        args: List[str],
        timeout: int = 30,
    ) -> ToolResult:
        """Run git command with safety validation

        Args:
            args: Git command arguments (e.g., ["status", "--porcelain"])
            timeout: Command timeout in seconds (default: 30)

        Returns:
            ToolResult with command output or error
        """
        if not self.git_available:
            return ToolResult(
                success=False,
                output=None,
                error="Git is not installed or not in PATH"
            )

        # Build full command
        full_command = ["git"] + args
        command_str = " ".join(full_command)

        # Safety check
        violation = self.safety.check_command(command_str)
        if violation:
            return ToolResult(
                success=False,
                output=None,
                error=f"Safety violation: {violation.message}",
                metadata={"violation": violation.violation_type.value}
            )

        try:
            # Execute command
            process = await asyncio.create_subprocess_exec(
                *full_command,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
            )

            stdout, stderr = await asyncio.wait_for(
                process.communicate(),
                timeout=timeout
            )

            if process.returncode != 0:
                error_msg = stderr.decode('utf-8', errors='replace').strip()
                return ToolResult(
                    success=False,
                    output=None,
                    error=f"Git command failed: {error_msg}",
                    metadata={"return_code": process.returncode}
                )

            output = stdout.decode('utf-8', errors='replace')
            return ToolResult(
                success=True,
                output=output,
                metadata={"command": command_str}
            )

        except asyncio.TimeoutError:
            return ToolResult(
                success=False,
                output=None,
                error=f"Git command timed out after {timeout}s"
            )
        except Exception as e:
            logger.error(f"Error running git command: {e}")
            return ToolResult(success=False, output=None, error=str(e))

    async def status(self) -> ToolResult:
        """Get repository status

        Returns:
            ToolResult with parsed status information
        """
        try:
            result = await self._run_git_command(["status", "--porcelain"])

            if not result.success:
                return result

            # Parse status output
            status_output = result.output
            lines = status_output.strip().split('\n') if status_output.strip() else []

            staged = []
            modified = []
            untracked = []

            for line in lines:
                if not line:
                    continue

                status_code = line[:2]
                filename = line[3:]

                # Staged files
                if status_code[0] in ['M', 'A', 'D', 'R', 'C']:
                    staged.append(filename)

                # Modified files (unstaged)
                if status_code[1] == 'M':
                    modified.append(filename)

                # Untracked files
                if status_code == '??':
                    untracked.append(filename)

            is_clean = len(lines) == 0

            logger.info(
                f"✅ Git status: {len(staged)} staged, {len(modified)} modified, "
                f"{len(untracked)} untracked"
            )

            return ToolResult(
                success=True,
                output={
                    "staged": staged,
                    "modified": modified,
                    "untracked": untracked,
                    "clean": is_clean,
                    "raw": status_output,
                },
                metadata={"total_changes": len(lines)}
            )

        except Exception as e:
            logger.error(f"Error getting git status: {e}")
            return ToolResult(success=False, output=None, error=str(e))

    async def diff(
        self,
        cached: bool = False,
        file_path: Optional[str] = None,
    ) -> ToolResult:
        """Get repository diff

        Args:
            cached: Show staged changes only (default: False)
            file_path: Specific file to diff (default: None = all files)

        Returns:
            ToolResult with diff output
        """
        try:
            args = ["diff"]

            if cached:
                args.append("--cached")

            if file_path:
                args.append(file_path)

            result = await self._run_git_command(args)

            if result.success:
                has_changes = len(result.output.strip()) > 0
                logger.info(f"✅ Git diff: {'Changes found' if has_changes else 'No changes'}")

                return ToolResult(
                    success=True,
                    output=result.output,
                    metadata={
                        "has_changes": has_changes,
                        "cached": cached,
                        "file": file_path,
                    }
                )

            return result

        except Exception as e:
            logger.error(f"Error getting git diff: {e}")
            return ToolResult(success=False, output=None, error=str(e))

    async def log(self, max_count: int = 10) -> ToolResult:
        """Get commit history

        Args:
            max_count: Number of commits to show (default: 10)

        Returns:
            ToolResult with list of commits
        """
        try:
            result = await self._run_git_command([
                "log",
                f"--max-count={max_count}",
                "--pretty=format:%h|%an|%ar|%s"
            ])

            if not result.success:
                return result

            # Parse log output
            log_output = result.output.strip()
            lines = log_output.split('\n') if log_output else []

            commits = []
            for line in lines:
                if not line:
                    continue

                parts = line.split('|', 3)
                if len(parts) == 4:
                    commits.append({
                        "hash": parts[0],
                        "author": parts[1],
                        "date": parts[2],
                        "message": parts[3],
                    })

            logger.info(f"✅ Git log: {len(commits)} commits")

            return ToolResult(
                success=True,
                output=commits,
                metadata={
                    "count": len(commits),
                    "raw": log_output,
                }
            )

        except Exception as e:
            logger.error(f"Error getting git log: {e}")
            return ToolResult(success=False, output=None, error=str(e))

    async def show_branch(self) -> ToolResult:
        """Get current branch name

        Returns:
            ToolResult with branch name
        """
        try:
            result = await self._run_git_command(["branch", "--show-current"])

            if result.success:
                branch_name = result.output.strip()
                logger.info(f"✅ Current branch: {branch_name}")

                return ToolResult(
                    success=True,
                    output=branch_name,
                    metadata={"branch": branch_name}
                )

            return result

        except Exception as e:
            logger.error(f"Error getting current branch: {e}")
            return ToolResult(success=False, output=None, error=str(e))

    async def list_branches(self) -> ToolResult:
        """List all branches

        Returns:
            ToolResult with list of branches
        """
        try:
            result = await self._run_git_command(["branch", "--list"])

            if not result.success:
                return result

            # Parse branch output
            branch_output = result.output.strip()
            lines = branch_output.split('\n') if branch_output else []

            branches = []
            current_branch = None

            for line in lines:
                if not line:
                    continue

                # Current branch starts with *
                is_current = line.startswith('*')
                branch_name = line.strip().lstrip('* ').strip()

                branches.append(branch_name)

                if is_current:
                    current_branch = branch_name

            logger.info(f"✅ Listed {len(branches)} branches (current: {current_branch})")

            return ToolResult(
                success=True,
                output={
                    "branches": branches,
                    "current": current_branch,
                },
                metadata={"count": len(branches)}
            )

        except Exception as e:
            logger.error(f"Error listing branches: {e}")
            return ToolResult(success=False, output=None, error=str(e))

    async def add(self, paths: List[str]) -> ToolResult:
        """Stage files for commit

        Args:
            paths: List of file paths to stage

        Returns:
            ToolResult with success status
        """
        try:
            args = ["add"] + paths
            result = await self._run_git_command(args)

            if result.success:
                logger.info(f"✅ Staged {len(paths)} files")

                return ToolResult(
                    success=True,
                    output=f"Staged {len(paths)} files",
                    metadata={"files": paths}
                )

            return result

        except Exception as e:
            logger.error(f"Error staging files: {e}")
            return ToolResult(success=False, output=None, error=str(e))

    async def commit(self, message: str) -> ToolResult:
        """Create a commit

        Args:
            message: Commit message

        Returns:
            ToolResult with commit hash
        """
        try:
            result = await self._run_git_command(["commit", "-m", message])

            if result.success:
                # Extract commit hash from output
                output = result.output.strip()
                logger.info(f"✅ Created commit: {message[:50]}")

                return ToolResult(
                    success=True,
                    output=output,
                    metadata={"message": message}
                )

            return result

        except Exception as e:
            logger.error(f"Error creating commit: {e}")
            return ToolResult(success=False, output=None, error=str(e))

    async def is_repository(self) -> ToolResult:
        """Check if current directory is a git repository

        Returns:
            ToolResult with boolean output
        """
        try:
            result = await self._run_git_command(["rev-parse", "--git-dir"])

            return ToolResult(
                success=True,
                output=result.success,
                metadata={"is_repository": result.success}
            )

        except Exception as e:
            logger.error(f"Error checking repository: {e}")
            return ToolResult(success=True, output=False, error=None)

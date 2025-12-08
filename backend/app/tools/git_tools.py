"""
Git Tools - Version control operations
"""

import asyncio
import logging
from typing import Optional

from .base import BaseTool, ToolCategory, ToolResult

logger = logging.getLogger(__name__)


class GitStatusTool(BaseTool):
    """Get git repository status"""

    def __init__(self):
        super().__init__("git_status", ToolCategory.GIT)
        self.description = "Get current git repository status"
        self.parameters = {}

    def validate_params(self, **kwargs) -> bool:
        return True

    async def execute(self) -> ToolResult:
        try:
            # Run git status with porcelain format
            process = await asyncio.create_subprocess_exec(
                'git', 'status', '--porcelain',
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE
            )

            stdout, stderr = await process.communicate()

            if process.returncode != 0:
                return ToolResult(
                    False,
                    None,
                    f"Git error: {stderr.decode('utf-8')}"
                )

            status_output = stdout.decode('utf-8')
            lines = status_output.strip().split('\n') if status_output.strip() else []

            # Parse status
            modified = []
            untracked = []
            staged = []

            for line in lines:
                if not line:
                    continue

                status = line[:2]
                filename = line[3:]

                if status[0] in ['M', 'A', 'D', 'R']:
                    staged.append(filename)
                if status[1] == 'M':
                    modified.append(filename)
                if status == '??':
                    untracked.append(filename)

            return ToolResult(
                success=True,
                output={
                    "staged": staged,
                    "modified": modified,
                    "untracked": untracked,
                    "clean": len(lines) == 0,
                    "raw": status_output
                }
            )

        except FileNotFoundError:
            return ToolResult(False, None, "Git not found. Please install git.")
        except Exception as e:
            logger.error(f"Error getting git status: {str(e)}")
            return ToolResult(False, None, str(e))


class GitDiffTool(BaseTool):
    """View git changes"""

    def __init__(self):
        super().__init__("git_diff", ToolCategory.GIT)
        self.description = "View git changes (diff)"
        self.parameters = {
            "cached": {
                "type": "boolean",
                "default": False,
                "description": "Show staged changes only"
            },
            "file_path": {
                "type": "string",
                "required": False,
                "description": "Specific file to diff"
            }
        }

    def validate_params(self, **kwargs) -> bool:
        return True

    async def execute(
        self,
        cached: bool = False,
        file_path: Optional[str] = None
    ) -> ToolResult:
        try:
            cmd = ['git', 'diff']
            if cached:
                cmd.append('--cached')
            if file_path:
                cmd.append(file_path)

            process = await asyncio.create_subprocess_exec(
                *cmd,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE
            )

            stdout, stderr = await asyncio.wait_for(
                process.communicate(),
                timeout=30
            )

            if process.returncode != 0:
                return ToolResult(
                    False,
                    None,
                    f"Git error: {stderr.decode('utf-8')}"
                )

            diff_output = stdout.decode('utf-8')

            return ToolResult(
                success=True,
                output=diff_output,
                metadata={
                    "has_changes": len(diff_output) > 0,
                    "cached": cached,
                    "file": file_path
                }
            )

        except asyncio.TimeoutError:
            return ToolResult(False, None, "Git diff timeout")
        except FileNotFoundError:
            return ToolResult(False, None, "Git not found")
        except Exception as e:
            logger.error(f"Error getting git diff: {str(e)}")
            return ToolResult(False, None, str(e))


class GitLogTool(BaseTool):
    """View git commit history"""

    def __init__(self):
        super().__init__("git_log", ToolCategory.GIT)
        self.description = "View recent git commits"
        self.parameters = {
            "max_count": {
                "type": "number",
                "default": 10,
                "description": "Number of commits to show"
            }
        }

    def validate_params(self, **kwargs) -> bool:
        return True

    async def execute(self, max_count: int = 10) -> ToolResult:
        try:
            process = await asyncio.create_subprocess_exec(
                'git', 'log',
                f'--max-count={max_count}',
                '--pretty=format:%h|%an|%ar|%s',
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE
            )

            stdout, stderr = await process.communicate()

            if process.returncode != 0:
                return ToolResult(
                    False,
                    None,
                    f"Git error: {stderr.decode('utf-8')}"
                )

            log_output = stdout.decode('utf-8')
            commits = []

            for line in log_output.strip().split('\n'):
                if not line:
                    continue

                parts = line.split('|', 3)
                if len(parts) == 4:
                    commits.append({
                        "hash": parts[0],
                        "author": parts[1],
                        "date": parts[2],
                        "message": parts[3]
                    })

            return ToolResult(
                success=True,
                output=commits,
                metadata={
                    "count": len(commits)
                }
            )

        except FileNotFoundError:
            return ToolResult(False, None, "Git not found")
        except Exception as e:
            logger.error(f"Error getting git log: {str(e)}")
            return ToolResult(False, None, str(e))


class GitBranchTool(BaseTool):
    """Get current git branch"""

    def __init__(self):
        super().__init__("git_branch", ToolCategory.GIT)
        self.description = "Get current git branch name"
        self.parameters = {}

    def validate_params(self, **kwargs) -> bool:
        return True

    async def execute(self) -> ToolResult:
        try:
            process = await asyncio.create_subprocess_exec(
                'git', 'branch', '--show-current',
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE
            )

            stdout, stderr = await process.communicate()

            if process.returncode != 0:
                return ToolResult(
                    False,
                    None,
                    f"Git error: {stderr.decode('utf-8')}"
                )

            branch_name = stdout.decode('utf-8').strip()

            return ToolResult(
                success=True,
                output=branch_name
            )

        except FileNotFoundError:
            return ToolResult(False, None, "Git not found")
        except Exception as e:
            logger.error(f"Error getting git branch: {str(e)}")
            return ToolResult(False, None, str(e))

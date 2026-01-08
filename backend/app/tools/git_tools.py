"""
Git Tools - Version control operations
"""

import asyncio
import logging
from typing import Optional, List

from .base import BaseTool, ToolCategory, ToolResult, NetworkType

logger = logging.getLogger(__name__)


class GitStatusTool(BaseTool):
    """Get git repository status"""

    def __init__(self):
        super().__init__("git_status", ToolCategory.GIT)

        # Phase 2: Network requirement - LOCAL (local git command)
        self.requires_network = False
        self.network_type = NetworkType.LOCAL

        self.description = "Get current git repository status - works offline"
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

        # Phase 2: Network requirement - LOCAL (local git command)
        self.requires_network = False
        self.network_type = NetworkType.LOCAL

        self.description = "View git changes (diff) - works offline"
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

        # Phase 2: Network requirement - LOCAL (local git command)
        self.requires_network = False
        self.network_type = NetworkType.LOCAL

        self.description = "View recent git commits - works offline"
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

        # Phase 2: Network requirement - LOCAL (local git command)
        self.requires_network = False
        self.network_type = NetworkType.LOCAL

        self.description = "Get current git branch name - works offline"
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


class GitCommitTool(BaseTool):
    """Create git commit"""

    def __init__(self):
        super().__init__("git_commit", ToolCategory.GIT)

        # Phase 2: Network requirement - LOCAL (local git command)
        self.requires_network = False
        self.network_type = NetworkType.LOCAL

        self.description = "Create a git commit with staged or specified files - works offline"
        self.parameters = {
            "message": {
                "type": "string",
                "required": True,
                "description": "Commit message"
            },
            "files": {
                "type": "array",
                "items": {"type": "string"},
                "required": False,
                "description": "Specific files to stage and commit. If not provided, commits all staged files."
            },
            "add_all": {
                "type": "boolean",
                "default": False,
                "required": False,
                "description": "Stage all modified files before committing"
            }
        }

    def validate_params(self, **kwargs) -> bool:
        """Validate commit parameters"""
        # Validate message
        if "message" not in kwargs or not kwargs["message"]:
            logger.error("Commit message is required")
            return False

        message = kwargs["message"].strip()
        if len(message) < 5:
            logger.error("Commit message too short (minimum 5 characters)")
            return False

        if len(message) > 500:
            logger.error("Commit message too long (maximum 500 characters)")
            return False

        # Validate files if provided
        if "files" in kwargs and kwargs["files"]:
            files = kwargs["files"]
            if not isinstance(files, list):
                logger.error("Files parameter must be a list")
                return False

        return True

    async def execute(
        self,
        message: str,
        files: Optional[List[str]] = None,
        add_all: bool = False
    ) -> ToolResult:
        """Execute git commit

        Args:
            message: Commit message
            files: Optional list of specific files to stage and commit
            add_all: If True, stage all modified files (git add -A)

        Returns:
            ToolResult with commit information
        """
        try:
            logger.info(f"🔨 Creating git commit: '{message[:50]}...'")

            # Step 1: Stage files if needed
            staged_files = []

            if add_all:
                # Stage all modified files
                logger.info("   Staging all modified files (git add -A)")
                process = await asyncio.create_subprocess_exec(
                    'git', 'add', '-A',
                    stdout=asyncio.subprocess.PIPE,
                    stderr=asyncio.subprocess.PIPE
                )
                stdout, stderr = await process.communicate()

                if process.returncode != 0:
                    error_msg = f"Failed to stage files: {stderr.decode('utf-8')}"
                    logger.error(f"❌ {error_msg}")
                    return ToolResult(False, None, error_msg)

                staged_files.append("all modified files")

            elif files:
                # Stage specific files
                logger.info(f"   Staging {len(files)} specific files")
                cmd = ['git', 'add'] + files
                process = await asyncio.create_subprocess_exec(
                    *cmd,
                    stdout=asyncio.subprocess.PIPE,
                    stderr=asyncio.subprocess.PIPE
                )
                stdout, stderr = await process.communicate()

                if process.returncode != 0:
                    error_msg = f"Failed to stage files: {stderr.decode('utf-8')}"
                    logger.error(f"❌ {error_msg}")
                    return ToolResult(False, None, error_msg)

                staged_files.extend(files)

            # Step 2: Check if there are changes to commit
            status_process = await asyncio.create_subprocess_exec(
                'git', 'status', '--porcelain',
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE
            )
            stdout, stderr = await status_process.communicate()

            if status_process.returncode == 0:
                status_output = stdout.decode('utf-8').strip()
                # Check for staged changes (lines starting with M, A, D, R in first column)
                has_staged = any(
                    line[0] in ['M', 'A', 'D', 'R']
                    for line in status_output.split('\n')
                    if line
                )

                if not has_staged:
                    logger.warning("⚠️  No staged changes to commit")
                    return ToolResult(
                        success=False,
                        output=None,
                        error="Nothing to commit (no staged changes). Use add_all=True or specify files."
                    )

            # Step 3: Create commit
            logger.info(f"   Creating commit with message: '{message}'")
            process = await asyncio.create_subprocess_exec(
                'git', 'commit', '-m', message,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE
            )

            stdout, stderr = await asyncio.wait_for(
                process.communicate(),
                timeout=30
            )

            if process.returncode != 0:
                error_output = stderr.decode('utf-8')

                # Check for common errors
                if "nothing to commit" in error_output.lower():
                    logger.warning("⚠️  Nothing to commit")
                    return ToolResult(
                        success=False,
                        output=None,
                        error="Nothing to commit (working tree clean)"
                    )

                error_msg = f"Git commit failed: {error_output}"
                logger.error(f"❌ {error_msg}")
                return ToolResult(False, None, error_msg)

            commit_output = stdout.decode('utf-8')

            # Parse commit hash from output (first line usually contains it)
            commit_hash = None
            for line in commit_output.split('\n'):
                if line.strip():
                    # Extract hash if present (e.g., "[master 1a2b3c4]")
                    import re
                    match = re.search(r'\[.+?\s+([a-f0-9]+)\]', line)
                    if match:
                        commit_hash = match.group(1)
                        break

            logger.info(f"✅ Commit created successfully: {commit_hash or 'unknown'}")

            return ToolResult(
                success=True,
                output={
                    "commit_hash": commit_hash,
                    "message": message,
                    "staged_files": staged_files if staged_files else None,
                    "raw_output": commit_output,
                    "summary": f"Commit created: {message}"
                },
                metadata={
                    "tool": self.name,
                    "commit_hash": commit_hash,
                    "files_count": len(staged_files) if staged_files else None
                }
            )

        except asyncio.TimeoutError:
            error_msg = "Git commit timeout (exceeded 30 seconds)"
            logger.error(f"❌ {error_msg}")
            return ToolResult(False, None, error_msg)

        except FileNotFoundError:
            error_msg = "Git not found. Please install git."
            logger.error(f"❌ {error_msg}")
            return ToolResult(False, None, error_msg)

        except Exception as e:
            error_msg = f"Error creating git commit: {str(e)}"
            logger.error(f"❌ {error_msg}", exc_info=True)
            return ToolResult(False, None, error_msg)

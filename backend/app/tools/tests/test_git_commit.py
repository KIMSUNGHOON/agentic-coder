"""
Unit tests for GitCommitTool
"""

import pytest
import asyncio
from unittest.mock import Mock, patch, AsyncMock
from app.tools.git_tools import GitCommitTool
from app.tools.base import ToolResult


class TestGitCommitTool:
    """Test cases for GitCommitTool"""

    def test_init(self):
        """Test tool initialization"""
        tool = GitCommitTool()
        assert tool.name == "git_commit"
        assert "message" in tool.parameters
        assert "files" in tool.parameters
        assert "add_all" in tool.parameters

    def test_validate_params_valid(self):
        """Test parameter validation with valid params"""
        tool = GitCommitTool()

        # Valid params
        assert tool.validate_params(message="Valid commit message") is True
        assert tool.validate_params(message="Fix bug", files=["file1.py"]) is True
        assert tool.validate_params(message="Update docs", add_all=True) is True

    def test_validate_params_invalid(self):
        """Test parameter validation with invalid params"""
        tool = GitCommitTool()

        # Missing message
        assert tool.validate_params() is False
        assert tool.validate_params(message="") is False

        # Message too short
        assert tool.validate_params(message="fix") is False

        # Message too long
        long_message = "x" * 501
        assert tool.validate_params(message=long_message) is False

        # Invalid files parameter
        assert tool.validate_params(message="Valid message", files="not a list") is False

    @pytest.mark.asyncio
    async def test_execute_nothing_to_commit(self):
        """Test execution when there's nothing to commit"""
        tool = GitCommitTool()

        # Mock subprocess for git status (no staged files)
        mock_status_process = AsyncMock()
        mock_status_process.returncode = 0
        mock_status_process.communicate = AsyncMock(return_value=(b"", b""))

        with patch('asyncio.create_subprocess_exec', return_value=mock_status_process):
            result = await tool.execute(message="Test commit")

            assert result.success is False
            assert "Nothing to commit" in result.error or "no staged changes" in result.error

    @pytest.mark.asyncio
    async def test_execute_with_add_all(self):
        """Test execution with add_all flag"""
        tool = GitCommitTool()

        # Mock git add -A
        mock_add_process = AsyncMock()
        mock_add_process.returncode = 0
        mock_add_process.communicate = AsyncMock(return_value=(b"", b""))

        # Mock git status (has staged files)
        mock_status_process = AsyncMock()
        mock_status_process.returncode = 0
        mock_status_process.communicate = AsyncMock(return_value=(b"M  file1.py\n", b""))

        # Mock git commit
        mock_commit_process = AsyncMock()
        mock_commit_process.returncode = 0
        mock_commit_process.communicate = AsyncMock(
            return_value=(b"[main 1a2b3c4] Test commit\n 1 file changed\n", b"")
        )

        async def mock_exec(*args, **kwargs):
            if 'add' in args:
                return mock_add_process
            elif 'status' in args:
                return mock_status_process
            elif 'commit' in args:
                return mock_commit_process

        with patch('asyncio.create_subprocess_exec', side_effect=mock_exec):
            with patch('asyncio.wait_for', side_effect=lambda coro, timeout: coro):
                result = await tool.execute(
                    message="Test commit",
                    add_all=True
                )

                assert result.success is True
                assert result.output["message"] == "Test commit"
                assert "commit_hash" in result.output

    @pytest.mark.asyncio
    async def test_execute_with_specific_files(self):
        """Test execution with specific files"""
        tool = GitCommitTool()

        # Mock git add file1.py file2.py
        mock_add_process = AsyncMock()
        mock_add_process.returncode = 0
        mock_add_process.communicate = AsyncMock(return_value=(b"", b""))

        # Mock git status (has staged files)
        mock_status_process = AsyncMock()
        mock_status_process.returncode = 0
        mock_status_process.communicate = AsyncMock(return_value=(b"M  file1.py\nM  file2.py\n", b""))

        # Mock git commit
        mock_commit_process = AsyncMock()
        mock_commit_process.returncode = 0
        mock_commit_process.communicate = AsyncMock(
            return_value=(b"[main abc123] Update files\n 2 files changed\n", b"")
        )

        async def mock_exec(*args, **kwargs):
            if 'add' in args:
                return mock_add_process
            elif 'status' in args:
                return mock_status_process
            elif 'commit' in args:
                return mock_commit_process

        with patch('asyncio.create_subprocess_exec', side_effect=mock_exec):
            with patch('asyncio.wait_for', side_effect=lambda coro, timeout: coro):
                result = await tool.execute(
                    message="Update files",
                    files=["file1.py", "file2.py"]
                )

                assert result.success is True
                assert result.output["message"] == "Update files"
                assert "file1.py" in result.output["staged_files"]

    @pytest.mark.asyncio
    async def test_execute_git_not_found(self):
        """Test execution when git is not installed"""
        tool = GitCommitTool()

        with patch('asyncio.create_subprocess_exec', side_effect=FileNotFoundError):
            result = await tool.execute(message="Test commit")

            assert result.success is False
            assert "Git not found" in result.error

    @pytest.mark.asyncio
    async def test_execute_commit_timeout(self):
        """Test execution when commit times out"""
        tool = GitCommitTool()

        # Mock processes for add and status
        mock_add_process = AsyncMock()
        mock_add_process.returncode = 0
        mock_add_process.communicate = AsyncMock(return_value=(b"", b""))

        mock_status_process = AsyncMock()
        mock_status_process.returncode = 0
        mock_status_process.communicate = AsyncMock(return_value=(b"M  file.py\n", b""))

        async def mock_exec(*args, **kwargs):
            if 'add' in args:
                return mock_add_process
            elif 'status' in args:
                return mock_status_process
            elif 'commit' in args:
                # Simulate a process that takes too long
                await asyncio.sleep(100)
                return AsyncMock()

        with patch('asyncio.create_subprocess_exec', side_effect=mock_exec):
            with patch('asyncio.wait_for', side_effect=asyncio.TimeoutError):
                result = await tool.execute(message="Test", add_all=True)

                assert result.success is False
                assert "timeout" in result.error.lower()

    def test_get_schema(self):
        """Test tool schema generation"""
        tool = GitCommitTool()
        schema = tool.get_schema()

        assert schema["name"] == "git_commit"
        assert "message" in schema["parameters"]
        assert "files" in schema["parameters"]
        assert "add_all" in schema["parameters"]

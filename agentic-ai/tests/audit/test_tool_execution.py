"""Tool Execution Integration Tests

Tests that all tools actually work and produce expected results.
This is critical for ensuring the system functions correctly.
"""

import pytest
import asyncio
import os
import tempfile
import shutil
from pathlib import Path

# Import tools
import sys
sys.path.insert(0, str(Path(__file__).parent.parent))

from tools.filesystem import FileSystemTools
from tools.search import SearchTools
from tools.process import ProcessTools
from core.config import Config
from core.tool_safety import ToolSafetyManager


@pytest.fixture
def temp_workspace():
    """Create a temporary workspace for testing"""
    temp_dir = tempfile.mkdtemp(prefix="agentic_test_")
    yield temp_dir
    shutil.rmtree(temp_dir, ignore_errors=True)


@pytest.fixture
def fs_tools(temp_workspace):
    """Create FileSystemTools instance"""
    config = Config()
    safety = ToolSafetyManager(config=config)
    return FileSystemTools(safety_manager=safety, workspace=temp_workspace)


@pytest.fixture
def search_tools(temp_workspace):
    """Create SearchTools instance"""
    return SearchTools(workspace=temp_workspace)


@pytest.fixture
def process_tools():
    """Create ProcessTools instance"""
    config = Config()
    return ProcessTools(config=config)


class TestFilesystemTools:
    """Test filesystem tool operations"""

    @pytest.mark.asyncio
    async def test_write_file_creates_file(self, fs_tools, temp_workspace):
        """Test that WRITE_FILE actually creates a file"""
        file_path = "test.py"
        content = "print('hello world')"

        result = await fs_tools.write_file(file_path, content)

        # Check result
        assert result.success == True, f"write_file failed: {result.error}"
        assert result.error is None

        # Check file actually exists
        full_path = os.path.join(temp_workspace, file_path)
        assert os.path.exists(full_path), f"File not created at {full_path}"

        # Check content matches
        with open(full_path, 'r') as f:
            actual_content = f.read()
        assert actual_content == content, f"Content mismatch: expected '{content}', got '{actual_content}'"

    @pytest.mark.asyncio
    async def test_write_file_with_subdirectory(self, fs_tools, temp_workspace):
        """Test that WRITE_FILE creates subdirectories"""
        file_path = "subdir/nested/test.py"
        content = "# nested file"

        result = await fs_tools.write_file(file_path, content)

        assert result.success == True
        full_path = os.path.join(temp_workspace, file_path)
        assert os.path.exists(full_path)

    @pytest.mark.asyncio
    async def test_read_file_returns_content(self, fs_tools, temp_workspace):
        """Test that READ_FILE returns correct content"""
        # Create a file first
        file_path = "read_test.txt"
        content = "This is test content\nWith multiple lines\n"
        full_path = os.path.join(temp_workspace, file_path)
        os.makedirs(os.path.dirname(full_path) if os.path.dirname(full_path) else temp_workspace, exist_ok=True)
        with open(full_path, 'w') as f:
            f.write(content)

        # Read it back
        result = await fs_tools.read_file(file_path)

        assert result.success == True
        assert result.output == content

    @pytest.mark.asyncio
    async def test_read_nonexistent_file_fails(self, fs_tools):
        """Test that reading nonexistent file fails gracefully"""
        result = await fs_tools.read_file("nonexistent.txt")

        assert result.success == False
        assert result.error is not None
        assert "not found" in result.error.lower() or "does not exist" in result.error.lower()

    @pytest.mark.asyncio
    async def test_list_directory(self, fs_tools, temp_workspace):
        """Test that LIST_DIRECTORY returns file list"""
        # Create some files
        files = ["file1.py", "file2.txt", "subdir/file3.py"]
        for file_path in files:
            full_path = os.path.join(temp_workspace, file_path)
            os.makedirs(os.path.dirname(full_path), exist_ok=True)
            with open(full_path, 'w') as f:
                f.write("test")

        result = await fs_tools.list_directory(".")

        assert result.success == True
        entries = result.output

        # Check that we can see the files
        assert any("file1.py" in str(entry) for entry in entries)
        assert any("file2.txt" in str(entry) for entry in entries)

    @pytest.mark.asyncio
    async def test_search_files_by_pattern(self, fs_tools, temp_workspace):
        """Test that SEARCH_FILES finds files by pattern"""
        # Create files with different extensions
        files = ["test.py", "data.json", "another.py", "readme.md"]
        for file_path in files:
            full_path = os.path.join(temp_workspace, file_path)
            with open(full_path, 'w') as f:
                f.write("content")

        result = await fs_tools.search_files("*.py")

        assert result.success == True
        found_files = result.output
        assert any("test.py" in f for f in found_files)
        assert any("another.py" in f for f in found_files)
        # Should not find non-py files
        assert not any("data.json" in f for f in found_files)


class TestSearchTools:
    """Test search tool operations"""

    @pytest.mark.asyncio
    async def test_grep_finds_pattern(self, search_tools, temp_workspace):
        """Test that SEARCH_CODE finds patterns"""
        # Create files with searchable content
        file1 = os.path.join(temp_workspace, "file1.py")
        file2 = os.path.join(temp_workspace, "file2.py")

        with open(file1, 'w') as f:
            f.write("def calculate_total(items):\n    return sum(items)\n")

        with open(file2, 'w') as f:
            f.write("def process_data(data):\n    return data\n")

        result = await search_tools.grep("calculate", "*.py")

        assert result.success == True
        matches = result.output
        assert "calculate_total" in str(matches)
        assert "file1.py" in str(matches)

    @pytest.mark.asyncio
    async def test_grep_no_matches_returns_empty(self, search_tools, temp_workspace):
        """Test that SEARCH_CODE with no matches returns empty result"""
        file1 = os.path.join(temp_workspace, "test.py")
        with open(file1, 'w') as f:
            f.write("print('hello')")

        result = await search_tools.grep("nonexistent_pattern", "*.py")

        # Should succeed but return empty results
        assert result.success == True
        assert len(result.output) == 0 or result.output == []


class TestProcessTools:
    """Test process execution tools"""

    @pytest.mark.asyncio
    async def test_execute_simple_command(self, process_tools):
        """Test that RUN_COMMAND executes simple commands"""
        result = await process_tools.execute_command("echo 'test'")

        assert result.success == True
        assert "test" in result.output

    @pytest.mark.asyncio
    async def test_execute_command_with_failure(self, process_tools):
        """Test that failed commands are handled"""
        result = await process_tools.execute_command("exit 1")

        assert result.success == False
        assert result.error is not None

    @pytest.mark.asyncio
    async def test_execute_python_command(self, process_tools):
        """Test executing Python code"""
        result = await process_tools.execute_command("python -c \"print(2+2)\"")

        assert result.success == True
        assert "4" in result.output


class TestToolIntegration:
    """Test complete tool workflows"""

    @pytest.mark.asyncio
    async def test_write_read_cycle(self, fs_tools):
        """Test writing then reading a file"""
        file_path = "cycle_test.py"
        original_content = "def hello():\n    print('world')\n"

        # Write
        write_result = await fs_tools.write_file(file_path, original_content)
        assert write_result.success == True

        # Read
        read_result = await fs_tools.read_file(file_path)
        assert read_result.success == True
        assert read_result.output == original_content

    @pytest.mark.asyncio
    async def test_create_file_then_search(self, fs_tools, search_tools, temp_workspace):
        """Test creating a file then searching for content"""
        # Create file with specific content
        file_path = "searchable.py"
        content = "def my_unique_function():\n    pass\n"

        write_result = await fs_tools.write_file(file_path, content)
        assert write_result.success == True

        # Search for the content
        search_result = await search_tools.grep("my_unique_function", "*.py")
        assert search_result.success == True
        assert "my_unique_function" in str(search_result.output)


# Run this test file standalone
if __name__ == "__main__":
    pytest.main([__file__, "-v", "--tb=short"])

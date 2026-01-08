"""
End-to-End Integration Tests for Agent Tools

Tests the complete tool pipeline including:
1. Tool registration and discovery
2. Tool execution with real file system operations
3. Network mode switching (online/offline)
4. Performance features (caching, pooling)
5. Multi-tool workflows

These tests use the actual file system and may take longer to run.
"""

import os
import sys
import asyncio
import pytest
import tempfile
import pathlib
from unittest.mock import patch, AsyncMock

# Add backend to path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(__file__)))))

from app.tools.registry import ToolRegistry
from app.tools.base import ToolCategory, NetworkType
from app.tools.performance import ConnectionPool, get_cache, reset_cache


# =============================================================================
# Fixtures
# =============================================================================

@pytest.fixture
def clean_registry():
    """Provide a clean ToolRegistry instance"""
    ToolRegistry._instance = None
    yield
    ToolRegistry._instance = None


@pytest.fixture
def temp_workspace(tmp_path):
    """Create a temporary workspace with test files"""
    # Create directory structure
    src_dir = tmp_path / "src"
    src_dir.mkdir()

    tests_dir = tmp_path / "tests"
    tests_dir.mkdir()

    # Create test files
    (src_dir / "main.py").write_text("""
def hello(name: str) -> str:
    return f"Hello, {name}!"

def add(a: int, b: int) -> int:
    return a + b
""")

    (src_dir / "utils.py").write_text("""
import os

def get_env(key: str, default: str = "") -> str:
    return os.getenv(key, default)
""")

    (tests_dir / "test_main.py").write_text("""
import pytest
from src.main import hello, add

def test_hello():
    assert hello("World") == "Hello, World!"

def test_add():
    assert add(2, 3) == 5
""")

    # Create a .git directory to simulate a git repo
    git_dir = tmp_path / ".git"
    git_dir.mkdir()

    return tmp_path


@pytest.fixture
def clean_pool():
    """Clean connection pool before and after tests"""
    # Run cleanup synchronously before test
    loop = asyncio.new_event_loop()
    loop.run_until_complete(ConnectionPool.reset_instance())
    yield
    # Run cleanup synchronously after test
    loop.run_until_complete(ConnectionPool.reset_instance())
    loop.close()


# =============================================================================
# Tool Registration Tests
# =============================================================================

class TestToolRegistration:
    """Test tool registration and discovery"""

    def test_all_tools_registered(self, clean_registry):
        """Test that all expected tools are registered"""
        with patch.dict(os.environ, {"NETWORK_MODE": "online"}):
            registry = ToolRegistry()
            stats = registry.get_statistics()

            # Should have 19 tools (Phase 1 + Phase 2 + Phase 2.5)
            assert stats["total_tools"] == 20
            assert stats["available_tools"] == 20

    def test_tools_by_category(self, clean_registry):
        """Test tool categorization"""
        with patch.dict(os.environ, {"NETWORK_MODE": "online"}):
            registry = ToolRegistry()

            file_tools = registry.list_tools(ToolCategory.FILE)
            code_tools = registry.list_tools(ToolCategory.CODE)
            git_tools = registry.list_tools(ToolCategory.GIT)
            web_tools = registry.list_tools(ToolCategory.WEB)
            search_tools = registry.list_tools(ToolCategory.SEARCH)

            assert len(file_tools) == 4
            assert len(code_tools) == 7  # 3 Phase 1 + 3 Phase 2.5
            assert len(git_tools) == 5
            assert len(web_tools) == 3
            assert len(search_tools) == 1

    def test_tool_schemas_valid(self, clean_registry):
        """Test that all tool schemas are valid"""
        with patch.dict(os.environ, {"NETWORK_MODE": "online"}):
            registry = ToolRegistry()

            for tool in registry.list_tools():
                schema = tool.get_schema()

                assert "name" in schema
                assert "description" in schema
                assert "parameters" in schema
                assert len(schema["name"]) > 0
                assert len(schema["description"]) > 0


# =============================================================================
# File Tools E2E Tests
# =============================================================================

class TestFileToolsE2E:
    """End-to-end tests for file tools"""

    @pytest.mark.asyncio
    async def test_read_write_file_workflow(self, temp_workspace, clean_registry):
        """Test complete read-write workflow"""
        with patch.dict(os.environ, {"NETWORK_MODE": "online"}):
            registry = ToolRegistry()

            # Get tools
            read_tool = registry.get_tool("read_file")
            write_tool = registry.get_tool("write_file")

            # Write a file
            test_file = temp_workspace / "new_file.txt"
            write_result = await write_tool.execute(
                path=str(test_file),
                content="Hello, World!"
            )
            assert write_result.success is True

            # Read the file back
            read_result = await read_tool.execute(path=str(test_file))
            assert read_result.success is True
            assert "Hello, World!" in read_result.output  # output is the content directly

    @pytest.mark.asyncio
    async def test_search_files(self, temp_workspace, clean_registry):
        """Test file search functionality"""
        with patch.dict(os.environ, {"NETWORK_MODE": "online"}):
            registry = ToolRegistry()

            search_tool = registry.get_tool("search_files")

            result = await search_tool.execute(
                pattern="*.py",
                path=str(temp_workspace)
            )

            assert result.success is True
            assert len(result.output) >= 3  # main.py, utils.py, test_main.py (output is a list)

    @pytest.mark.asyncio
    async def test_list_directory(self, temp_workspace, clean_registry):
        """Test directory listing"""
        with patch.dict(os.environ, {"NETWORK_MODE": "online"}):
            registry = ToolRegistry()

            list_tool = registry.get_tool("list_directory")

            result = await list_tool.execute(path=str(temp_workspace))

            assert result.success is True
            # Output is a list of entries with name, path, type, size
            assert isinstance(result.output, list)
            names = [entry["name"] for entry in result.output]
            assert "src" in names
            assert "tests" in names


# =============================================================================
# Code Tools E2E Tests
# =============================================================================

class TestCodeToolsE2E:
    """End-to-end tests for code tools"""

    @pytest.mark.asyncio
    async def test_execute_python(self, clean_registry):
        """Test Python code execution"""
        with patch.dict(os.environ, {"NETWORK_MODE": "online"}):
            registry = ToolRegistry()

            python_tool = registry.get_tool("execute_python")

            result = await python_tool.execute(
                code="print(2 + 2)"
            )

            assert result.success is True
            assert "4" in result.output["stdout"]

    @pytest.mark.asyncio
    async def test_docstring_generator(self, temp_workspace, clean_registry):
        """Test docstring generation"""
        with patch.dict(os.environ, {"NETWORK_MODE": "online"}):
            registry = ToolRegistry()

            docstring_tool = registry.get_tool("generate_docstring")

            result = await docstring_tool.execute(
                file_path=str(temp_workspace / "src" / "main.py"),
                style="google"
            )

            assert result.success is True
            # Should find functions without docstrings
            assert result.output["count"] >= 1

    @pytest.mark.asyncio
    async def test_shell_command_safe(self, temp_workspace, clean_registry):
        """Test safe shell command execution"""
        with patch.dict(os.environ, {"NETWORK_MODE": "online"}):
            registry = ToolRegistry()

            shell_tool = registry.get_tool("shell_command")

            # Safe command should work
            result = await shell_tool.execute(
                command="ls -la",
                working_dir=str(temp_workspace)
            )

            assert result.success is True
            assert "src" in result.output["stdout"]

    @pytest.mark.asyncio
    async def test_shell_command_blocked(self, clean_registry):
        """Test that dangerous commands are blocked"""
        with patch.dict(os.environ, {"NETWORK_MODE": "online"}):
            registry = ToolRegistry()

            shell_tool = registry.get_tool("shell_command")

            # Dangerous command should be blocked
            result = await shell_tool.execute(command="rm -rf /")

            assert result.success is False
            assert "Security check failed" in result.error


# =============================================================================
# Network Mode E2E Tests
# =============================================================================

class TestNetworkModeE2E:
    """End-to-end tests for network mode switching"""

    def test_offline_mode_blocks_external_api(self, clean_registry):
        """Test that EXTERNAL_API tools are blocked in offline mode"""
        with patch.dict(os.environ, {"NETWORK_MODE": "offline"}):
            registry = ToolRegistry()

            # These should be blocked
            http_tool = registry.get_tool("http_request")
            web_search = registry.get_tool("web_search")

            assert http_tool is None
            assert web_search is None

    def test_offline_mode_allows_download(self, clean_registry):
        """Test that EXTERNAL_DOWNLOAD tools work in offline mode"""
        with patch.dict(os.environ, {"NETWORK_MODE": "offline"}):
            registry = ToolRegistry()

            # Download should still be available
            download_tool = registry.get_tool("download_file")

            assert download_tool is not None
            assert download_tool.network_type == NetworkType.EXTERNAL_DOWNLOAD

    def test_offline_mode_allows_local(self, clean_registry):
        """Test that LOCAL tools work in offline mode"""
        with patch.dict(os.environ, {"NETWORK_MODE": "offline"}):
            registry = ToolRegistry()

            # All local tools should be available
            read_tool = registry.get_tool("read_file")
            python_tool = registry.get_tool("execute_python")
            git_tool = registry.get_tool("git_status")

            assert read_tool is not None
            assert python_tool is not None
            assert git_tool is not None

    def test_mode_statistics(self, clean_registry):
        """Test statistics in different modes"""
        # Online mode
        with patch.dict(os.environ, {"NETWORK_MODE": "online"}):
            ToolRegistry._instance = None
            registry = ToolRegistry()
            online_stats = registry.get_statistics()

        # Offline mode
        with patch.dict(os.environ, {"NETWORK_MODE": "offline"}):
            ToolRegistry._instance = None
            registry = ToolRegistry()
            offline_stats = registry.get_statistics()

        # Online should have all tools available
        assert online_stats["available_tools"] == 20
        assert online_stats["disabled_tools"] == 0

        # Offline should have 2 blocked (http_request, web_search)
        assert offline_stats["available_tools"] == 18
        assert offline_stats["disabled_tools"] == 2


# =============================================================================
# Performance Features E2E Tests
# =============================================================================

class TestPerformanceE2E:
    """End-to-end tests for performance features"""

    @pytest.mark.asyncio
    async def test_connection_pool_reuse(self, clean_registry, clean_pool):
        """Test that connection pool is reused across requests"""
        pool = await ConnectionPool.get_instance()
        initial_count = pool._request_count

        # Simulate multiple requests
        for _ in range(3):
            async with pool.get_session() as session:
                pass

        # Request count should increase
        assert pool._request_count == initial_count + 3

    @pytest.mark.asyncio
    async def test_result_cache_integration(self, clean_registry):
        """Test result cache with actual tool usage"""
        reset_cache()

        with patch.dict(os.environ, {"NETWORK_MODE": "online"}):
            registry = ToolRegistry()

            cache = get_cache()

            # Manually test cache
            cache.set("test_tool", {"param": "value"}, "test_result")

            # Should get cached result
            result = cache.get("test_tool", {"param": "value"})
            assert result == "test_result"

            # Different params should miss
            result2 = cache.get("test_tool", {"param": "other"})
            assert result2 is None

            stats = cache.get_stats()
            assert stats["hits"] == 1
            assert stats["misses"] == 1

        reset_cache()


# =============================================================================
# Multi-Tool Workflow Tests
# =============================================================================

class TestMultiToolWorkflow:
    """Test workflows using multiple tools together"""

    @pytest.mark.asyncio
    async def test_code_analysis_workflow(self, temp_workspace, clean_registry):
        """Test a complete code analysis workflow"""
        with patch.dict(os.environ, {"NETWORK_MODE": "online"}):
            registry = ToolRegistry()

            # 1. List Python files
            search_tool = registry.get_tool("search_files")
            files_result = await search_tool.execute(
                pattern="*.py",
                path=str(temp_workspace / "src")
            )
            assert files_result.success is True

            # 2. Read each file (output is a list of relative paths)
            read_tool = registry.get_tool("read_file")
            src_path = temp_workspace / "src"
            for rel_path in files_result.output:
                full_path = src_path / rel_path
                read_result = await read_tool.execute(path=str(full_path))
                assert read_result.success is True

            # 3. Generate docstrings
            docstring_tool = registry.get_tool("generate_docstring")
            for rel_path in files_result.output:
                full_path = src_path / rel_path
                doc_result = await docstring_tool.execute(
                    file_path=str(full_path),
                    style="google"
                )
                assert doc_result.success is True

    @pytest.mark.asyncio
    async def test_file_modification_workflow(self, temp_workspace, clean_registry):
        """Test file read-modify-write workflow"""
        with patch.dict(os.environ, {"NETWORK_MODE": "online"}):
            registry = ToolRegistry()

            test_file = temp_workspace / "src" / "main.py"

            # 1. Read original
            read_tool = registry.get_tool("read_file")
            original = await read_tool.execute(path=str(test_file))
            assert original.success is True

            original_content = original.output  # output is the content directly

            # 2. Modify content
            new_content = original_content + "\n\ndef goodbye():\n    return 'Goodbye!'\n"

            # 3. Write modified
            write_tool = registry.get_tool("write_file")
            write_result = await write_tool.execute(
                path=str(test_file),
                content=new_content
            )
            assert write_result.success is True

            # 4. Verify modification
            verify = await read_tool.execute(path=str(test_file))
            assert verify.success is True
            assert "goodbye" in verify.output  # output is the content directly


# =============================================================================
# Error Handling Tests
# =============================================================================

class TestErrorHandling:
    """Test error handling across tools"""

    @pytest.mark.asyncio
    async def test_file_not_found(self, clean_registry):
        """Test handling of non-existent files"""
        with patch.dict(os.environ, {"NETWORK_MODE": "online"}):
            registry = ToolRegistry()

            read_tool = registry.get_tool("read_file")
            result = await read_tool.execute(path="/nonexistent/file.txt")

            assert result.success is False
            assert result.error is not None

    @pytest.mark.asyncio
    async def test_invalid_python_code(self, clean_registry):
        """Test handling of invalid Python code"""
        with patch.dict(os.environ, {"NETWORK_MODE": "online"}):
            registry = ToolRegistry()

            python_tool = registry.get_tool("execute_python")
            result = await python_tool.execute(code="invalid python syntax !!!")

            assert result.success is False

    @pytest.mark.asyncio
    async def test_invalid_parameters(self, clean_registry):
        """Test parameter validation"""
        with patch.dict(os.environ, {"NETWORK_MODE": "online"}):
            registry = ToolRegistry()

            # Test with empty path parameter
            read_tool = registry.get_tool("read_file")
            is_valid = read_tool.validate_params(path="")

            assert is_valid is False

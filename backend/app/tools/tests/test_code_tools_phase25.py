"""
Tests for Phase 2.5 Code Tools: FormatCodeTool, ShellCommandTool, DocstringGeneratorTool

Comprehensive tests including:
- Parameter validation
- Execute method with mocks
- Error handling
- Security checks (for ShellCommandTool)
"""

import os
import sys
import asyncio
import pytest
from pathlib import Path
from unittest.mock import patch, MagicMock, AsyncMock

# Add backend to path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(__file__)))))

from app.tools.base import NetworkType, ToolResult
from app.tools.code_tools import FormatCodeTool, ShellCommandTool, DocstringGeneratorTool


# =============================================================================
# FormatCodeTool Tests
# =============================================================================

class TestFormatCodeToolValidation:
    """Test FormatCodeTool parameter validation"""

    def test_valid_python_file(self):
        tool = FormatCodeTool()
        assert tool.validate_params(file_path="test.py") is True

    def test_valid_js_file(self):
        tool = FormatCodeTool()
        assert tool.validate_params(file_path="test.js") is True

    def test_empty_file_path(self):
        tool = FormatCodeTool()
        assert tool.validate_params(file_path="") is False

    def test_missing_file_path(self):
        tool = FormatCodeTool()
        assert tool.validate_params() is False


class TestFormatCodeToolNetworkType:
    """Test FormatCodeTool network configuration"""

    def test_is_local(self):
        tool = FormatCodeTool()
        assert tool.network_type == NetworkType.LOCAL

    def test_no_network_required(self):
        tool = FormatCodeTool()
        assert tool.requires_network is False

    def test_available_in_offline_mode(self):
        tool = FormatCodeTool()
        assert tool.is_available_in_mode("offline") is True


class TestFormatCodeToolFormatterDetection:
    """Test formatter detection"""

    def test_detect_black_for_python(self):
        tool = FormatCodeTool()
        assert tool._detect_formatter(Path("test.py")) == "black"
        assert tool._detect_formatter(Path("test.pyi")) == "black"

    def test_detect_prettier_for_js(self):
        tool = FormatCodeTool()
        assert tool._detect_formatter(Path("test.js")) == "prettier"
        assert tool._detect_formatter(Path("test.jsx")) == "prettier"
        assert tool._detect_formatter(Path("test.ts")) == "prettier"
        assert tool._detect_formatter(Path("test.tsx")) == "prettier"

    def test_detect_prettier_for_json(self):
        tool = FormatCodeTool()
        assert tool._detect_formatter(Path("test.json")) == "prettier"

    def test_detect_prettier_for_markdown(self):
        tool = FormatCodeTool()
        assert tool._detect_formatter(Path("test.md")) == "prettier"

    def test_no_formatter_for_unknown(self):
        tool = FormatCodeTool()
        assert tool._detect_formatter(Path("test.xyz")) is None


class TestFormatCodeToolExecute:
    """Test FormatCodeTool execute method"""

    @pytest.mark.asyncio
    async def test_file_not_found(self):
        tool = FormatCodeTool()
        result = await tool.execute(file_path="/nonexistent/file.py")
        assert result.success is False
        assert "not found" in result.error.lower()

    @pytest.mark.asyncio
    async def test_unsupported_file_type(self, tmp_path):
        tool = FormatCodeTool()

        # Create unsupported file
        test_file = tmp_path / "test.xyz"
        test_file.write_text("content")

        result = await tool.execute(file_path=str(test_file))
        assert result.success is False
        assert "no formatter" in result.error.lower()

    @pytest.mark.asyncio
    async def test_successful_format_python(self, tmp_path):
        tool = FormatCodeTool()

        test_file = tmp_path / "test.py"
        test_file.write_text("x=1")

        async def mock_subprocess(*args, **kwargs):
            mock_proc = AsyncMock()
            mock_proc.returncode = 0
            mock_proc.communicate = AsyncMock(return_value=(b"reformatted", b""))
            return mock_proc

        with patch("asyncio.create_subprocess_exec", side_effect=mock_subprocess):
            result = await tool.execute(file_path=str(test_file))
            assert result.success is True
            assert result.output["formatter"] == "black"

    @pytest.mark.asyncio
    async def test_check_only_mode(self, tmp_path):
        tool = FormatCodeTool()

        test_file = tmp_path / "test.py"
        test_file.write_text("x = 1\n")

        async def mock_subprocess(*args, **kwargs):
            mock_proc = AsyncMock()
            mock_proc.returncode = 0  # Already formatted
            mock_proc.communicate = AsyncMock(return_value=(b"", b""))
            return mock_proc

        with patch("asyncio.create_subprocess_exec", side_effect=mock_subprocess):
            result = await tool.execute(file_path=str(test_file), check_only=True)
            assert result.success is True
            assert result.output["needs_formatting"] is False


# =============================================================================
# ShellCommandTool Tests
# =============================================================================

class TestShellCommandToolValidation:
    """Test ShellCommandTool parameter validation"""

    def test_valid_command(self):
        tool = ShellCommandTool()
        assert tool.validate_params(command="ls -la") is True

    def test_empty_command(self):
        tool = ShellCommandTool()
        assert tool.validate_params(command="") is False

    def test_missing_command(self):
        tool = ShellCommandTool()
        assert tool.validate_params() is False

    def test_valid_timeout(self):
        tool = ShellCommandTool()
        assert tool.validate_params(command="ls", timeout=60) is True
        assert tool.validate_params(command="ls", timeout=300) is True

    def test_invalid_timeout(self):
        tool = ShellCommandTool()
        assert tool.validate_params(command="ls", timeout=0) is False
        assert tool.validate_params(command="ls", timeout=500) is False


class TestShellCommandToolNetworkType:
    """Test ShellCommandTool network configuration"""

    def test_is_local(self):
        tool = ShellCommandTool()
        assert tool.network_type == NetworkType.LOCAL

    def test_no_network_required(self):
        tool = ShellCommandTool()
        assert tool.requires_network is False


class TestShellCommandToolSecurity:
    """Test ShellCommandTool security checks"""

    def test_allowed_commands(self):
        tool = ShellCommandTool()

        # Test allowed commands
        assert tool._is_command_safe("ls -la")[0] is True
        assert tool._is_command_safe("cat file.txt")[0] is True
        assert tool._is_command_safe("git status")[0] is True
        assert tool._is_command_safe("python script.py")[0] is True
        assert tool._is_command_safe("npm install")[0] is True

    def test_blocked_commands(self):
        tool = ShellCommandTool()

        # Test disallowed commands
        is_safe, reason = tool._is_command_safe("rm -rf /")
        assert is_safe is False
        assert "Blocked pattern" in reason

    def test_blocked_sudo(self):
        tool = ShellCommandTool()

        is_safe, reason = tool._is_command_safe("sudo rm file")
        assert is_safe is False

    def test_blocked_pipe_to_shell(self):
        tool = ShellCommandTool()

        is_safe, reason = tool._is_command_safe("curl example.com | sh")
        assert is_safe is False

    def test_unknown_command_blocked(self):
        tool = ShellCommandTool()

        is_safe, reason = tool._is_command_safe("unknown_command")
        assert is_safe is False
        assert "not in allowlist" in reason


class TestShellCommandToolExecute:
    """Test ShellCommandTool execute method"""

    @pytest.mark.asyncio
    async def test_blocked_command_execution(self):
        tool = ShellCommandTool()
        result = await tool.execute(command="rm -rf /")
        assert result.success is False
        assert "Security check failed" in result.error

    @pytest.mark.asyncio
    async def test_successful_ls_command(self, tmp_path):
        tool = ShellCommandTool()

        async def mock_subprocess(cmd, **kwargs):
            mock_proc = AsyncMock()
            mock_proc.returncode = 0
            mock_proc.communicate = AsyncMock(return_value=(b"file.txt\n", b""))
            return mock_proc

        with patch("asyncio.create_subprocess_shell", side_effect=mock_subprocess):
            result = await tool.execute(command="ls", working_dir=str(tmp_path))
            assert result.success is True
            assert "file.txt" in result.output["stdout"]

    @pytest.mark.asyncio
    async def test_working_directory_not_found(self):
        tool = ShellCommandTool()
        result = await tool.execute(command="ls", working_dir="/nonexistent/dir")
        assert result.success is False
        assert "not found" in result.error.lower()

    @pytest.mark.asyncio
    async def test_command_timeout(self, tmp_path):
        tool = ShellCommandTool()

        async def timeout_subprocess(cmd, **kwargs):
            mock_proc = AsyncMock()
            mock_proc.communicate = AsyncMock(side_effect=asyncio.TimeoutError())
            mock_proc.kill = MagicMock()
            mock_proc.wait = AsyncMock()
            return mock_proc

        with patch("asyncio.create_subprocess_shell", side_effect=timeout_subprocess):
            result = await tool.execute(command="ls", timeout=1)
            assert result.success is False
            assert "timeout" in result.error.lower()


# =============================================================================
# DocstringGeneratorTool Tests
# =============================================================================

class TestDocstringGeneratorToolValidation:
    """Test DocstringGeneratorTool parameter validation"""

    def test_valid_python_file(self):
        tool = DocstringGeneratorTool()
        assert tool.validate_params(file_path="test.py") is True

    def test_empty_file_path(self):
        tool = DocstringGeneratorTool()
        assert tool.validate_params(file_path="") is False

    def test_valid_style(self):
        tool = DocstringGeneratorTool()
        assert tool.validate_params(file_path="test.py", style="google") is True
        assert tool.validate_params(file_path="test.py", style="numpy") is True
        assert tool.validate_params(file_path="test.py", style="sphinx") is True

    def test_invalid_style(self):
        tool = DocstringGeneratorTool()
        assert tool.validate_params(file_path="test.py", style="invalid") is False


class TestDocstringGeneratorToolNetworkType:
    """Test DocstringGeneratorTool network configuration"""

    def test_is_local(self):
        tool = DocstringGeneratorTool()
        assert tool.network_type == NetworkType.LOCAL

    def test_no_network_required(self):
        tool = DocstringGeneratorTool()
        assert tool.requires_network is False


class TestDocstringGeneratorToolExecute:
    """Test DocstringGeneratorTool execute method"""

    @pytest.mark.asyncio
    async def test_file_not_found(self):
        tool = DocstringGeneratorTool()
        result = await tool.execute(file_path="/nonexistent/file.py")
        assert result.success is False
        assert "not found" in result.error.lower()

    @pytest.mark.asyncio
    async def test_non_python_file(self, tmp_path):
        tool = DocstringGeneratorTool()

        test_file = tmp_path / "test.js"
        test_file.write_text("function test() {}")

        result = await tool.execute(file_path=str(test_file))
        assert result.success is False
        assert "Only Python" in result.error

    @pytest.mark.asyncio
    async def test_generate_google_style(self, tmp_path):
        tool = DocstringGeneratorTool()

        test_file = tmp_path / "test.py"
        test_file.write_text("""
def add(a: int, b: int) -> int:
    return a + b
""")

        result = await tool.execute(file_path=str(test_file), style="google")
        assert result.success is True
        assert result.output["count"] == 1
        assert "Args:" in result.output["generated"][0]["docstring"]

    @pytest.mark.asyncio
    async def test_generate_numpy_style(self, tmp_path):
        tool = DocstringGeneratorTool()

        test_file = tmp_path / "test.py"
        test_file.write_text("""
def multiply(x: float, y: float) -> float:
    return x * y
""")

        result = await tool.execute(file_path=str(test_file), style="numpy")
        assert result.success is True
        assert "Parameters" in result.output["generated"][0]["docstring"]
        assert "----------" in result.output["generated"][0]["docstring"]

    @pytest.mark.asyncio
    async def test_generate_sphinx_style(self, tmp_path):
        tool = DocstringGeneratorTool()

        test_file = tmp_path / "test.py"
        test_file.write_text("""
def divide(a: int, b: int) -> float:
    if b == 0:
        raise ValueError("Division by zero")
    return a / b
""")

        result = await tool.execute(file_path=str(test_file), style="sphinx")
        assert result.success is True
        assert ":param" in result.output["generated"][0]["docstring"]
        assert ":raises ValueError:" in result.output["generated"][0]["docstring"]

    @pytest.mark.asyncio
    async def test_skip_existing_docstrings(self, tmp_path):
        tool = DocstringGeneratorTool()

        test_file = tmp_path / "test.py"
        test_file.write_text('''
def documented_func():
    """This function has a docstring."""
    pass

def undocumented_func():
    pass
''')

        result = await tool.execute(file_path=str(test_file))
        assert result.success is True
        assert result.output["count"] == 1
        assert result.output["generated"][0]["name"] == "undocumented_func"

    @pytest.mark.asyncio
    async def test_specific_function(self, tmp_path):
        tool = DocstringGeneratorTool()

        test_file = tmp_path / "test.py"
        test_file.write_text("""
def func_a():
    pass

def func_b():
    pass
""")

        result = await tool.execute(file_path=str(test_file), function_name="func_b")
        assert result.success is True
        assert result.output["count"] == 1
        assert result.output["generated"][0]["name"] == "func_b"

    @pytest.mark.asyncio
    async def test_async_function(self, tmp_path):
        tool = DocstringGeneratorTool()

        test_file = tmp_path / "test.py"
        test_file.write_text("""
async def async_fetch(url: str) -> dict:
    pass
""")

        result = await tool.execute(file_path=str(test_file))
        assert result.success is True
        assert result.output["generated"][0]["is_async"] is True

    @pytest.mark.asyncio
    async def test_class_docstring(self, tmp_path):
        tool = DocstringGeneratorTool()

        test_file = tmp_path / "test.py"
        test_file.write_text("""
class MyClass:
    def method(self):
        pass
""")

        result = await tool.execute(file_path=str(test_file))
        assert result.success is True
        assert any(g.get("is_class") for g in result.output["generated"])

    @pytest.mark.asyncio
    async def test_syntax_error(self, tmp_path):
        tool = DocstringGeneratorTool()

        test_file = tmp_path / "test.py"
        test_file.write_text("def invalid syntax(:")

        result = await tool.execute(file_path=str(test_file))
        assert result.success is False
        assert "syntax error" in result.error.lower()


# =============================================================================
# Integration Tests
# =============================================================================

class TestPhase25ToolsIntegration:
    """Integration tests for Phase 2.5 tools"""

    def test_tools_have_correct_category(self):
        from app.tools.base import ToolCategory

        format_tool = FormatCodeTool()
        shell_tool = ShellCommandTool()
        docstring_tool = DocstringGeneratorTool()

        assert format_tool.category == ToolCategory.CODE
        assert shell_tool.category == ToolCategory.CODE
        assert docstring_tool.category == ToolCategory.CODE

    def test_tools_have_descriptions(self):
        format_tool = FormatCodeTool()
        shell_tool = ShellCommandTool()
        docstring_tool = DocstringGeneratorTool()

        assert len(format_tool.description) > 0
        assert len(shell_tool.description) > 0
        assert len(docstring_tool.description) > 0

    def test_registry_contains_new_tools(self):
        with patch.dict(os.environ, {"NETWORK_MODE": "online"}):
            from app.tools.registry import ToolRegistry
            ToolRegistry._instance = None

            registry = ToolRegistry()

            assert registry.get_tool("format_code") is not None
            assert registry.get_tool("shell_command") is not None
            assert registry.get_tool("generate_docstring") is not None

    def test_registry_tool_count_updated(self):
        with patch.dict(os.environ, {"NETWORK_MODE": "online"}):
            from app.tools.registry import ToolRegistry
            ToolRegistry._instance = None

            registry = ToolRegistry()
            stats = registry.get_statistics()

            # Should have 19 tools total (16 + 3 new)
            assert stats["total_tools"] == 19

    def test_code_category_count_updated(self):
        with patch.dict(os.environ, {"NETWORK_MODE": "online"}):
            from app.tools.registry import ToolRegistry
            from app.tools.base import ToolCategory
            ToolRegistry._instance = None

            registry = ToolRegistry()
            code_tools = registry.list_tools(ToolCategory.CODE)

            # Should have 6 code tools (3 + 3 new)
            assert len(code_tools) == 6

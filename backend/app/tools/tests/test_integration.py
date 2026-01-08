"""
Integration tests for Agent Tools

Tests the integration of tools with ToolRegistry
LangChain adapter tests are skipped if dependencies are not available

Updated for Phase 2.5: 19 tools total (14 Phase 1 + 2 Phase 2 + 3 Phase 2.5)
"""

import pytest
import os
from unittest.mock import patch
from app.tools.registry import ToolRegistry
from app.tools.base import ToolCategory

# Try to import LangChain - skip those tests if not available
try:
    from app.agent.langchain.tool_adapter import LangChainToolRegistry
    LANGCHAIN_AVAILABLE = True
except ImportError:
    LANGCHAIN_AVAILABLE = False


class TestToolRegistryIntegration:
    """Test Tool Registry integration with all tools"""

    def setup_method(self):
        """Reset registry before each test"""
        ToolRegistry._instance = None

    def test_registry_has_phase1_tools(self):
        """Test that registry contains all Phase 1 tools"""
        with patch.dict(os.environ, {"NETWORK_MODE": "online"}):
            ToolRegistry._instance = None
            registry = ToolRegistry()

            # Check Phase 1 new tools are registered
            assert registry.get_tool("web_search") is not None
            assert registry.get_tool("code_search") is not None
            assert registry.get_tool("git_commit") is not None

    def test_registry_has_phase2_tools(self):
        """Test that registry contains all Phase 2 tools"""
        with patch.dict(os.environ, {"NETWORK_MODE": "online"}):
            ToolRegistry._instance = None
            registry = ToolRegistry()

            # Check Phase 2 new tools are registered
            assert registry.get_tool("http_request") is not None
            assert registry.get_tool("download_file") is not None

    def test_registry_tool_count(self):
        """Test that registry has correct total tool count"""
        with patch.dict(os.environ, {"NETWORK_MODE": "online"}):
            ToolRegistry._instance = None
            registry = ToolRegistry()
            stats = registry.get_statistics()

            # Should have 19 tools total (14 Phase 1 + 2 Phase 2 + 3 Phase 2.5)
            assert stats["total_tools"] == 20

    def test_registry_categories(self):
        """Test that all tool categories are properly registered"""
        with patch.dict(os.environ, {"NETWORK_MODE": "online"}):
            ToolRegistry._instance = None
            registry = ToolRegistry()
            stats = registry.get_statistics()

            # Check WEB category (now has 3 tools: web_search, http_request, download_file)
            assert "web" in stats["by_category"]
            assert stats["by_category"]["web"] == 3

            # Check SEARCH category (has 1 tool)
            assert "search" in stats["by_category"]
            assert stats["by_category"]["search"] == 1

            # Check GIT category (has 5 tools)
            assert "git" in stats["by_category"]
            assert stats["by_category"]["git"] == 5

            # Check FILE category (has 4 tools)
            assert "file" in stats["by_category"]
            assert stats["by_category"]["file"] == 4

            # Check CODE category (has 6 tools: 3 Phase 1 + 3 Phase 2.5)
            assert "code" in stats["by_category"]
            assert stats["by_category"]["code"] == 7

    def test_get_web_tools(self):
        """Test retrieval of web category tools"""
        with patch.dict(os.environ, {"NETWORK_MODE": "online"}):
            ToolRegistry._instance = None
            registry = ToolRegistry()
            web_tools = registry.list_tools(ToolCategory.WEB)

            # Phase 2: Now has 3 tools
            assert len(web_tools) == 3
            web_tool_names = [t.name for t in web_tools]
            assert "web_search" in web_tool_names
            assert "http_request" in web_tool_names
            assert "download_file" in web_tool_names

    def test_get_search_tools(self):
        """Test retrieval of search category tools"""
        with patch.dict(os.environ, {"NETWORK_MODE": "online"}):
            ToolRegistry._instance = None
            registry = ToolRegistry()
            search_tools = registry.list_tools(ToolCategory.SEARCH)

            assert len(search_tools) == 1
            assert search_tools[0].name == "code_search"

    def test_get_git_tools(self):
        """Test retrieval of git category tools"""
        with patch.dict(os.environ, {"NETWORK_MODE": "online"}):
            ToolRegistry._instance = None
            registry = ToolRegistry()
            git_tools = registry.list_tools(ToolCategory.GIT)

            # Should have 5 git tools
            assert len(git_tools) == 5

            git_tool_names = [t.name for t in git_tools]
            assert "git_commit" in git_tool_names
            assert "git_status" in git_tool_names
            assert "git_diff" in git_tool_names
            assert "git_log" in git_tool_names
            assert "git_branch" in git_tool_names

    def test_tool_schemas(self):
        """Test that all tools provide valid schemas"""
        with patch.dict(os.environ, {"NETWORK_MODE": "online"}):
            ToolRegistry._instance = None
            registry = ToolRegistry()

            # WebSearchTool schema
            web_tool = registry.get_tool("web_search")
            web_schema = web_tool.get_schema()
            assert web_schema["name"] == "web_search"
            assert "parameters" in web_schema
            assert "query" in web_schema["parameters"]

            # CodeSearchTool schema
            code_tool = registry.get_tool("code_search")
            code_schema = code_tool.get_schema()
            assert code_schema["name"] == "code_search"
            assert "parameters" in code_schema
            assert "query" in code_schema["parameters"]

            # GitCommitTool schema
            git_tool = registry.get_tool("git_commit")
            git_schema = git_tool.get_schema()
            assert git_schema["name"] == "git_commit"
            assert "parameters" in git_schema
            assert "message" in git_schema["parameters"]

            # HttpRequestTool schema (Phase 2)
            http_tool = registry.get_tool("http_request")
            http_schema = http_tool.get_schema()
            assert http_schema["name"] == "http_request"
            assert "url" in http_schema["parameters"]

            # DownloadFileTool schema (Phase 2)
            download_tool = registry.get_tool("download_file")
            download_schema = download_tool.get_schema()
            assert download_schema["name"] == "download_file"
            assert "url" in download_schema["parameters"]
            assert "output_path" in download_schema["parameters"]


@pytest.mark.skipif(not LANGCHAIN_AVAILABLE, reason="LangChain not installed")
class TestLangChainAdapterIntegration:
    """Test LangChain adapter integration with all tools"""

    def test_adapter_provides_all_tools(self):
        """Test that LangChain adapter can access all tools"""
        lc_registry = LangChainToolRegistry(session_id="test")

        # Get all tools
        all_tools = lc_registry.get_all_tools()
        tool_names = [t.name for t in all_tools]

        # Check Phase 1 tools
        assert "web_search" in tool_names
        assert "code_search" in tool_names
        assert "git_commit" in tool_names

        # Check Phase 2 tools
        assert "http_request" in tool_names
        assert "download_file" in tool_names

    def test_adapter_tool_count(self):
        """Test that adapter provides all 19 tools"""
        lc_registry = LangChainToolRegistry(session_id="test")
        all_tools = lc_registry.get_all_tools()

        # Should have 19 tools total (Phase 1 + Phase 2 + Phase 2.5)
        assert len(all_tools) == 20

    def test_adapter_web_category(self):
        """Test adapter can filter by WEB category"""
        lc_registry = LangChainToolRegistry(session_id="test")
        web_tools = lc_registry.get_tools_by_category("web")

        # Phase 2: Now has 3 tools
        assert len(web_tools) == 3

    def test_adapter_tool_wrapping(self):
        """Test that adapter properly wraps native tools"""
        lc_registry = LangChainToolRegistry(session_id="test")

        # Get specific tools
        web_tool = lc_registry.get_tool("web_search")
        http_tool = lc_registry.get_tool("http_request")
        download_tool = lc_registry.get_tool("download_file")

        # All should be wrapped LangChain tools
        assert web_tool is not None
        assert http_tool is not None
        assert download_tool is not None

        # Check they have LangChain BaseTool interface
        assert hasattr(web_tool, '_run')
        assert hasattr(web_tool, '_arun')


class TestBackwardCompatibility:
    """Test backward compatibility with existing tools"""

    def setup_method(self):
        """Reset registry before each test"""
        ToolRegistry._instance = None

    def test_existing_file_tools_unchanged(self):
        """Test that existing file tools still work"""
        with patch.dict(os.environ, {"NETWORK_MODE": "online"}):
            ToolRegistry._instance = None
            registry = ToolRegistry()

            # All original file tools should exist
            assert registry.get_tool("read_file") is not None
            assert registry.get_tool("write_file") is not None
            assert registry.get_tool("search_files") is not None
            assert registry.get_tool("list_directory") is not None

    def test_existing_code_tools_unchanged(self):
        """Test that existing code tools still work"""
        with patch.dict(os.environ, {"NETWORK_MODE": "online"}):
            ToolRegistry._instance = None
            registry = ToolRegistry()

            # All original code tools should exist
            assert registry.get_tool("execute_python") is not None
            assert registry.get_tool("run_tests") is not None
            assert registry.get_tool("lint_code") is not None

    def test_existing_git_tools_unchanged(self):
        """Test that existing git tools still work"""
        with patch.dict(os.environ, {"NETWORK_MODE": "online"}):
            ToolRegistry._instance = None
            registry = ToolRegistry()

            # All original git tools should exist
            assert registry.get_tool("git_status") is not None
            assert registry.get_tool("git_diff") is not None
            assert registry.get_tool("git_log") is not None
            assert registry.get_tool("git_branch") is not None

    def test_file_category_count(self):
        """Test that FILE category still has 4 tools"""
        with patch.dict(os.environ, {"NETWORK_MODE": "online"}):
            ToolRegistry._instance = None
            registry = ToolRegistry()
            file_tools = registry.list_tools(ToolCategory.FILE)

            assert len(file_tools) == 4

    def test_code_category_count(self):
        """Test that CODE category has 6 tools (3 Phase 1 + 3 Phase 2.5)"""
        with patch.dict(os.environ, {"NETWORK_MODE": "online"}):
            ToolRegistry._instance = None
            registry = ToolRegistry()
            code_tools = registry.list_tools(ToolCategory.CODE)

            # Phase 2.5 added: FormatCodeTool, ShellCommandTool, DocstringGeneratorTool
            assert len(code_tools) == 7


class TestNetworkModeIntegration:
    """Test Network Mode integration with registry"""

    def setup_method(self):
        """Reset registry before each test"""
        ToolRegistry._instance = None

    def test_offline_mode_blocks_external_api(self):
        """Test that offline mode blocks EXTERNAL_API tools"""
        with patch.dict(os.environ, {"NETWORK_MODE": "offline"}):
            ToolRegistry._instance = None
            registry = ToolRegistry()

            # EXTERNAL_API tools should be blocked
            assert registry.get_tool("web_search") is None
            assert registry.get_tool("http_request") is None

    def test_offline_mode_allows_download(self):
        """Test that offline mode allows EXTERNAL_DOWNLOAD tools"""
        with patch.dict(os.environ, {"NETWORK_MODE": "offline"}):
            ToolRegistry._instance = None
            registry = ToolRegistry()

            # EXTERNAL_DOWNLOAD should be allowed
            assert registry.get_tool("download_file") is not None

    def test_offline_mode_allows_local(self):
        """Test that offline mode allows LOCAL tools"""
        with patch.dict(os.environ, {"NETWORK_MODE": "offline"}):
            ToolRegistry._instance = None
            registry = ToolRegistry()

            # LOCAL tools should be allowed
            assert registry.get_tool("read_file") is not None
            assert registry.get_tool("git_status") is not None
            assert registry.get_tool("code_search") is not None

    def test_offline_mode_statistics(self):
        """Test statistics in offline mode"""
        with patch.dict(os.environ, {"NETWORK_MODE": "offline"}):
            ToolRegistry._instance = None
            registry = ToolRegistry()
            stats = registry.get_statistics()

            # 19 total, 2 disabled (web_search, http_request)
            assert stats["total_tools"] == 20
            assert stats["disabled_tools"] == 2
            assert stats["available_tools"] == 18

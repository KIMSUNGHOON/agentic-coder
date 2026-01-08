"""
Integration tests for Agent Tools Phase 1

Tests the integration of new tools with ToolRegistry and LangChainToolAdapter
"""

import pytest
from app.tools.registry import ToolRegistry, get_registry
from app.tools.base import ToolCategory
from app.agent.langchain.tool_adapter import LangChainToolRegistry


class TestToolRegistryIntegration:
    """Test Tool Registry integration with Phase 1 tools"""

    def test_registry_has_new_tools(self):
        """Test that registry contains all new Phase 1 tools"""
        registry = get_registry()

        # Check new tools are registered
        assert registry.get_tool("web_search") is not None
        assert registry.get_tool("code_search") is not None
        assert registry.get_tool("git_commit") is not None

    def test_registry_tool_count(self):
        """Test that registry has correct total tool count"""
        registry = get_registry()
        stats = registry.get_statistics()

        # Should have 14 tools total (11 original + 3 new)
        assert stats["total_tools"] == 14

    def test_registry_categories(self):
        """Test that new tool categories are properly registered"""
        registry = get_registry()
        stats = registry.get_statistics()

        # Check WEB category (was empty, now has 1 tool)
        assert "web" in stats["by_category"]
        assert stats["by_category"]["web"] == 1

        # Check SEARCH category (was empty, now has 1 tool)
        assert "search" in stats["by_category"]
        assert stats["by_category"]["search"] == 1

        # Check GIT category (was 4, now has 5 tools)
        assert "git" in stats["by_category"]
        assert stats["by_category"]["git"] == 5

    def test_get_web_tools(self):
        """Test retrieval of web category tools"""
        registry = get_registry()
        web_tools = registry.list_tools(ToolCategory.WEB)

        assert len(web_tools) == 1
        assert web_tools[0].name == "web_search"

    def test_get_search_tools(self):
        """Test retrieval of search category tools"""
        registry = get_registry()
        search_tools = registry.list_tools(ToolCategory.SEARCH)

        assert len(search_tools) == 1
        assert search_tools[0].name == "code_search"

    def test_get_git_tools(self):
        """Test retrieval of git category tools"""
        registry = get_registry()
        git_tools = registry.list_tools(ToolCategory.GIT)

        # Should have 5 git tools now (status, diff, log, branch, commit)
        assert len(git_tools) == 5

        git_tool_names = [t.name for t in git_tools]
        assert "git_commit" in git_tool_names
        assert "git_status" in git_tool_names
        assert "git_diff" in git_tool_names
        assert "git_log" in git_tool_names
        assert "git_branch" in git_tool_names

    def test_tool_schemas(self):
        """Test that new tools provide valid schemas"""
        registry = get_registry()

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


class TestLangChainAdapterIntegration:
    """Test LangChain adapter integration with Phase 1 tools"""

    def test_adapter_provides_new_tools(self):
        """Test that LangChain adapter can access new tools"""
        lc_registry = LangChainToolRegistry(session_id="test")

        # Get all tools
        all_tools = lc_registry.get_all_tools()
        tool_names = [t.name for t in all_tools]

        # Check new tools are available
        assert "web_search" in tool_names
        assert "code_search" in tool_names
        assert "git_commit" in tool_names

    def test_adapter_tool_count(self):
        """Test that adapter provides all 14 tools"""
        lc_registry = LangChainToolRegistry(session_id="test")
        all_tools = lc_registry.get_all_tools()

        # Should have 14 tools total
        assert len(all_tools) == 14

    def test_adapter_web_category(self):
        """Test adapter can filter by WEB category"""
        lc_registry = LangChainToolRegistry(session_id="test")
        web_tools = lc_registry.get_tools_by_category("web")

        assert len(web_tools) == 1
        assert web_tools[0].name == "web_search"

    def test_adapter_search_category(self):
        """Test adapter can filter by SEARCH category"""
        lc_registry = LangChainToolRegistry(session_id="test")
        search_tools = lc_registry.get_tools_by_category("search")

        assert len(search_tools) == 1
        assert search_tools[0].name == "code_search"

    def test_adapter_git_category(self):
        """Test adapter can filter by GIT category"""
        lc_registry = LangChainToolRegistry(session_id="test")
        git_tools = lc_registry.get_tools_by_category("git")

        # Should have 5 git tools
        assert len(git_tools) == 5

        git_tool_names = [t.name for t in git_tools]
        assert "git_commit" in git_tool_names

    def test_adapter_tool_wrapping(self):
        """Test that adapter properly wraps native tools"""
        lc_registry = LangChainToolRegistry(session_id="test")

        # Get specific tools
        web_tool = lc_registry.get_tool("web_search")
        code_tool = lc_registry.get_tool("code_search")
        git_tool = lc_registry.get_tool("git_commit")

        # All should be wrapped LangChain tools
        assert web_tool is not None
        assert code_tool is not None
        assert git_tool is not None

        # Check they have LangChain BaseTool interface
        assert hasattr(web_tool, '_run')
        assert hasattr(web_tool, '_arun')
        assert hasattr(code_tool, '_run')
        assert hasattr(code_tool, '_arun')
        assert hasattr(git_tool, '_run')
        assert hasattr(git_tool, '_arun')


class TestBackwardCompatibility:
    """Test backward compatibility with existing tools"""

    def test_existing_file_tools_unchanged(self):
        """Test that existing file tools still work"""
        registry = get_registry()

        # All original file tools should exist
        assert registry.get_tool("read_file") is not None
        assert registry.get_tool("write_file") is not None
        assert registry.get_tool("search_files") is not None
        assert registry.get_tool("list_directory") is not None

    def test_existing_code_tools_unchanged(self):
        """Test that existing code tools still work"""
        registry = get_registry()

        # All original code tools should exist
        assert registry.get_tool("execute_python") is not None
        assert registry.get_tool("run_tests") is not None
        assert registry.get_tool("lint_code") is not None

    def test_existing_git_tools_unchanged(self):
        """Test that existing git tools still work"""
        registry = get_registry()

        # All original git tools should exist
        assert registry.get_tool("git_status") is not None
        assert registry.get_tool("git_diff") is not None
        assert registry.get_tool("git_log") is not None
        assert registry.get_tool("git_branch") is not None

    def test_file_category_count(self):
        """Test that FILE category still has 4 tools"""
        registry = get_registry()
        file_tools = registry.list_tools(ToolCategory.FILE)

        assert len(file_tools) == 4

    def test_code_category_count(self):
        """Test that CODE category still has 3 tools"""
        registry = get_registry()
        code_tools = registry.list_tools(ToolCategory.CODE)

        assert len(code_tools) == 3

    def test_langchain_adapter_backward_compat(self):
        """Test that LangChain adapter still provides all original tools"""
        lc_registry = LangChainToolRegistry(session_id="test")

        # Original tool categories
        file_tools = lc_registry.get_tools_by_category("file")
        code_tools = lc_registry.get_tools_by_category("code")

        assert len(file_tools) == 4
        assert len(code_tools) == 3

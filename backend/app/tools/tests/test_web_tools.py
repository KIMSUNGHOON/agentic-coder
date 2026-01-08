"""
Unit tests for WebSearchTool
"""

import pytest
import os
from unittest.mock import Mock, patch
from app.tools.web_tools import WebSearchTool
from app.tools.base import ToolResult


class TestWebSearchTool:
    """Test cases for WebSearchTool"""

    def test_init(self):
        """Test tool initialization"""
        tool = WebSearchTool(api_key="test_key")
        assert tool.name == "web_search"
        assert tool.api_key == "test_key"
        assert "query" in tool.parameters

    def test_init_from_env(self):
        """Test initialization from environment variable"""
        with patch.dict(os.environ, {"TAVILY_API_KEY": "env_key"}):
            tool = WebSearchTool()
            assert tool.api_key == "env_key"

    def test_validate_params_valid(self):
        """Test parameter validation with valid params"""
        tool = WebSearchTool(api_key="test_key")

        # Valid params
        assert tool.validate_params(query="test query") is True
        assert tool.validate_params(query="test", max_results=5) is True
        assert tool.validate_params(query="test", search_depth="basic") is True

    def test_validate_params_invalid(self):
        """Test parameter validation with invalid params"""
        tool = WebSearchTool(api_key="test_key")

        # Missing query
        assert tool.validate_params() is False
        assert tool.validate_params(query="") is False

        # Invalid max_results
        assert tool.validate_params(query="test", max_results=0) is False
        assert tool.validate_params(query="test", max_results=25) is False

        # Invalid search_depth
        assert tool.validate_params(query="test", search_depth="invalid") is False

    @pytest.mark.asyncio
    async def test_execute_missing_api_key(self):
        """Test execution without API key"""
        tool = WebSearchTool(api_key=None)
        result = await tool.execute(query="test")

        assert result.success is False
        assert "API key not found" in result.error

    @pytest.mark.asyncio
    async def test_execute_with_mock(self):
        """Test execution with mocked Tavily client"""
        tool = WebSearchTool(api_key="test_key")

        # Mock Tavily search results
        mock_results = {
            "results": [
                {
                    "title": "Test Result 1",
                    "url": "https://example.com/1",
                    "content": "Test content 1",
                    "score": 0.95
                },
                {
                    "title": "Test Result 2",
                    "url": "https://example.com/2",
                    "content": "Test content 2",
                    "score": 0.85
                }
            ]
        }

        # Mock the _get_client method directly
        mock_client = Mock()
        mock_client.search.return_value = mock_results

        with patch.object(tool, '_get_client', return_value=mock_client):
            result = await tool.execute(query="test query", max_results=2)

            assert result.success is True
            assert result.output["result_count"] == 2
            assert len(result.output["results"]) == 2
            assert result.output["results"][0]["title"] == "Test Result 1"
            assert "test query" in result.output["message"].lower()

    @pytest.mark.asyncio
    @pytest.mark.skipif(
        not os.getenv("TAVILY_API_KEY"),
        reason="TAVILY_API_KEY not set - skip integration test"
    )
    async def test_execute_real_api(self):
        """Integration test with real Tavily API (requires API key)"""
        tool = WebSearchTool()  # Uses env var

        result = await tool.execute(
            query="Python programming language",
            max_results=3,
            search_depth="basic"
        )

        assert result.success is True
        assert result.output["result_count"] > 0
        assert len(result.output["results"]) <= 3
        assert "query" in result.output

    def test_get_schema(self):
        """Test tool schema generation"""
        tool = WebSearchTool(api_key="test_key")
        schema = tool.get_schema()

        assert schema["name"] == "web_search"
        assert "query" in schema["parameters"]
        assert "max_results" in schema["parameters"]
        assert "search_depth" in schema["parameters"]

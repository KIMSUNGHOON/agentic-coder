"""
Unit tests for CodeSearchTool
"""

import pytest
import os
from unittest.mock import Mock, patch, MagicMock
from app.tools.search_tools import CodeSearchTool
from app.tools.base import ToolResult


class TestCodeSearchTool:
    """Test cases for CodeSearchTool"""

    def test_init(self):
        """Test tool initialization"""
        tool = CodeSearchTool(chroma_path="./test_chroma")
        assert tool.name == "code_search"
        assert tool.chroma_path == "./test_chroma"
        assert "query" in tool.parameters

    def test_init_default_path(self):
        """Test initialization with default path"""
        tool = CodeSearchTool()
        assert tool.chroma_path == "./chroma_db"

    def test_validate_params_valid(self):
        """Test parameter validation with valid params"""
        tool = CodeSearchTool()

        # Valid params
        assert tool.validate_params(query="authentication") is True
        assert tool.validate_params(query="test", n_results=10) is True
        assert tool.validate_params(query="api", repo_filter="myrepo") is True

    def test_validate_params_invalid(self):
        """Test parameter validation with invalid params"""
        tool = CodeSearchTool()

        # Missing query
        assert tool.validate_params() is False
        assert tool.validate_params(query="") is False

        # Invalid n_results
        assert tool.validate_params(query="test", n_results=0) is False
        assert tool.validate_params(query="test", n_results=100) is False

    @pytest.mark.asyncio
    async def test_execute_with_mock(self):
        """Test execution with mocked ChromaDB"""
        tool = CodeSearchTool()

        # Mock search results
        mock_results = [
            {
                "file_path": "backend/app/auth.py",
                "file_type": "python",
                "chunk_index": 0,
                "content": "def authenticate(user, password):\n    ...",
                "score": 0.92,
                "repo": "test_repo"
            },
            {
                "file_path": "backend/app/middleware.py",
                "file_type": "python",
                "chunk_index": 1,
                "content": "class AuthMiddleware:\n    ...",
                "score": 0.88,
                "repo": "test_repo"
            }
        ]

        # Mock embedder
        mock_embedder = Mock()
        mock_embedder.search.return_value = mock_results

        # Patch the _get_embedder method
        with patch.object(tool, '_get_embedder', return_value=mock_embedder):
            result = await tool.execute(query="authentication", n_results=5)

            assert result.success is True
            assert result.output["result_count"] == 2
            assert len(result.output["results"]) == 2
            assert result.output["results"][0]["file_path"] == "backend/app/auth.py"
            assert "authentication" in result.message.lower()

    @pytest.mark.asyncio
    async def test_execute_no_results(self):
        """Test execution when no results found"""
        tool = CodeSearchTool()

        # Mock empty results
        mock_embedder = Mock()
        mock_embedder.search.return_value = []

        with patch.object(tool, '_get_embedder', return_value=mock_embedder):
            result = await tool.execute(query="nonexistent")

            assert result.success is True
            assert result.output["result_count"] == 0
            assert len(result.output["results"]) == 0

    @pytest.mark.asyncio
    async def test_execute_chromadb_error(self):
        """Test execution when ChromaDB fails"""
        tool = CodeSearchTool()

        # Mock embedder that raises exception
        with patch.object(tool, '_get_embedder', side_effect=RuntimeError("DB connection failed")):
            result = await tool.execute(query="test")

            assert result.success is False
            assert "ChromaDB initialization failed" in result.error

    @pytest.mark.asyncio
    @pytest.mark.skipif(
        not os.path.exists("./chroma_db"),
        reason="ChromaDB not initialized - skip integration test"
    )
    async def test_execute_real_chromadb(self):
        """Integration test with real ChromaDB (requires initialized DB)"""
        tool = CodeSearchTool()

        result = await tool.execute(
            query="tool system",
            n_results=3
        )

        # Result should succeed (even if no results found)
        assert result.success is True
        assert "result_count" in result.output
        assert isinstance(result.output["results"], list)

    def test_get_schema(self):
        """Test tool schema generation"""
        tool = CodeSearchTool()
        schema = tool.get_schema()

        assert schema["name"] == "code_search"
        assert "query" in schema["parameters"]
        assert "n_results" in schema["parameters"]
        assert "repo_filter" in schema["parameters"]
        assert "file_type_filter" in schema["parameters"]

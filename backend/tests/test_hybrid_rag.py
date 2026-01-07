"""Tests for HybridRAG - Phase 3-E verification."""
import pytest
from unittest.mock import MagicMock, patch, PropertyMock
from pathlib import Path

from app.services.hybrid_rag import (
    CodeGraphBuilder,
    HybridRAGBuilder,
    GraphSearchResult,
    HybridRAGContext,
    get_hybrid_rag_builder
)
from app.memory.knowledge_graph import Concept


class TestGraphSearchResult:
    """Test GraphSearchResult dataclass."""

    def test_creation(self):
        """Test dataclass creation."""
        result = GraphSearchResult(
            concept_id="file:test.py",
            concept_type="file",
            name="test.py",
            relationship="contains",
            depth=1,
            properties={"path": "src/test.py"}
        )

        assert result.concept_id == "file:test.py"
        assert result.concept_type == "file"
        assert result.name == "test.py"
        assert result.relationship == "contains"
        assert result.depth == 1
        assert result.properties["path"] == "src/test.py"

    def test_default_properties(self):
        """Test default empty properties."""
        result = GraphSearchResult(
            concept_id="test",
            concept_type="function",
            name="test_func",
            relationship="calls",
            depth=2
        )

        assert result.properties == {}


class TestHybridRAGContext:
    """Test HybridRAGContext dataclass."""

    def test_creation(self):
        """Test dataclass creation with all fields."""
        context = HybridRAGContext(
            vector_context="## Code Context\n...",
            vector_results_count=5,
            files_from_vector=["file1.py", "file2.py"],
            graph_context="## Related Code\n...",
            graph_results_count=3,
            related_concepts=["ClassA", "function_b"],
            conversation_context="## Previous Conversations\n...",
            conversation_results=2,
            search_query="test query",
            avg_relevance=0.75
        )

        assert context.vector_results_count == 5
        assert len(context.files_from_vector) == 2
        assert context.graph_results_count == 3
        assert len(context.related_concepts) == 2
        assert context.conversation_results == 2
        assert context.avg_relevance == 0.75


class TestCodeGraphBuilder:
    """Test CodeGraphBuilder class."""

    def test_initialization(self):
        """Test CodeGraphBuilder instantiation."""
        with patch('app.services.hybrid_rag.get_knowledge_graph') as mock_get_kg:
            mock_graph = MagicMock()
            mock_get_kg.return_value = mock_graph

            builder = CodeGraphBuilder("test_session", "/workspace")

            assert builder.session_id == "test_session"
            assert builder.workspace == Path("/workspace")
            mock_get_kg.assert_called_once_with("test_session")

    def test_detect_language(self):
        """Test language detection from file extension."""
        with patch('app.services.hybrid_rag.get_knowledge_graph'):
            builder = CodeGraphBuilder("test", "/workspace")

            assert builder._detect_language("test.py") == "python"
            assert builder._detect_language("app.js") == "javascript"
            assert builder._detect_language("module.ts") == "typescript"
            assert builder._detect_language("component.tsx") == "typescript"
            assert builder._detect_language("file.jsx") == "javascript"
            assert builder._detect_language("data.json") == "unknown"

    def test_create_file_concept(self):
        """Test file concept creation."""
        with patch('app.services.hybrid_rag.get_knowledge_graph'):
            builder = CodeGraphBuilder("test", "/workspace")

            concept = builder._create_file_concept("/workspace/src/test.py")

            assert concept.type == "file"
            assert concept.name == "test.py"
            assert "path" in concept.properties
            assert concept.properties["extension"] == ".py"

    def test_extract_python_imports(self):
        """Test Python import extraction."""
        with patch('app.services.hybrid_rag.get_knowledge_graph'):
            builder = CodeGraphBuilder("test", "/workspace")

            content = """
import os
import sys
from pathlib import Path
from typing import List, Dict
import json
"""
            imports = builder._extract_imports(content, "python")

            assert "os" in imports
            assert "sys" in imports
            assert "pathlib" in imports
            assert "typing" in imports
            assert "json" in imports

    def test_extract_javascript_imports(self):
        """Test JavaScript import extraction."""
        with patch('app.services.hybrid_rag.get_knowledge_graph'):
            builder = CodeGraphBuilder("test", "/workspace")

            content = """
import React from 'react';
import { useState } from 'react';
const express = require('express');
"""
            imports = builder._extract_imports(content, "javascript")

            assert "react" in imports
            assert "express" in imports

    def test_extract_python_definitions(self):
        """Test Python class/function extraction."""
        with patch('app.services.hybrid_rag.get_knowledge_graph'):
            builder = CodeGraphBuilder("test", "/workspace")

            content = """
class MyClass:
    pass

def my_function():
    pass

class AnotherClass:
    def method(self):
        pass
"""
            definitions = builder._extract_definitions(content, "python", "test.py")

            names = [d.name for d in definitions]
            assert "MyClass" in names
            assert "my_function" in names
            assert "AnotherClass" in names

            # Check types
            types = {d.name: d.type for d in definitions}
            assert types["MyClass"] == "class"
            assert types["my_function"] == "function"

    def test_extract_javascript_definitions(self):
        """Test JavaScript class/function extraction."""
        with patch('app.services.hybrid_rag.get_knowledge_graph'):
            builder = CodeGraphBuilder("test", "/workspace")

            content = """
class Component {
}

export class ExportedComponent {
}

function handleClick() {
}

export async function fetchData() {
}
"""
            definitions = builder._extract_definitions(content, "javascript", "test.js")

            names = [d.name for d in definitions]
            assert "Component" in names
            assert "ExportedComponent" in names
            assert "handleClick" in names
            assert "fetchData" in names

    def test_build_from_files(self, tmp_path):
        """Test building graph from files."""
        # Create test file
        test_file = tmp_path / "test.py"
        test_file.write_text("""
import os

class TestClass:
    pass

def test_function():
    pass
""")

        with patch('app.services.hybrid_rag.get_knowledge_graph') as mock_get_kg:
            mock_graph = MagicMock()
            mock_get_kg.return_value = mock_graph

            builder = CodeGraphBuilder("test", str(tmp_path))
            nodes_added = builder.build_from_files([str(test_file)])

            # Should add: file node + import + class + function
            assert nodes_added >= 4
            assert mock_graph.add_concept.called
            assert mock_graph.add_relationship.called


class TestHybridRAGBuilder:
    """Test HybridRAGBuilder class."""

    def test_initialization(self):
        """Test HybridRAGBuilder instantiation."""
        with patch('app.services.hybrid_rag.get_knowledge_graph') as mock_get_kg:
            with patch('app.services.hybrid_rag.RAGContextBuilder'):
                mock_graph = MagicMock()
                mock_get_kg.return_value = mock_graph

                builder = HybridRAGBuilder("test_session", "/workspace")

                assert builder.session_id == "test_session"
                assert builder.workspace == "/workspace"

    def test_build_context(self):
        """Test hybrid context building."""
        with patch('app.services.hybrid_rag.get_knowledge_graph') as mock_get_kg:
            with patch('app.services.hybrid_rag.RAGContextBuilder') as mock_rag:
                mock_graph = MagicMock()
                mock_get_kg.return_value = mock_graph

                # Mock RAG context
                mock_rag_instance = MagicMock()
                mock_rag.return_value = mock_rag_instance

                from app.services.rag_context import RAGContext
                mock_context = MagicMock(spec=RAGContext)
                mock_context.formatted_context = "## Code\n..."
                mock_context.results_count = 3
                mock_context.files_referenced = ["file1.py"]
                mock_context.conversation_context = ""
                mock_context.conversation_results = 0
                mock_context.avg_relevance = 0.7

                mock_rag_instance.enrich_query.return_value = ("enriched", mock_context)

                builder = HybridRAGBuilder("test_session")
                context = builder.build_context("test query")

                assert isinstance(context, HybridRAGContext)
                assert context.vector_results_count == 3
                assert context.search_query == "test query"

    def test_traverse_graph(self):
        """Test graph traversal from starting files."""
        with patch('app.services.hybrid_rag.get_knowledge_graph') as mock_get_kg:
            with patch('app.services.hybrid_rag.RAGContextBuilder'):
                mock_graph = MagicMock()
                mock_get_kg.return_value = mock_graph

                # Mock search_concepts
                mock_file_node = Concept(
                    id="file:test.py",
                    type="file",
                    name="test.py",
                    properties={}
                )
                mock_graph.search_concepts.return_value = [mock_file_node]

                # Mock get_related_concepts
                mock_related = Concept(
                    id="class:TestClass",
                    type="class",
                    name="TestClass",
                    properties={"file": "test.py"}
                )
                mock_graph.get_related_concepts.return_value = [mock_related]

                # Mock edge data
                mock_graph.graph.get_edge_data.return_value = {"type": "contains"}

                builder = HybridRAGBuilder("test_session")
                results = builder._traverse_graph(["test.py"], depth=2, max_results=5)

                assert len(results) >= 1
                assert results[0].concept_type == "class"
                assert results[0].name == "TestClass"

    def test_format_graph_results_empty(self):
        """Test formatting empty results."""
        with patch('app.services.hybrid_rag.get_knowledge_graph'):
            with patch('app.services.hybrid_rag.RAGContextBuilder'):
                builder = HybridRAGBuilder("test_session")
                formatted, concepts = builder._format_graph_results([])

                assert formatted == ""
                assert concepts == []

    def test_format_graph_results(self):
        """Test formatting graph results."""
        with patch('app.services.hybrid_rag.get_knowledge_graph'):
            with patch('app.services.hybrid_rag.RAGContextBuilder'):
                builder = HybridRAGBuilder("test_session")

                results = [
                    GraphSearchResult(
                        concept_id="class:MyClass",
                        concept_type="class",
                        name="MyClass",
                        relationship="contains",
                        depth=1,
                        properties={"path": "src/module.py"}
                    ),
                    GraphSearchResult(
                        concept_id="function:my_func",
                        concept_type="function",
                        name="my_func",
                        relationship="calls",
                        depth=2,
                        properties={}
                    )
                ]

                formatted, concepts = builder._format_graph_results(results)

                assert "Related Code" in formatted
                assert "MyClass" in formatted
                assert "my_func" in formatted
                assert "class" in formatted
                assert "function" in formatted
                assert "MyClass" in concepts
                assert "my_func" in concepts

    def test_enrich_query(self):
        """Test query enrichment."""
        with patch('app.services.hybrid_rag.get_knowledge_graph') as mock_get_kg:
            with patch('app.services.hybrid_rag.RAGContextBuilder') as mock_rag:
                mock_graph = MagicMock()
                mock_get_kg.return_value = mock_graph
                mock_graph.search_concepts.return_value = []

                # Mock RAG context
                mock_rag_instance = MagicMock()
                mock_rag.return_value = mock_rag_instance

                from app.services.rag_context import RAGContext
                mock_context = MagicMock(spec=RAGContext)
                mock_context.formatted_context = "## Code Context\nsome code"
                mock_context.results_count = 2
                mock_context.files_referenced = []
                mock_context.conversation_context = ""
                mock_context.conversation_results = 0
                mock_context.avg_relevance = 0.8

                mock_rag_instance.enrich_query.return_value = ("enriched", mock_context)

                builder = HybridRAGBuilder("test_session")
                enriched, context = builder.enrich_query("How do I use this?")

                assert "How do I use this?" in enriched
                assert isinstance(context, HybridRAGContext)


class TestGetHybridRAGBuilder:
    """Test get_hybrid_rag_builder factory function."""

    def test_returns_instance(self):
        """Test factory returns HybridRAGBuilder instance."""
        with patch('app.services.hybrid_rag.get_knowledge_graph'):
            with patch('app.services.hybrid_rag.RAGContextBuilder'):
                builder = get_hybrid_rag_builder("session_123")
                assert isinstance(builder, HybridRAGBuilder)
                assert builder.session_id == "session_123"

    def test_caches_instance(self):
        """Test that factory caches instances."""
        with patch('app.services.hybrid_rag.get_knowledge_graph'):
            with patch('app.services.hybrid_rag.RAGContextBuilder'):
                # Clear cache first
                from app.services import hybrid_rag
                hybrid_rag._hybrid_builders.clear()

                builder1 = get_hybrid_rag_builder("cache_test")
                builder2 = get_hybrid_rag_builder("cache_test")
                assert builder1 is builder2

    def test_different_sessions(self):
        """Test different sessions get different instances."""
        with patch('app.services.hybrid_rag.get_knowledge_graph'):
            with patch('app.services.hybrid_rag.RAGContextBuilder'):
                # Clear cache first
                from app.services import hybrid_rag
                hybrid_rag._hybrid_builders.clear()

                builder1 = get_hybrid_rag_builder("session_a")
                builder2 = get_hybrid_rag_builder("session_b")
                assert builder1 is not builder2

    def test_workspace_in_cache_key(self):
        """Test workspace is included in cache key."""
        with patch('app.services.hybrid_rag.get_knowledge_graph'):
            with patch('app.services.hybrid_rag.RAGContextBuilder'):
                # Clear cache first
                from app.services import hybrid_rag
                hybrid_rag._hybrid_builders.clear()

                builder1 = get_hybrid_rag_builder("session", "/workspace1")
                builder2 = get_hybrid_rag_builder("session", "/workspace2")
                assert builder1 is not builder2


if __name__ == "__main__":
    pytest.main([__file__, "-v"])

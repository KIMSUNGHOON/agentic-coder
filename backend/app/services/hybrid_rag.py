"""Hybrid RAG - 벡터 검색과 Knowledge Graph 통합

벡터 검색(시맨틱)과 그래프 탐색(관계)을 결합하여
더 풍부한 컨텍스트를 제공합니다.
"""
import re
import logging
from typing import List, Dict, Optional, Tuple, Set
from dataclasses import dataclass, field
from pathlib import Path

from app.services.vector_db import vector_db, SearchResult
from app.services.rag_context import RAGContextBuilder, RAGContext
from app.memory.knowledge_graph import (
    KnowledgeGraph, Concept, Relationship, get_knowledge_graph
)

logger = logging.getLogger(__name__)


@dataclass
class GraphSearchResult:
    """그래프 검색 결과"""
    concept_id: str
    concept_type: str
    name: str
    relationship: str
    depth: int
    properties: Dict = field(default_factory=dict)


@dataclass
class HybridRAGContext:
    """하이브리드 RAG 컨텍스트"""
    # 벡터 검색 결과
    vector_context: str
    vector_results_count: int
    files_from_vector: List[str]

    # 그래프 탐색 결과
    graph_context: str
    graph_results_count: int
    related_concepts: List[str]

    # 대화 검색 결과
    conversation_context: str
    conversation_results: int

    # 메타데이터
    search_query: str
    avg_relevance: float


class CodeGraphBuilder:
    """코드베이스에서 Knowledge Graph를 구축하는 빌더

    파일 간의 관계, import 구문, 클래스/함수 참조 등을
    분석하여 그래프를 구축합니다.
    """

    # 지원하는 import 패턴
    PYTHON_IMPORT_PATTERNS = [
        r'^import\s+([\w.]+)',
        r'^from\s+([\w.]+)\s+import',
    ]

    JS_IMPORT_PATTERNS = [
        r'^import\s+.*?\s+from\s+[\'"]([^"\']+)[\'"]',
        r'^const\s+\w+\s*=\s*require\([\'"]([^"\']+)[\'"]\)',
    ]

    def __init__(self, session_id: str, workspace: str):
        """CodeGraphBuilder 초기화

        Args:
            session_id: 세션 ID
            workspace: 워크스페이스 경로
        """
        self.session_id = session_id
        self.workspace = Path(workspace)
        self.graph = get_knowledge_graph(session_id)
        self.logger = logging.getLogger(f"{__name__}.{session_id[:8]}")

    def build_from_files(self, file_paths: List[str]) -> int:
        """파일 목록에서 그래프 구축

        Args:
            file_paths: 분석할 파일 경로 목록

        Returns:
            int: 추가된 노드 수
        """
        nodes_added = 0

        for file_path in file_paths:
            try:
                # 파일 노드 추가
                file_concept = self._create_file_concept(file_path)
                self.graph.add_concept(file_concept)
                nodes_added += 1

                # 파일 내용 분석
                content = Path(file_path).read_text(encoding='utf-8', errors='ignore')
                language = self._detect_language(file_path)

                # Import/의존성 분석
                imports = self._extract_imports(content, language)
                for imp in imports:
                    # 의존성 노드 추가
                    dep_concept = Concept(
                        id=f"dep:{imp}",
                        type="dependency",
                        name=imp,
                        properties={"source": file_path}
                    )
                    self.graph.add_concept(dep_concept)

                    # 관계 추가
                    rel = Relationship(
                        source_id=file_concept.id,
                        target_id=dep_concept.id,
                        relationship_type="imports",
                        properties={}
                    )
                    self.graph.add_relationship(rel)
                    nodes_added += 1

                # 클래스/함수 분석
                definitions = self._extract_definitions(content, language, file_path)
                for defn in definitions:
                    self.graph.add_concept(defn)
                    # 파일과의 관계
                    rel = Relationship(
                        source_id=file_concept.id,
                        target_id=defn.id,
                        relationship_type="contains",
                        properties={}
                    )
                    self.graph.add_relationship(rel)
                    nodes_added += 1

            except Exception as e:
                self.logger.warning(f"Failed to analyze {file_path}: {e}")

        self.logger.info(f"Built graph: {nodes_added} nodes from {len(file_paths)} files")
        return nodes_added

    def _create_file_concept(self, file_path: str) -> Concept:
        """파일 Concept 생성"""
        path = Path(file_path)
        try:
            rel_path = path.relative_to(self.workspace)
        except ValueError:
            rel_path = path

        return Concept(
            id=f"file:{rel_path}",
            type="file",
            name=path.name,
            properties={
                "path": str(rel_path),
                "extension": path.suffix,
                "directory": str(rel_path.parent)
            }
        )

    def _detect_language(self, file_path: str) -> str:
        """파일 언어 감지"""
        ext = Path(file_path).suffix.lower()
        lang_map = {
            '.py': 'python',
            '.js': 'javascript',
            '.ts': 'typescript',
            '.jsx': 'javascript',
            '.tsx': 'typescript',
        }
        return lang_map.get(ext, 'unknown')

    def _extract_imports(self, content: str, language: str) -> List[str]:
        """Import 구문 추출"""
        imports = []

        if language == 'python':
            patterns = self.PYTHON_IMPORT_PATTERNS
        elif language in ('javascript', 'typescript'):
            patterns = self.JS_IMPORT_PATTERNS
        else:
            return imports

        for line in content.split('\n'):
            for pattern in patterns:
                match = re.match(pattern, line.strip())
                if match:
                    imports.append(match.group(1))

        return imports

    def _extract_definitions(
        self, content: str, language: str, file_path: str
    ) -> List[Concept]:
        """클래스/함수 정의 추출"""
        definitions = []

        if language == 'python':
            # 클래스 추출
            for match in re.finditer(r'^class\s+(\w+)', content, re.MULTILINE):
                definitions.append(Concept(
                    id=f"class:{file_path}::{match.group(1)}",
                    type="class",
                    name=match.group(1),
                    properties={"file": file_path}
                ))

            # 함수 추출
            for match in re.finditer(r'^def\s+(\w+)', content, re.MULTILINE):
                definitions.append(Concept(
                    id=f"function:{file_path}::{match.group(1)}",
                    type="function",
                    name=match.group(1),
                    properties={"file": file_path}
                ))

        elif language in ('javascript', 'typescript'):
            # 클래스 추출
            for match in re.finditer(r'^(?:export\s+)?class\s+(\w+)', content, re.MULTILINE):
                definitions.append(Concept(
                    id=f"class:{file_path}::{match.group(1)}",
                    type="class",
                    name=match.group(1),
                    properties={"file": file_path}
                ))

            # 함수 추출
            for match in re.finditer(r'^(?:export\s+)?(?:async\s+)?function\s+(\w+)', content, re.MULTILINE):
                definitions.append(Concept(
                    id=f"function:{file_path}::{match.group(1)}",
                    type="function",
                    name=match.group(1),
                    properties={"file": file_path}
                ))

        return definitions


class HybridRAGBuilder:
    """하이브리드 RAG 빌더

    벡터 검색과 Knowledge Graph 탐색을 결합하여
    더 풍부한 컨텍스트를 제공합니다.
    """

    def __init__(self, session_id: str, workspace: Optional[str] = None):
        """HybridRAGBuilder 초기화

        Args:
            session_id: 세션 ID
            workspace: 워크스페이스 경로 (그래프 구축용)
        """
        self.session_id = session_id
        self.workspace = workspace
        self.rag_builder = RAGContextBuilder(session_id)
        self.graph = get_knowledge_graph(session_id)
        self.logger = logging.getLogger(f"{__name__}.{session_id[:8]}")

    def build_context(
        self,
        query: str,
        n_vector_results: int = 5,
        n_graph_results: int = 3,
        graph_depth: int = 2,
        min_relevance: float = 0.5,
        include_conversation: bool = True
    ) -> HybridRAGContext:
        """하이브리드 RAG 컨텍스트 구축

        Args:
            query: 검색 쿼리
            n_vector_results: 벡터 검색 결과 수
            n_graph_results: 그래프 탐색 결과 수
            graph_depth: 그래프 탐색 깊이
            min_relevance: 최소 관련성
            include_conversation: 대화 검색 포함 여부

        Returns:
            HybridRAGContext: 하이브리드 컨텍스트
        """
        # 1. 벡터 검색 (코드 + 대화)
        _, rag_context = self.rag_builder.enrich_query(
            query,
            n_results=n_vector_results,
            min_relevance=min_relevance,
            include_conversation=include_conversation
        )

        # 2. 그래프 탐색 (벡터 검색 결과에서 시작)
        graph_results = self._traverse_graph(
            rag_context.files_referenced,
            depth=graph_depth,
            max_results=n_graph_results
        )

        # 3. 그래프 컨텍스트 포맷팅
        graph_context, related_concepts = self._format_graph_results(graph_results)

        self.logger.info(
            f"Hybrid RAG: {rag_context.results_count} vector, "
            f"{len(graph_results)} graph, "
            f"{rag_context.conversation_results} conversation"
        )

        return HybridRAGContext(
            vector_context=rag_context.formatted_context,
            vector_results_count=rag_context.results_count,
            files_from_vector=rag_context.files_referenced,
            graph_context=graph_context,
            graph_results_count=len(graph_results),
            related_concepts=related_concepts,
            conversation_context=rag_context.conversation_context,
            conversation_results=rag_context.conversation_results,
            search_query=query,
            avg_relevance=rag_context.avg_relevance
        )

    def _traverse_graph(
        self,
        starting_files: List[str],
        depth: int = 2,
        max_results: int = 5
    ) -> List[GraphSearchResult]:
        """그래프 탐색

        벡터 검색으로 찾은 파일들에서 시작하여
        관련된 개념들을 탐색합니다.

        Args:
            starting_files: 시작 파일 목록
            depth: 탐색 깊이
            max_results: 최대 결과 수

        Returns:
            List[GraphSearchResult]: 그래프 탐색 결과
        """
        results = []
        visited: Set[str] = set()

        for file_ref in starting_files[:3]:  # 상위 3개 파일만
            # 파일명에서 concept ID 추론
            file_name = Path(file_ref).name if '::' not in file_ref else file_ref.split('::')[0]

            # 그래프에서 관련 파일 노드 찾기
            file_nodes = self.graph.search_concepts("file", {"name": file_name})

            for file_node in file_nodes:
                if file_node.id in visited:
                    continue
                visited.add(file_node.id)

                # 관련 개념 탐색
                related = self.graph.get_related_concepts(
                    file_node.id,
                    depth=depth
                )

                for concept in related:
                    if concept.id in visited:
                        continue
                    visited.add(concept.id)

                    # 관계 타입 추출
                    edge_data = self.graph.graph.get_edge_data(file_node.id, concept.id)
                    rel_type = edge_data.get("type", "related") if edge_data else "related"

                    results.append(GraphSearchResult(
                        concept_id=concept.id,
                        concept_type=concept.type,
                        name=concept.name,
                        relationship=rel_type,
                        depth=1,
                        properties=concept.properties
                    ))

                    if len(results) >= max_results:
                        return results

        return results

    def _format_graph_results(
        self,
        results: List[GraphSearchResult]
    ) -> Tuple[str, List[str]]:
        """그래프 결과 포맷팅

        Args:
            results: 그래프 검색 결과

        Returns:
            Tuple[str, List[str]]: (포맷된 컨텍스트, 관련 개념 목록)
        """
        if not results:
            return "", []

        parts = ["## Related Code (from Knowledge Graph)\n"]
        concepts = []

        for i, result in enumerate(results, 1):
            type_icon = {
                "file": "📄",
                "class": "📦",
                "function": "⚡",
                "dependency": "📚"
            }.get(result.concept_type, "📌")

            parts.append(
                f"### [{i}] {type_icon} {result.name} ({result.concept_type})\n"
                f"- Relationship: {result.relationship}\n"
            )

            if result.properties.get("path"):
                parts.append(f"- Path: {result.properties['path']}\n")

            concepts.append(result.name)

        return "\n".join(parts), concepts

    def enrich_query(
        self,
        user_request: str,
        n_vector_results: int = 5,
        n_graph_results: int = 3,
        include_conversation: bool = True
    ) -> Tuple[str, HybridRAGContext]:
        """사용자 요청을 하이브리드 RAG로 보강

        Args:
            user_request: 원본 사용자 요청
            n_vector_results: 벡터 검색 결과 수
            n_graph_results: 그래프 탐색 결과 수
            include_conversation: 대화 검색 포함 여부

        Returns:
            Tuple[str, HybridRAGContext]: (보강된 요청, 하이브리드 컨텍스트)
        """
        context = self.build_context(
            query=user_request,
            n_vector_results=n_vector_results,
            n_graph_results=n_graph_results,
            include_conversation=include_conversation
        )

        # 컨텍스트 결합
        context_parts = []

        if context.vector_context:
            context_parts.append(context.vector_context)

        if context.graph_context:
            context_parts.append(context.graph_context)

        if context.conversation_context:
            context_parts.append(context.conversation_context)

        if context_parts:
            combined = "\n\n".join(context_parts)
            enriched = f"{user_request}\n\n{combined}"
            return enriched, context

        return user_request, context


# 캐시된 빌더 인스턴스
_hybrid_builders: Dict[str, HybridRAGBuilder] = {}


def get_hybrid_rag_builder(
    session_id: str,
    workspace: Optional[str] = None
) -> HybridRAGBuilder:
    """HybridRAGBuilder 인스턴스 가져오기 (캐시됨)

    Args:
        session_id: 세션 ID
        workspace: 워크스페이스 경로

    Returns:
        HybridRAGBuilder: 빌더 인스턴스
    """
    key = f"{session_id}:{workspace or 'default'}"
    if key not in _hybrid_builders:
        _hybrid_builders[key] = HybridRAGBuilder(session_id, workspace)
    return _hybrid_builders[key]

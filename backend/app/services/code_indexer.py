"""Code Indexer - 프로젝트 코드 자동 색인 서비스.

워크스페이스의 코드 파일들을 자동으로 벡터DB에 색인합니다.
"""
import os
import re
import logging
import hashlib
import asyncio
from pathlib import Path
from typing import List, Dict, Set, Optional, Tuple
from dataclasses import dataclass, field

from app.services.vector_db import vector_db

logger = logging.getLogger(__name__)


@dataclass
class IndexingStats:
    """색인 작업 통계"""
    indexed: int = 0
    skipped: int = 0
    errors: int = 0
    total_chunks: int = 0
    files_processed: List[str] = field(default_factory=list)
    error_files: List[str] = field(default_factory=list)


class CodeIndexer:
    """프로젝트 코드를 벡터DB에 색인하는 서비스

    워크스페이스 내의 코드 파일들을 스캔하고,
    각 파일을 의미 있는 청크로 분할하여 벡터DB에 저장합니다.
    """

    # 지원하는 파일 확장자와 언어 매핑
    SUPPORTED_EXTENSIONS: Dict[str, str] = {
        '.py': 'python',
        '.js': 'javascript',
        '.ts': 'typescript',
        '.jsx': 'javascript',
        '.tsx': 'typescript',
        '.java': 'java',
        '.go': 'go',
        '.rs': 'rust',
        '.cpp': 'cpp',
        '.c': 'c',
        '.h': 'c',
        '.hpp': 'cpp',
        '.cs': 'csharp',
        '.rb': 'ruby',
        '.php': 'php',
        '.swift': 'swift',
        '.kt': 'kotlin',
        '.scala': 'scala',
        '.r': 'r',
        '.sql': 'sql',
        '.sh': 'bash',
        '.yaml': 'yaml',
        '.yml': 'yaml',
        '.json': 'json',
        '.md': 'markdown',
        '.html': 'html',
        '.css': 'css',
        '.scss': 'scss',
        '.vue': 'vue',
        '.svelte': 'svelte',
    }

    # 제외할 디렉토리
    EXCLUDED_DIRS: Set[str] = {
        'node_modules', '.git', '__pycache__', '.venv', 'venv',
        'dist', 'build', '.next', 'coverage', '.pytest_cache',
        '.mypy_cache', '.tox', 'eggs', '*.egg-info', '.eggs',
        'target', 'out', 'bin', 'obj', '.idea', '.vscode',
        '.cache', 'tmp', 'temp', 'logs', '.logs',
    }

    # 제외할 파일 패턴
    EXCLUDED_PATTERNS: Set[str] = {
        '*.min.js', '*.min.css', '*.map', '*.lock',
        'package-lock.json', 'yarn.lock', 'pnpm-lock.yaml',
        '*.pyc', '*.pyo', '*.so', '*.dll', '*.exe',
        '*.png', '*.jpg', '*.jpeg', '*.gif', '*.ico', '*.svg',
        '*.pdf', '*.doc', '*.docx', '*.xls', '*.xlsx',
        '.DS_Store', 'Thumbs.db', '*.log',
    }

    # 청크 설정
    MAX_CHUNK_SIZE: int = 2000  # 최대 청크 크기 (문자)
    MIN_CHUNK_SIZE: int = 100   # 최소 청크 크기
    MAX_FILE_SIZE: int = 100000  # 최대 파일 크기 (100KB)

    def __init__(self, workspace: str, session_id: str):
        """CodeIndexer 초기화

        Args:
            workspace: 워크스페이스 경로
            session_id: 세션 ID (색인 그룹화용)
        """
        self.workspace = Path(workspace)
        self.session_id = session_id
        self.logger = logging.getLogger(f"{__name__}.{session_id[:8]}")

    async def index_project(self,
                           incremental: bool = True,
                           max_files: Optional[int] = None) -> IndexingStats:
        """전체 프로젝트 색인

        Args:
            incremental: True면 변경된 파일만 색인 (현재는 전체 색인)
            max_files: 최대 색인할 파일 수 (None이면 무제한)

        Returns:
            IndexingStats: 색인 통계
        """
        stats = IndexingStats()
        self.logger.info(f"Starting project indexing: {self.workspace}")

        code_files = list(self._get_code_files())
        total_files = len(code_files)

        if max_files:
            code_files = code_files[:max_files]

        self.logger.info(f"Found {total_files} code files, indexing {len(code_files)}")

        for i, file_path in enumerate(code_files):
            try:
                # 진행률 로깅 (10% 단위)
                if total_files > 10 and i % (total_files // 10) == 0:
                    self.logger.info(f"Indexing progress: {i}/{len(code_files)} ({i*100//len(code_files)}%)")

                chunk_count = await self._index_file(file_path)
                stats.indexed += 1
                stats.total_chunks += chunk_count
                stats.files_processed.append(str(file_path))

            except Exception as e:
                self.logger.warning(f"Failed to index {file_path}: {e}")
                stats.errors += 1
                stats.error_files.append(str(file_path))

        self.logger.info(
            f"Indexing complete: {stats.indexed} files, "
            f"{stats.total_chunks} chunks, {stats.errors} errors"
        )

        # Knowledge Graph 구축 (Phase 3-E)
        await self._build_knowledge_graph(stats.files_processed)

        return stats

    async def _build_knowledge_graph(self, file_paths: List[str]):
        """Knowledge Graph 구축

        색인된 파일들을 분석하여 Knowledge Graph를 구축합니다.

        Args:
            file_paths: 분석할 파일 경로 목록
        """
        try:
            from app.services.hybrid_rag import CodeGraphBuilder

            builder = CodeGraphBuilder(self.session_id, str(self.workspace))
            nodes_added = builder.build_from_files(file_paths)
            self.logger.info(f"Knowledge Graph built: {nodes_added} nodes")
        except Exception as e:
            # 그래프 구축 실패해도 색인은 완료된 것으로 처리
            self.logger.warning(f"Knowledge Graph build failed: {e}")

    async def index_file(self, file_path: str) -> List[str]:
        """단일 파일 색인

        Args:
            file_path: 파일 경로

        Returns:
            List[str]: 생성된 문서 ID 목록
        """
        return await self._index_file(Path(file_path))

    async def _index_file(self, file_path: Path) -> int:
        """파일 색인 내부 구현

        Args:
            file_path: 파일 경로

        Returns:
            int: 생성된 청크 수
        """
        # 파일 읽기
        try:
            content = file_path.read_text(encoding='utf-8', errors='ignore')
        except Exception as e:
            self.logger.warning(f"Cannot read file {file_path}: {e}")
            raise

        # 파일 크기 체크
        if len(content) > self.MAX_FILE_SIZE:
            self.logger.debug(f"File too large, truncating: {file_path}")
            content = content[:self.MAX_FILE_SIZE]

        # 상대 경로 계산
        try:
            rel_path = file_path.relative_to(self.workspace)
        except ValueError:
            rel_path = file_path

        # 언어 감지
        language = self._detect_language(file_path)

        # 코드 청킹
        chunks = self._chunk_code(content, str(rel_path), language)

        # 각 청크 색인
        for chunk in chunks:
            doc_id = vector_db.add_code_snippet(
                code=chunk['code'],
                filename=chunk['filename'],
                language=chunk['language'],
                session_id=self.session_id,
                description=chunk['description']
            )
            self.logger.debug(f"Indexed chunk: {chunk['filename']} ({len(chunk['code'])} chars)")

        return len(chunks)

    def _get_code_files(self) -> List[Path]:
        """워크스페이스에서 코드 파일 목록 가져오기

        Returns:
            List[Path]: 코드 파일 경로 목록
        """
        code_files = []

        for root, dirs, files in os.walk(self.workspace):
            # 제외 디렉토리 필터링
            dirs[:] = [d for d in dirs if d not in self.EXCLUDED_DIRS
                      and not d.startswith('.')]

            for filename in files:
                file_path = Path(root) / filename

                # 확장자 체크
                if file_path.suffix.lower() not in self.SUPPORTED_EXTENSIONS:
                    continue

                # 제외 패턴 체크
                if self._should_exclude(filename):
                    continue

                code_files.append(file_path)

        return code_files

    def _should_exclude(self, filename: str) -> bool:
        """파일이 제외 대상인지 확인

        Args:
            filename: 파일명

        Returns:
            bool: 제외해야 하면 True
        """
        import fnmatch
        for pattern in self.EXCLUDED_PATTERNS:
            if fnmatch.fnmatch(filename, pattern):
                return True
        return False

    def _detect_language(self, file_path: Path) -> str:
        """파일 확장자로 언어 감지

        Args:
            file_path: 파일 경로

        Returns:
            str: 언어 이름
        """
        return self.SUPPORTED_EXTENSIONS.get(
            file_path.suffix.lower(),
            'text'
        )

    def _chunk_code(self, content: str, filename: str, language: str) -> List[Dict]:
        """코드를 의미 있는 청크로 분할

        현재 구현: 파일 단위 + 크기 기반 분할
        TODO: AST 기반 함수/클래스 단위 분할

        Args:
            content: 파일 내용
            filename: 파일 이름
            language: 프로그래밍 언어

        Returns:
            List[Dict]: 청크 목록
        """
        chunks = []

        # 작은 파일은 전체를 하나의 청크로
        if len(content) <= self.MAX_CHUNK_SIZE:
            description = self._generate_description(content, filename, language)
            chunks.append({
                'code': content,
                'filename': filename,
                'language': language,
                'description': description
            })
            return chunks

        # 큰 파일은 함수/클래스 단위로 분할 시도
        if language == 'python':
            chunks = self._chunk_python(content, filename, language)
        elif language in ('javascript', 'typescript'):
            chunks = self._chunk_javascript(content, filename, language)
        else:
            # 기본: 라인 기반 분할
            chunks = self._chunk_by_lines(content, filename, language)

        return chunks if chunks else [{
            'code': content[:self.MAX_CHUNK_SIZE],
            'filename': filename,
            'language': language,
            'description': f"Partial content of {filename}"
        }]

    def _chunk_python(self, content: str, filename: str, language: str) -> List[Dict]:
        """Python 코드를 함수/클래스 단위로 분할

        Args:
            content: 파일 내용
            filename: 파일 이름
            language: 언어

        Returns:
            List[Dict]: 청크 목록
        """
        chunks = []

        # 정규식으로 함수와 클래스 찾기
        # class/def 시작점 찾기
        pattern = r'^(class\s+\w+|def\s+\w+|async\s+def\s+\w+)'

        lines = content.split('\n')
        current_chunk_start = 0
        current_chunk_lines = []
        current_name = "module_header"

        for i, line in enumerate(lines):
            match = re.match(pattern, line.lstrip())
            if match and len(line) - len(line.lstrip()) == 0:  # 탑레벨만
                # 이전 청크 저장
                if current_chunk_lines:
                    chunk_content = '\n'.join(current_chunk_lines)
                    if len(chunk_content) >= self.MIN_CHUNK_SIZE:
                        chunks.append({
                            'code': chunk_content,
                            'filename': f"{filename}::{current_name}",
                            'language': language,
                            'description': f"{current_name} in {filename}"
                        })

                # 새 청크 시작
                current_name = match.group(1).split()[1] if len(match.group(1).split()) > 1 else match.group(1)
                current_chunk_lines = [line]
                current_chunk_start = i
            else:
                current_chunk_lines.append(line)

        # 마지막 청크
        if current_chunk_lines:
            chunk_content = '\n'.join(current_chunk_lines)
            if len(chunk_content) >= self.MIN_CHUNK_SIZE:
                chunks.append({
                    'code': chunk_content,
                    'filename': f"{filename}::{current_name}",
                    'language': language,
                    'description': f"{current_name} in {filename}"
                })

        # 청크가 없거나 너무 크면 라인 기반으로
        if not chunks:
            return self._chunk_by_lines(content, filename, language)

        # 너무 큰 청크는 추가 분할
        final_chunks = []
        for chunk in chunks:
            if len(chunk['code']) > self.MAX_CHUNK_SIZE:
                sub_chunks = self._chunk_by_lines(
                    chunk['code'],
                    chunk['filename'],
                    language
                )
                final_chunks.extend(sub_chunks)
            else:
                final_chunks.append(chunk)

        return final_chunks

    def _chunk_javascript(self, content: str, filename: str, language: str) -> List[Dict]:
        """JavaScript/TypeScript 코드를 함수/클래스 단위로 분할

        Args:
            content: 파일 내용
            filename: 파일 이름
            language: 언어

        Returns:
            List[Dict]: 청크 목록
        """
        chunks = []

        # export, function, class, const 패턴
        pattern = r'^(export\s+)?(class\s+\w+|function\s+\w+|const\s+\w+\s*=|let\s+\w+\s*=|async\s+function\s+\w+)'

        lines = content.split('\n')
        current_chunk_lines = []
        current_name = "module"

        for line in lines:
            match = re.match(pattern, line.lstrip())
            if match:
                # 이전 청크 저장
                if current_chunk_lines and len('\n'.join(current_chunk_lines)) >= self.MIN_CHUNK_SIZE:
                    chunk_content = '\n'.join(current_chunk_lines)
                    chunks.append({
                        'code': chunk_content,
                        'filename': f"{filename}::{current_name}",
                        'language': language,
                        'description': f"{current_name} in {filename}"
                    })

                # 새 청크 시작
                parts = match.group(0).replace('export ', '').split()
                current_name = parts[1] if len(parts) > 1 else parts[0]
                current_name = current_name.split('=')[0].strip()
                current_chunk_lines = [line]
            else:
                current_chunk_lines.append(line)

        # 마지막 청크
        if current_chunk_lines and len('\n'.join(current_chunk_lines)) >= self.MIN_CHUNK_SIZE:
            chunk_content = '\n'.join(current_chunk_lines)
            chunks.append({
                'code': chunk_content,
                'filename': f"{filename}::{current_name}",
                'language': language,
                'description': f"{current_name} in {filename}"
            })

        if not chunks:
            return self._chunk_by_lines(content, filename, language)

        return chunks

    def _chunk_by_lines(self, content: str, filename: str, language: str) -> List[Dict]:
        """라인 기반으로 청크 분할

        Args:
            content: 파일 내용
            filename: 파일 이름
            language: 언어

        Returns:
            List[Dict]: 청크 목록
        """
        chunks = []
        lines = content.split('\n')
        current_chunk = []
        current_size = 0
        chunk_num = 1

        for line in lines:
            line_size = len(line) + 1  # +1 for newline

            if current_size + line_size > self.MAX_CHUNK_SIZE and current_chunk:
                # 청크 저장
                chunk_content = '\n'.join(current_chunk)
                chunks.append({
                    'code': chunk_content,
                    'filename': f"{filename}::part{chunk_num}",
                    'language': language,
                    'description': f"Part {chunk_num} of {filename}"
                })
                chunk_num += 1
                current_chunk = [line]
                current_size = line_size
            else:
                current_chunk.append(line)
                current_size += line_size

        # 마지막 청크
        if current_chunk:
            chunk_content = '\n'.join(current_chunk)
            if len(chunk_content) >= self.MIN_CHUNK_SIZE:
                chunks.append({
                    'code': chunk_content,
                    'filename': f"{filename}::part{chunk_num}" if chunk_num > 1 else filename,
                    'language': language,
                    'description': f"Part {chunk_num} of {filename}" if chunk_num > 1 else f"Content of {filename}"
                })

        return chunks

    def _generate_description(self, content: str, filename: str, language: str) -> str:
        """코드 청크의 설명 생성

        Args:
            content: 코드 내용
            filename: 파일 이름
            language: 언어

        Returns:
            str: 설명 문자열
        """
        # 간단한 휴리스틱으로 설명 생성
        lines = content.split('\n')[:10]  # 첫 10줄

        # docstring이나 주석 찾기
        for line in lines:
            stripped = line.strip()
            if stripped.startswith('"""') or stripped.startswith("'''"):
                # Python docstring
                return f"{filename}: {stripped[3:50]}..."
            elif stripped.startswith('//') or stripped.startswith('#'):
                # 주석
                comment = stripped.lstrip('/# ')
                if len(comment) > 10:
                    return f"{filename}: {comment[:50]}..."
            elif stripped.startswith('/*'):
                # Block comment
                comment = stripped.lstrip('/* ')
                if len(comment) > 10:
                    return f"{filename}: {comment[:50]}..."

        # 기본 설명
        return f"Code from {filename} ({language})"


# 전역 인덱서 팩토리
_indexers: Dict[str, CodeIndexer] = {}


def get_code_indexer(workspace: str, session_id: str) -> CodeIndexer:
    """CodeIndexer 인스턴스 가져오기 (캐시됨)

    Args:
        workspace: 워크스페이스 경로
        session_id: 세션 ID

    Returns:
        CodeIndexer: 인덱서 인스턴스
    """
    key = f"{workspace}:{session_id}"
    if key not in _indexers:
        _indexers[key] = CodeIndexer(workspace, session_id)
    return _indexers[key]

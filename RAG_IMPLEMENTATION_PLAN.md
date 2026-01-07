# RAG System Implementation Plan

**Date**: 2026-01-08
**Author**: Claude Code
**Status**: Planning

---

## 1. RAG 시스템 개요

### 1.1 RAG란?

**RAG (Retrieval-Augmented Generation)** 는 LLM 응답의 품질과 정확도를 높이기 위해 **외부 지식을 검색하여 컨텍스트로 제공**하는 기술입니다.

```
┌──────────────────────────────────────────────────────────────────┐
│                     전통적인 LLM 방식                              │
│                                                                   │
│   사용자: "UserService 수정해줘"                                   │
│                    ↓                                              │
│                  [LLM]                                            │
│                    ↓                                              │
│   응답: "UserService 코드를 보여주세요" (프로젝트 코드 모름)         │
└──────────────────────────────────────────────────────────────────┘

┌──────────────────────────────────────────────────────────────────┐
│                     RAG 방식                                      │
│                                                                   │
│   사용자: "UserService 수정해줘"                                   │
│                    ↓                                              │
│           [1. 벡터 검색: "UserService"]                           │
│                    ↓                                              │
│           [2. 관련 코드 5개 검색됨]                                │
│              - user_service.py (유사도 0.95)                      │
│              - user_model.py (유사도 0.82)                        │
│              - auth_service.py (유사도 0.71)                      │
│                    ↓                                              │
│           [3. LLM + 검색된 코드 컨텍스트]                          │
│                    ↓                                              │
│   응답: "user_service.py의 UserService를 분석했습니다.             │
│          현재 get_user() 메서드가... 어떤 수정이 필요하신가요?"     │
└──────────────────────────────────────────────────────────────────┘
```

### 1.2 RAG의 핵심 구성요소

```
┌─────────────────────────────────────────────────────────────────┐
│                        RAG Pipeline                              │
├─────────────────────────────────────────────────────────────────┤
│                                                                  │
│  [Indexing Phase - 색인 단계]                                    │
│                                                                  │
│    코드/문서 → Chunking → Embedding → Vector DB 저장             │
│       │           │          │              │                    │
│       │      (분할)      (벡터화)      (ChromaDB)                 │
│       │                                                          │
│    예: user_service.py                                           │
│        ↓                                                         │
│        "class UserService:                                       │
│         def get_user(self, id):"  → [0.12, -0.45, 0.78, ...]    │
│                                                                  │
├─────────────────────────────────────────────────────────────────┤
│                                                                  │
│  [Retrieval Phase - 검색 단계]                                   │
│                                                                  │
│    사용자 질문 → Embedding → 유사도 검색 → Top-K 결과             │
│         │           │            │            │                  │
│    "UserService"   벡터화    코사인 유사도   가장 관련된 5개       │
│                                                                  │
├─────────────────────────────────────────────────────────────────┤
│                                                                  │
│  [Generation Phase - 생성 단계]                                  │
│                                                                  │
│    검색 결과 + 질문 → 프롬프트 구성 → LLM → 응답                  │
│         │                 │            │                         │
│    "다음 코드를 참고하여  시스템 프롬프트  정확한 응답             │
│     질문에 답하세요:      + 컨텍스트                              │
│     [검색된 코드들]"                                              │
│                                                                  │
└─────────────────────────────────────────────────────────────────┘
```

### 1.3 TestCodeAgent에서 RAG가 필요한 이유

| 현재 문제 | RAG 해결책 | 기대 효과 |
|----------|-----------|----------|
| LLM이 프로젝트 코드를 모름 | 코드를 벡터DB에 색인 | 정확한 코드 참조 |
| 긴 대화에서 컨텍스트 손실 | 대화 요약 저장 및 검색 | 일관된 대화 유지 |
| 이전 결정사항 망각 | 결정사항 색인 | 일관된 의사결정 |
| 반복적인 코드 분석 요청 | 분석 결과 캐싱 | 응답 속도 향상 |
| 할루시네이션 | 실제 코드 기반 응답 | 정확도 향상 |

---

## 2. 현재 인프라 분석

### 2.1 이미 구현된 컴포넌트

| 컴포넌트 | 파일 위치 | 상태 | 설명 |
|---------|----------|------|------|
| VectorDBService | `app/services/vector_db.py` | ⚠️ 코드 있음, 미설치 | ChromaDB 기반 벡터 저장/검색 |
| KnowledgeGraph | `app/memory/knowledge_graph.py` | ✅ 활성화 | NetworkX 기반 코드 구조 그래프 |
| ContextManager | `app/utils/context_manager.py` | ✅ 활성화 | 컨텍스트 압축/추출 (Phase 2) |
| Vector API | `app/api/main_routes.py` | ⚠️ 엔드포인트 있음 | /vector/* REST API |
| LM Cache | `app/services/lm_cache.py` | ✅ 활성화 | LLM 응답 캐싱 |

### 2.2 현재 아키텍처

```
┌─────────────────────────────────────────────────────────────────┐
│                    Current Architecture                          │
├─────────────────────────────────────────────────────────────────┤
│                                                                  │
│  Frontend (React) ←→ FastAPI Backend ←→ vLLM (DeepSeek/GPT-OSS) │
│                           │                                      │
│                           ├── ContextManager (압축/추출) ✅       │
│                           ├── KnowledgeGraph (NetworkX) ✅       │
│                           ├── LM Cache (Redis) ✅                │
│                           └── VectorDB (ChromaDB) ⚠️ 미설치      │
│                                                                  │
└─────────────────────────────────────────────────────────────────┘
```

### 2.3 Gap Analysis

| 필요 기능 | 현재 상태 | 필요 작업 |
|----------|----------|----------|
| ChromaDB 설치 | 주석 처리됨 | requirements.txt 활성화 |
| 코드 자동 색인 | API만 존재 | 워크플로우 통합 |
| 질의 시 자동 검색 | 미구현 | Supervisor/Handler 통합 |
| Embedding 모델 | 기본값 사용 | 선택적 업그레이드 |
| 대화 컨텍스트 색인 | 미구현 | 새 기능 추가 |

---

## 3. 구현 계획

### 3.1 Phase 3-A: 기본 RAG 활성화 (Priority: HIGH)

**목표**: 기존 VectorDB 인프라 활성화 및 테스트

#### Task 3-A-1: ChromaDB 설치 및 검증
```bash
# requirements.txt에서 주석 해제
chromadb>=0.4.0
```

**검증 방법**:
```python
from app.services.vector_db import vector_db
stats = vector_db.get_stats()
print(stats)  # {'collection': 'code_snippets', 'count': 0, ...}
```

#### Task 3-A-2: 수동 코드 색인 테스트
```python
# API 테스트
POST /vector/index
{
    "code": "class UserService:\n    def get_user(self, id): ...",
    "filename": "user_service.py",
    "language": "python",
    "session_id": "test-session",
    "description": "User management service"
}
```

#### Task 3-A-3: 검색 기능 테스트
```python
# API 테스트
GET /vector/search?query=UserService&n_results=5
```

**예상 소요**: 1-2시간

---

### 3.2 Phase 3-B: 자동 코드 색인 (Priority: HIGH)

**목표**: 프로젝트 코드를 자동으로 벡터DB에 색인

#### Task 3-B-1: CodeIndexer 클래스 생성

**파일**: `backend/app/services/code_indexer.py`

```python
"""Code Indexer - 프로젝트 코드 자동 색인 서비스"""
import os
from pathlib import Path
from typing import List, Dict, Optional
from app.services.vector_db import vector_db

class CodeIndexer:
    """프로젝트 코드를 벡터DB에 색인하는 서비스"""

    # 색인할 파일 확장자
    SUPPORTED_EXTENSIONS = {
        '.py': 'python',
        '.js': 'javascript',
        '.ts': 'typescript',
        '.jsx': 'javascript',
        '.tsx': 'typescript',
        '.java': 'java',
        '.go': 'go',
        '.rs': 'rust',
    }

    # 제외할 디렉토리
    EXCLUDED_DIRS = {
        'node_modules', '.git', '__pycache__', '.venv',
        'venv', 'dist', 'build', '.next', 'coverage'
    }

    def __init__(self, workspace: str, session_id: str):
        self.workspace = Path(workspace)
        self.session_id = session_id

    async def index_project(self) -> Dict[str, int]:
        """전체 프로젝트 색인"""
        stats = {'indexed': 0, 'skipped': 0, 'errors': 0}

        for file_path in self._get_code_files():
            try:
                await self._index_file(file_path)
                stats['indexed'] += 1
            except Exception as e:
                stats['errors'] += 1

        return stats

    async def index_file(self, file_path: str) -> str:
        """단일 파일 색인"""
        # 파일 읽기
        content = Path(file_path).read_text(encoding='utf-8')

        # 청킹 (함수/클래스 단위)
        chunks = self._chunk_code(content, file_path)

        # 각 청크 색인
        doc_ids = []
        for chunk in chunks:
            doc_id = await vector_db.add_code_snippet(
                code=chunk['code'],
                filename=chunk['filename'],
                language=chunk['language'],
                session_id=self.session_id,
                description=chunk['description']
            )
            doc_ids.append(doc_id)

        return doc_ids

    def _chunk_code(self, content: str, file_path: str) -> List[Dict]:
        """코드를 의미 있는 단위로 분할"""
        # TODO: AST 파싱으로 함수/클래스 단위 분할
        # 우선은 파일 전체를 하나의 청크로
        return [{
            'code': content,
            'filename': os.path.basename(file_path),
            'language': self._detect_language(file_path),
            'description': f"Full content of {file_path}"
        }]
```

#### Task 3-B-2: 워크스페이스 로드 시 자동 색인

**파일**: `backend/app/api/main_routes.py` (기존 파일 수정)

```python
@router.post("/workspace/load")
async def load_workspace(request: WorkspaceRequest):
    # 기존 로직...

    # RAG 색인 트리거 (비동기 백그라운드)
    indexer = CodeIndexer(request.path, session_id)
    asyncio.create_task(indexer.index_project())

    return {"status": "success", "indexing": "started"}
```

**예상 소요**: 4-6시간

---

### 3.3 Phase 3-C: 검색 통합 (Priority: HIGH)

**목표**: 사용자 질문 시 자동으로 관련 코드 검색

#### Task 3-C-1: RAG Context Builder

**파일**: `backend/app/services/rag_context.py`

```python
"""RAG Context Builder - 질의에 맞는 컨텍스트 구성"""
from typing import List, Dict, Optional
from app.services.vector_db import vector_db, SearchResult

class RAGContextBuilder:
    """사용자 질문에 맞는 RAG 컨텍스트를 구성"""

    def __init__(self, session_id: str):
        self.session_id = session_id

    async def build_context(
        self,
        query: str,
        n_results: int = 5,
        min_relevance: float = 0.7
    ) -> str:
        """질문에 관련된 코드 컨텍스트 생성"""

        # 벡터 검색
        results = await vector_db.search_code(
            query=query,
            session_id=self.session_id,
            n_results=n_results
        )

        # 관련성 필터링
        relevant = [r for r in results if r.distance < (1 - min_relevance)]

        if not relevant:
            return ""

        # 컨텍스트 포맷팅
        context_parts = ["## Relevant Code from Project\n"]

        for i, result in enumerate(relevant, 1):
            filename = result.metadata.get('filename', 'unknown')
            language = result.metadata.get('language', 'text')
            relevance = round((1 - result.distance) * 100, 1)

            context_parts.append(f"""
### [{i}] {filename} (Relevance: {relevance}%)

```{language}
{result.content}
```
""")

        return "\n".join(context_parts)
```

#### Task 3-C-2: Supervisor 통합

**파일**: `backend/core/supervisor.py` (기존 파일 수정)

```python
class SupervisorAgent:
    def __init__(self, use_api: bool = True):
        # 기존 초기화...
        self.rag_builder = None  # Lazy initialization

    async def _enrich_with_rag(
        self,
        user_request: str,
        session_id: str
    ) -> str:
        """RAG 컨텍스트로 요청 보강"""
        if not self.rag_builder:
            from app.services.rag_context import RAGContextBuilder
            self.rag_builder = RAGContextBuilder(session_id)

        rag_context = await self.rag_builder.build_context(user_request)

        if rag_context:
            return f"{user_request}\n\n{rag_context}"
        return user_request
```

**예상 소요**: 4-6시간

---

### 3.4 Phase 3-D: 대화 컨텍스트 RAG (Priority: MEDIUM)

**목표**: 이전 대화 내용도 벡터 검색 가능하게

#### Task 3-D-1: 대화 색인 서비스

```python
class ConversationIndexer:
    """대화 내용을 벡터DB에 색인"""

    async def index_message(
        self,
        message: str,
        role: str,  # 'user' or 'assistant'
        session_id: str,
        turn_number: int
    ) -> str:
        """개별 메시지 색인"""
        return await vector_db.add_documents(
            documents=[message],
            metadatas=[{
                'type': 'conversation',
                'role': role,
                'session_id': session_id,
                'turn': turn_number
            }]
        )

    async def search_conversation(
        self,
        query: str,
        session_id: str,
        n_results: int = 3
    ) -> List[SearchResult]:
        """이전 대화에서 관련 내용 검색"""
        return await vector_db.search(
            query=query,
            n_results=n_results,
            where={'session_id': session_id, 'type': 'conversation'}
        )
```

**예상 소요**: 2-4시간

---

### 3.5 Phase 3-E: Knowledge Graph 통합 (Priority: MEDIUM)

**목표**: 벡터 검색 + 그래프 탐색 결합

```
┌─────────────────────────────────────────────────────────────────┐
│                  Hybrid RAG Architecture                         │
├─────────────────────────────────────────────────────────────────┤
│                                                                  │
│  사용자 질문: "UserService의 get_user를 수정하려면?"              │
│                     │                                            │
│          ┌─────────┴─────────┐                                  │
│          ↓                   ↓                                   │
│   [Vector Search]      [Graph Traversal]                        │
│   "UserService" 검색   UserService 노드에서                      │
│          │             연결된 노드 탐색                          │
│          ↓                   ↓                                   │
│   user_service.py      - UserModel (uses)                       │
│   (0.95 relevance)     - DatabaseService (calls)                │
│                        - AuthMiddleware (related)                │
│          │                   │                                   │
│          └─────────┬─────────┘                                  │
│                    ↓                                             │
│           [Combined Context]                                     │
│           - 직접 관련 코드 (vector)                              │
│           - 의존성 코드 (graph)                                  │
│                    ↓                                             │
│              [LLM Response]                                      │
│                                                                  │
└─────────────────────────────────────────────────────────────────┘
```

**예상 소요**: 6-8시간

---

## 4. 기술 스택 결정

### 4.1 Embedding 모델 옵션

| 옵션 | 장점 | 단점 | 추천 |
|------|------|------|------|
| ChromaDB 기본 (all-MiniLM-L6-v2) | 무료, 빠름 | 코드 특화 아님 | ✅ 초기 개발 |
| CodeBERT | 코드 특화 | 설치 필요 | 중기 |
| OpenAI Embeddings | 고품질 | 비용 발생, API 의존 | 선택적 |

### 4.2 Vector DB 옵션

| 옵션 | 장점 | 단점 | 현재 상태 |
|------|------|------|----------|
| ChromaDB | 로컬, 무료, 쉬움 | 대규모 시 성능 | ✅ 이미 구현 |
| FAISS | 빠름, Facebook 지원 | 메타데이터 제한 | 선택적 |
| Pinecone | 확장성, 관리형 | 비용, 클라우드 의존 | 미래 옵션 |

**결정**: ChromaDB 유지 (이미 구현되어 있고, 충분한 성능)

---

## 5. 구현 로드맵

```
Week 1: Phase 3-A (기본 활성화)
├── Day 1-2: ChromaDB 설치 및 테스트
└── Day 3: 기존 API 엔드포인트 검증

Week 2: Phase 3-B (자동 색인)
├── Day 1-2: CodeIndexer 구현
├── Day 3-4: 워크스페이스 로드 통합
└── Day 5: 테스트 및 버그 수정

Week 3: Phase 3-C (검색 통합)
├── Day 1-2: RAGContextBuilder 구현
├── Day 3-4: Supervisor 통합
└── Day 5: End-to-end 테스트

Week 4: Phase 3-D & 3-E (고급 기능)
├── Day 1-2: 대화 컨텍스트 RAG
├── Day 3-4: Knowledge Graph 통합
└── Day 5: 문서화 및 최적화
```

---

## 6. 성공 지표 (KPIs)

| 지표 | 현재 | 목표 | 측정 방법 |
|------|------|------|----------|
| 코드 참조 정확도 | N/A | >80% | 검색 결과 관련성 |
| 응답 시간 | ~3s | <4s (RAG 포함) | API 레이턴시 |
| 컨텍스트 활용률 | 0% | >60% | RAG 컨텍스트 사용 비율 |
| 색인 커버리지 | 0% | >90% | 프로젝트 파일 색인율 |

---

## 7. 리스크 및 완화 방안

| 리스크 | 영향 | 확률 | 완화 방안 |
|--------|------|------|----------|
| ChromaDB 호환성 문제 | 높음 | 낮음 | 버전 고정, fallback 구현 |
| 색인 성능 저하 | 중간 | 중간 | 배치 처리, 백그라운드 작업 |
| 검색 품질 낮음 | 높음 | 중간 | Embedding 모델 업그레이드, 청킹 전략 개선 |
| 메모리 사용량 증가 | 중간 | 높음 | 청크 크기 제한, 정기 정리 |

---

## 8. 구현 진행 상황

| Phase | 상태 | 완료일 | Commit |
|-------|------|--------|--------|
| Phase 3-A | ✅ 완료 | 2026-01-08 | c379c5b |
| Phase 3-B | ✅ 완료 | 2026-01-08 | e416536 |
| Phase 3-C | ✅ 완료 | 2026-01-08 | 4c0d555 |
| Phase 3-D | ✅ 완료 | 2026-01-08 | 1eb1dc6 |
| Phase 3-E | ✅ 완료 | 2026-01-08 | 1144bd3 |

### 🎉 RAG System 구현 완료!

모든 Phase가 완료되었습니다. TestCodeAgent는 이제 완전한 RAG 시스템을 갖추었습니다.

### 완료된 핵심 기능

- ✅ ChromaDB 벡터 DB 활성화
- ✅ 자동 코드 인덱싱 (워크스페이스 로드 시)
- ✅ RAG 검색 → Supervisor 통합
- ✅ 관련 코드 자동 첨부 (LLM 응답 품질 향상)
- ✅ 대화 내용 자동 색인 (메시지 저장 시)
- ✅ 이전 대화 시맨틱 검색 (관련 대화 컨텍스트 제공)
- ✅ Knowledge Graph 자동 구축 (코드 인덱싱 시)
- ✅ Hybrid RAG (벡터 검색 + 그래프 탐색 결합)

### Phase 3-E 구현 상세

**새로운 컴포넌트**:
- `CodeGraphBuilder`: 코드베이스에서 Knowledge Graph 자동 구축
  - Python/JavaScript import 추출
  - 클래스/함수 정의 추출
  - 파일-의존성-정의 관계 그래프 생성
- `HybridRAGBuilder`: 벡터 검색 + 그래프 탐색 결합
  - 벡터 검색 결과에서 시작하여 관계된 코드 탐색
  - 시맨틱 + 구조적 컨텍스트 통합 제공

**테스트 커버리지**:
- 74개 RAG 관련 테스트 (21 CodeIndexer + 15 RAGContext + 17 ConversationIndexer + 21 HybridRAG)

---

**문서 작성**: Claude Code
**마지막 업데이트**: 2026-01-08 (Phase 3-E 완료 - RAG 시스템 구현 완료)

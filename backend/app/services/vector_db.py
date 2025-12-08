"""Vector database service using ChromaDB for semantic search."""
import os
import logging
from typing import List, Dict, Any, Optional
from dataclasses import dataclass

logger = logging.getLogger(__name__)

# Data directory for persistence
DATA_DIR = os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(__file__))), "data")
CHROMA_DIR = os.path.join(DATA_DIR, "chromadb")
os.makedirs(CHROMA_DIR, exist_ok=True)


@dataclass
class SearchResult:
    """Search result from vector database."""
    id: str
    content: str
    metadata: Dict[str, Any]
    distance: float


class VectorDBService:
    """Vector database service for semantic search using ChromaDB."""

    def __init__(self, collection_name: str = "code_snippets"):
        """Initialize ChromaDB client and collection.

        Args:
            collection_name: Name of the collection to use
        """
        self.collection_name = collection_name
        self._client = None
        self._collection = None
        self._initialized = False

    def _init_client(self):
        """Lazy initialization of ChromaDB client."""
        if self._initialized:
            return

        try:
            import chromadb
            from chromadb.config import Settings

            # Create persistent client
            self._client = chromadb.PersistentClient(
                path=CHROMA_DIR,
                settings=Settings(anonymized_telemetry=False)
            )

            # Get or create collection
            self._collection = self._client.get_or_create_collection(
                name=self.collection_name,
                metadata={"hnsw:space": "cosine"}  # Use cosine similarity
            )

            self._initialized = True
            logger.info(f"Initialized ChromaDB collection: {self.collection_name}")

        except ImportError:
            logger.warning("ChromaDB not installed. Vector search disabled.")
            raise RuntimeError("ChromaDB not installed. Run: pip install chromadb")
        except Exception as e:
            logger.error(f"Failed to initialize ChromaDB: {e}")
            raise

    @property
    def client(self):
        """Get ChromaDB client (lazy initialization)."""
        self._init_client()
        return self._client

    @property
    def collection(self):
        """Get ChromaDB collection (lazy initialization)."""
        self._init_client()
        return self._collection

    def add_documents(
        self,
        documents: List[str],
        ids: List[str],
        metadatas: Optional[List[Dict[str, Any]]] = None
    ) -> None:
        """Add documents to the vector database.

        Args:
            documents: List of document contents
            ids: List of unique document IDs
            metadatas: Optional list of metadata dicts
        """
        try:
            self.collection.add(
                documents=documents,
                ids=ids,
                metadatas=metadatas
            )
            logger.info(f"Added {len(documents)} documents to vector DB")
        except Exception as e:
            logger.error(f"Failed to add documents: {e}")
            raise

    def add_code_snippet(
        self,
        code: str,
        filename: str,
        language: str,
        session_id: str,
        description: Optional[str] = None
    ) -> str:
        """Add a code snippet to the vector database.

        Args:
            code: The code content
            filename: Name of the file
            language: Programming language
            session_id: Associated session ID
            description: Optional description

        Returns:
            Document ID
        """
        import hashlib

        # Create unique ID from content hash
        doc_id = hashlib.md5(f"{session_id}:{filename}:{code}".encode()).hexdigest()

        # Create searchable document text
        doc_text = f"{description or ''}\n\nFilename: {filename}\nLanguage: {language}\n\n{code}"

        metadata = {
            "filename": filename,
            "language": language,
            "session_id": session_id,
            "type": "code_snippet"
        }
        if description:
            metadata["description"] = description

        self.add_documents(
            documents=[doc_text],
            ids=[doc_id],
            metadatas=[metadata]
        )

        return doc_id

    def search(
        self,
        query: str,
        n_results: int = 5,
        filter_metadata: Optional[Dict[str, Any]] = None
    ) -> List[SearchResult]:
        """Search for similar documents.

        Args:
            query: Search query
            n_results: Maximum number of results
            filter_metadata: Optional metadata filter

        Returns:
            List of search results
        """
        try:
            results = self.collection.query(
                query_texts=[query],
                n_results=n_results,
                where=filter_metadata
            )

            search_results = []
            if results and results['ids'] and results['ids'][0]:
                for i, doc_id in enumerate(results['ids'][0]):
                    search_results.append(SearchResult(
                        id=doc_id,
                        content=results['documents'][0][i] if results['documents'] else "",
                        metadata=results['metadatas'][0][i] if results['metadatas'] else {},
                        distance=results['distances'][0][i] if results['distances'] else 0.0
                    ))

            return search_results

        except Exception as e:
            logger.error(f"Search failed: {e}")
            return []

    def search_code(
        self,
        query: str,
        session_id: Optional[str] = None,
        language: Optional[str] = None,
        n_results: int = 5
    ) -> List[SearchResult]:
        """Search for code snippets.

        Args:
            query: Search query (natural language or code)
            session_id: Optional filter by session
            language: Optional filter by language
            n_results: Maximum number of results

        Returns:
            List of matching code snippets
        """
        filter_metadata = {"type": "code_snippet"}
        if session_id:
            filter_metadata["session_id"] = session_id
        if language:
            filter_metadata["language"] = language

        return self.search(query, n_results, filter_metadata)

    def delete_by_session(self, session_id: str) -> None:
        """Delete all documents for a session.

        Args:
            session_id: Session ID to delete
        """
        try:
            self.collection.delete(
                where={"session_id": session_id}
            )
            logger.info(f"Deleted documents for session: {session_id}")
        except Exception as e:
            logger.error(f"Failed to delete documents: {e}")

    def get_stats(self) -> Dict[str, Any]:
        """Get vector database statistics.

        Returns:
            Dictionary with stats
        """
        try:
            count = self.collection.count()
            return {
                "collection_name": self.collection_name,
                "document_count": count,
                "storage_path": CHROMA_DIR
            }
        except Exception as e:
            logger.error(f"Failed to get stats: {e}")
            return {"error": str(e)}


# Global instance
vector_db = VectorDBService()

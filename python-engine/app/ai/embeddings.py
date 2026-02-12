"""
Embedding service for vector search over tax regulation documents.
Uses sentence-transformers with multilingual support (Vietnamese).
"""

import logging

import chromadb
from chromadb.config import Settings as ChromaSettings

from app.config import settings

logger = logging.getLogger(__name__)


class EmbeddingService:
    """
    Manages vector embeddings using ChromaDB.
    Used for RAG - retrieving relevant tax regulations for user queries.
    """

    def __init__(self) -> None:
        self.client = chromadb.Client(ChromaSettings(
            chroma_db_impl="duckdb+parquet",
            persist_directory=settings.chroma_persist_dir,
            anonymized_telemetry=False,
        ))
        self.collection = self.client.get_or_create_collection(
            name="tax_regulations",
            metadata={"hnsw:space": "cosine"},
        )

    def add_document(
        self,
        doc_id: str,
        content: str,
        metadata: dict | None = None,
    ) -> None:
        """Add a document to the vector store."""
        self.collection.add(
            ids=[doc_id],
            documents=[content],
            metadatas=[metadata or {}],
        )
        logger.debug("Added document to vector store: %s", doc_id)

    def add_documents_batch(
        self,
        doc_ids: list[str],
        contents: list[str],
        metadatas: list[dict] | None = None,
    ) -> None:
        """Add multiple documents at once."""
        self.collection.add(
            ids=doc_ids,
            documents=contents,
            metadatas=metadatas or [{}] * len(doc_ids),
        )
        logger.info("Added %d documents to vector store", len(doc_ids))

    def search(
        self,
        query: str,
        n_results: int = 5,
        category_filter: str | None = None,
    ) -> list[dict]:
        """
        Search for relevant documents given a query.

        Returns list of dicts with keys: id, content, metadata, distance
        """
        where_filter = {"category": category_filter} if category_filter else None

        results = self.collection.query(
            query_texts=[query],
            n_results=n_results,
            where=where_filter,
        )

        documents = []
        if results and results["ids"]:
            for i, doc_id in enumerate(results["ids"][0]):
                documents.append({
                    "id": doc_id,
                    "content": results["documents"][0][i] if results["documents"] else "",
                    "metadata": results["metadatas"][0][i] if results["metadatas"] else {},
                    "distance": results["distances"][0][i] if results["distances"] else 0,
                })

        return documents

    def get_document_count(self) -> int:
        """Get total number of documents in the vector store."""
        return self.collection.count()

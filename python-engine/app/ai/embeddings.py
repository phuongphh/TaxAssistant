"""
Embedding service for vector search over tax regulation documents.
Uses Voyage AI API (voyage-multilingual-2) for multilingual embeddings.
"""

import logging

import chromadb
import voyageai

from app.config import settings

logger = logging.getLogger(__name__)


class EmbeddingService:
    """
    Manages vector embeddings using ChromaDB + Voyage AI API.
    Used for RAG - retrieving relevant tax regulations for user queries.

    voyage-multilingual-2 produces 1024-dimensional vectors.
    """

    def __init__(self) -> None:
        self._voyage = voyageai.AsyncClient(api_key=settings.voyage_api_key)
        self.client = chromadb.PersistentClient(
            path=settings.chroma_persist_dir,
        )
        self.collection = self.client.get_or_create_collection(
            name="tax_regulations",
            metadata={"hnsw:space": "cosine"},
        )

    async def _embed(self, texts: list[str]) -> list[list[float]]:
        """Call Voyage AI API to get embeddings for a list of texts."""
        result = await self._voyage.embed(
            texts,
            model=settings.embedding_model,
            input_type="document",
        )
        return result.embeddings

    async def _embed_query(self, query: str) -> list[list[float]]:
        """Call Voyage AI API with query input_type for better retrieval."""
        result = await self._voyage.embed(
            [query],
            model=settings.embedding_model,
            input_type="query",
        )
        return result.embeddings

    async def add_document(
        self,
        doc_id: str,
        content: str,
        metadata: dict | None = None,
    ) -> None:
        """Add a document to the vector store."""
        embeddings = await self._embed([content])
        self.collection.add(
            ids=[doc_id],
            embeddings=embeddings,
            documents=[content],
            metadatas=[metadata or {}],
        )
        logger.debug("Added document to vector store: %s", doc_id)

    async def add_documents_batch(
        self,
        doc_ids: list[str],
        contents: list[str],
        metadatas: list[dict] | None = None,
    ) -> None:
        """Add multiple documents at once."""
        embeddings = await self._embed(contents)
        self.collection.add(
            ids=doc_ids,
            embeddings=embeddings,
            documents=contents,
            metadatas=metadatas or [{}] * len(doc_ids),
        )
        logger.info("Added %d documents to vector store", len(doc_ids))

    async def search(
        self,
        query: str,
        n_results: int = 5,
        category_filter: str | None = None,
    ) -> list[dict]:
        """
        Search for relevant documents given a query.

        Returns list of dicts with keys: id, content, metadata, distance.
        Returns empty list on any ChromaDB error (empty collection, bad filter, etc).
        """
        # Skip search on empty collection to avoid ChromaDB errors
        if self.collection.count() == 0:
            return []

        # Cap n_results to actual collection size
        doc_count = self.collection.count()
        n_results = min(n_results, doc_count)

        query_embedding = await self._embed_query(query)
        where_filter = {"category": category_filter} if category_filter else None

        try:
            results = self.collection.query(
                query_embeddings=query_embedding,
                n_results=n_results,
                where=where_filter,
            )
        except Exception as e:
            # where_filter may fail if metadata field doesn't exist; retry without filter
            logger.warning("ChromaDB query with filter failed (%s), retrying without filter", e)
            try:
                results = self.collection.query(
                    query_embeddings=query_embedding,
                    n_results=n_results,
                )
            except Exception as e2:
                logger.error("ChromaDB query failed: %s", e2)
                return []

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

    def reset_collection(self) -> None:
        """Delete and recreate the ChromaDB collection. Used when switching embedding models."""
        logger.warning("Resetting ChromaDB collection 'tax_regulations'...")
        self.client.delete_collection("tax_regulations")
        self.collection = self.client.get_or_create_collection(
            name="tax_regulations",
            metadata={"hnsw:space": "cosine"},
        )
        logger.info("ChromaDB collection reset complete.")

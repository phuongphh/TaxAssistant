"""
RAG (Retrieval-Augmented Generation) service.
Combines vector search over tax regulations with LLM generation.
"""

import logging
from dataclasses import dataclass

from app.ai.embeddings import EmbeddingService
from app.ai.llm_client import LLMClient
from app.ai.prompts import TAX_CONSULTATION_PROMPT

logger = logging.getLogger(__name__)


@dataclass
class RAGResponse:
    answer: str
    sources: list[dict]
    confidence: float


class RAGService:
    """
    RAG pipeline:
    1. Embed user query
    2. Retrieve relevant tax regulation documents from vector store
    3. Pass retrieved context + query to LLM
    4. Return generated answer with source references
    """

    def __init__(self, embedding_service: EmbeddingService, llm_client: LLMClient) -> None:
        self.embeddings = embedding_service
        self.llm = llm_client

    async def query(
        self,
        question: str,
        customer_type: str = "",
        tax_category: str | None = None,
        n_results: int = 5,
    ) -> RAGResponse:
        """
        Process a tax question through the RAG pipeline.
        Returns a safe fallback response if any step fails.
        """
        try:
            return await self._do_query(question, customer_type, tax_category, n_results)
        except Exception as e:
            logger.exception("RAG query failed: %s", e)
            return RAGResponse(answer="", sources=[], confidence=0.0)

    async def _do_query(
        self,
        question: str,
        customer_type: str,
        tax_category: str | None,
        n_results: int,
    ) -> RAGResponse:
        """Internal RAG pipeline implementation."""
        # 1. Retrieve relevant documents
        logger.debug("RAG: searching ChromaDB (category=%s, n=%d)", tax_category, n_results)
        results = self.embeddings.search(
            query=question,
            n_results=n_results,
            category_filter=tax_category,
        )
        logger.debug("RAG: ChromaDB returned %d results", len(results))

        if not results:
            # No context available, try LLM knowledge only
            try:
                answer = await self.llm.generate_with_context(
                    query=question,
                    context_documents=[],
                    customer_type=customer_type,
                )
                return RAGResponse(answer=answer, sources=[], confidence=0.5)
            except Exception as e:
                logger.warning("RAG: LLM generation without context failed: %s", e)
                return RAGResponse(answer="", sources=[], confidence=0.0)

        # 2. Prepare context documents
        context_docs = []
        sources = []
        for doc in results:
            context_docs.append(doc["content"])
            sources.append({
                "title": doc["metadata"].get("document_number", ""),
                "snippet": doc["content"][:200],
                "url": doc["metadata"].get("source_url", ""),
            })

        # 3. Generate answer with context
        try:
            answer = await self.llm.generate_with_context(
                query=question,
                context_documents=context_docs,
                customer_type=customer_type,
                prompt_template=TAX_CONSULTATION_PROMPT,
            )
        except Exception as e:
            logger.warning("RAG: LLM generation with context failed: %s", e)
            # Return sources without LLM-generated answer so callers can still
            # use the retrieved documents for a rule-based response.
            return RAGResponse(answer="", sources=sources, confidence=0.3)

        # 4. Estimate confidence based on retrieval distances
        avg_distance = sum(d.get("distance", 1.0) for d in results) / len(results)
        confidence = max(0.3, min(0.95, 1.0 - avg_distance))

        return RAGResponse(
            answer=answer,
            sources=sources,
            confidence=confidence,
        )

    async def index_regulation(
        self,
        doc_id: str,
        content: str,
        metadata: dict,
    ) -> None:
        """Index a new tax regulation document for RAG retrieval."""
        # Split long documents into chunks for better retrieval
        chunks = self._chunk_text(content, chunk_size=500, overlap=50)

        doc_ids = [f"{doc_id}_chunk_{i}" for i in range(len(chunks))]
        metadatas = [metadata] * len(chunks)

        self.embeddings.add_documents_batch(doc_ids, chunks, metadatas)
        logger.info("Indexed regulation: %s (%d chunks)", doc_id, len(chunks))

    def _chunk_text(self, text: str, chunk_size: int = 500, overlap: int = 50) -> list[str]:
        """Split text into overlapping chunks for embedding."""
        words = text.split()
        chunks = []
        start = 0

        while start < len(words):
            end = start + chunk_size
            chunk = " ".join(words[start:end])
            chunks.append(chunk)
            start = end - overlap

        return chunks if chunks else [text]

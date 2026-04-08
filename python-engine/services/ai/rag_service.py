"""
RAG (Retrieval-Augmented Generation) service.
Combines vector search over tax regulations with LLM generation.
"""

import logging
from dataclasses import dataclass

from services.ai.embeddings import EmbeddingService
from services.ai.llm_client import LLMClient
from services.ai.prompts import TAX_CONSULTATION_PROMPT

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
        conversation_history: list[dict] | None = None,
        memory_context: str = "",
    ) -> RAGResponse:
        """
        Process a tax question through the RAG pipeline.
        Returns a safe fallback response if any step fails.

        Credit/auth errors from LLM are re-raised so callers can
        distinguish "LLM temporarily down" from "LLM permanently broken".
        """
        from services.ai.llm_client import LLMCreditError, LLMAuthError

        try:
            return await self._do_query(question, customer_type, tax_category, n_results, conversation_history, memory_context)
        except (LLMCreditError, LLMAuthError):
            # Permanent LLM errors: propagate so upstream can show a
            # specific message and avoid pointless retries.
            raise
        except Exception as e:
            logger.exception("RAG query failed: %s", e)
            return RAGResponse(answer="", sources=[], confidence=0.0)

    async def _do_query(
        self,
        question: str,
        customer_type: str,
        tax_category: str | None,
        n_results: int,
        conversation_history: list[dict] | None = None,
        memory_context: str = "",
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

        # Build enhanced system prompt with memory context
        system_prompt = None
        if memory_context:
            from services.ai.prompts import SYSTEM_PROMPT
            system_prompt = SYSTEM_PROMPT + "\n\n" + memory_context

        from services.ai.llm_client import LLMCreditError, LLMAuthError

        if not results:
            # No context available, try LLM knowledge only
            try:
                answer = await self.llm.generate_with_context(
                    query=question,
                    context_documents=[],
                    customer_type=customer_type,
                    conversation_history=conversation_history,
                    system_prompt=system_prompt,
                )
                return RAGResponse(answer=answer, sources=[], confidence=0.5)
            except (LLMCreditError, LLMAuthError):
                raise
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
        from services.ai.llm_client import LLMCreditError, LLMAuthError

        try:
            answer = await self.llm.generate_with_context(
                query=question,
                context_documents=context_docs,
                customer_type=customer_type,
                prompt_template=TAX_CONSULTATION_PROMPT,
                conversation_history=conversation_history,
                system_prompt=system_prompt,
            )
        except (LLMCreditError, LLMAuthError):
            # Permanent errors: build a document-based fallback instead of
            # returning empty, so the user still gets useful info.
            logger.warning("RAG: LLM unavailable (credit/auth), returning document-based fallback")
            fallback = self._build_document_fallback(question, sources, context_docs)
            return RAGResponse(answer=fallback, sources=sources, confidence=0.4)
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

    @staticmethod
    def _build_document_fallback(
        question: str,
        sources: list[dict],
        context_docs: list[str],
    ) -> str:
        """Build a readable fallback answer from retrieved documents when LLM is unavailable."""
        header = (
            "⚠️ Hệ thống AI tạm thời không khả dụng. "
            "Dưới đây là các tài liệu tham khảo liên quan đến câu hỏi của bạn:\n\n"
        )
        parts = []
        for i, (source, doc) in enumerate(zip(sources, context_docs), 1):
            title = source.get("title", f"Tài liệu {i}")
            snippet = doc[:300].strip()
            parts.append(f"📄 **{title}**\n{snippet}...")

        if not parts:
            return header + "Không tìm thấy tài liệu phù hợp. Vui lòng thử lại sau khi hệ thống khôi phục."

        footer = "\n\n💡 Để được tư vấn chi tiết hơn, vui lòng thử lại sau ít phút khi hệ thống AI khôi phục."
        return header + "\n\n".join(parts) + footer

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

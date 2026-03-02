"""
Conversation summarizer.

Generates concise summaries of conversation sessions using the LLM,
then stores them in the database for long-term memory.
"""

import logging
import uuid
from datetime import date

from app.ai.prompts import CONVERSATION_SUMMARY_PROMPT
from app.db.database import async_session
from app.db.summary_repository import SummaryRepository

logger = logging.getLogger(__name__)


async def summarize_and_store(
    customer_id: uuid.UUID,
    conversation_history: list[dict],
    support_case_id: uuid.UUID | None = None,
    llm_client=None,
) -> str | None:
    """Generate a summary of the conversation and store it in the DB.

    Args:
        customer_id: The customer UUID
        conversation_history: List of {"role": ..., "content": ...}
        support_case_id: Optional case this conversation belongs to
        llm_client: Optional LLMClient instance

    Returns:
        The summary text, or None if summarization failed/skipped.
    """
    if not conversation_history or len(conversation_history) < 4:
        # Too short to summarize
        return None

    # Build conversation text for the prompt
    conv_text = "\n".join(
        f"{'KH' if e.get('role') == 'user' else 'Bot'}: {e.get('content', '')}"
        for e in conversation_history[-20:]  # Last 20 messages max
    )

    summary = None

    if llm_client:
        try:
            prompt = CONVERSATION_SUMMARY_PROMPT.format(conversation=conv_text)
            summary = await llm_client.generate(
                user_prompt=prompt,
                max_tokens=300,
            )
            summary = summary.strip()
        except Exception as e:
            logger.warning("LLM summarization failed: %s", e)

    if not summary:
        # Fallback: simple extraction without LLM
        user_messages = [e["content"] for e in conversation_history if e.get("role") == "user"]
        summary = f"Khách hàng hỏi {len(user_messages)} câu hỏi. Nội dung: {'; '.join(m[:50] for m in user_messages[:3])}"

    # Store in DB
    try:
        async with async_session() as session:
            repo = SummaryRepository(session)
            # Extract key topics from the summary
            key_topics = _extract_topics(conversation_history)
            await repo.create(
                customer_id=customer_id,
                summary=summary,
                session_date=date.today(),
                support_case_id=support_case_id,
                key_topics=key_topics,
            )
            await session.commit()
        logger.info("Conversation summary stored for customer=%s", customer_id)
    except Exception as e:
        logger.warning("Failed to store conversation summary: %s", e)

    return summary


def _extract_topics(conversation_history: list[dict]) -> list[str]:
    """Extract key topic keywords from conversation."""
    topics = set()
    tax_keywords = {
        "gtgt": "vat", "vat": "vat",
        "tndn": "cit", "thu nhập doanh nghiệp": "cit",
        "tncn": "pit", "thu nhập cá nhân": "pit",
        "môn bài": "license_tax",
        "kê khai": "declaration",
        "quyết toán": "settlement",
        "đăng ký": "registration",
        "hóa đơn": "invoice",
        "hoàn thuế": "refund",
        "phạt": "penalty",
    }

    for entry in conversation_history:
        content = entry.get("content", "").lower()
        for keyword, topic in tax_keywords.items():
            if keyword in content:
                topics.add(topic)

    return list(topics)

"""
LLM client for Tax Assistant.
Wraps OpenAI-compatible API (can be swapped for local models).
"""

import logging

from openai import AsyncOpenAI

from app.config import settings
from app.ai.prompts import SYSTEM_PROMPT

logger = logging.getLogger(__name__)


class LLMClient:
    """Async LLM client using OpenAI API."""

    def __init__(self) -> None:
        self.client = AsyncOpenAI(api_key=settings.openai_api_key)
        self.model = settings.llm_model
        self.temperature = settings.llm_temperature

    async def generate(
        self,
        user_prompt: str,
        system_prompt: str = SYSTEM_PROMPT,
        max_tokens: int = 1024,
    ) -> str:
        """Generate a response from the LLM."""
        try:
            response = await self.client.chat.completions.create(
                model=self.model,
                messages=[
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": user_prompt},
                ],
                temperature=self.temperature,
                max_tokens=max_tokens,
            )
            return response.choices[0].message.content or ""
        except Exception as e:
            logger.error("LLM generation failed: %s", e)
            return "Xin lỗi, tôi gặp sự cố khi xử lý. Vui lòng thử lại."

    async def generate_with_context(
        self,
        query: str,
        context_documents: list[str],
        customer_type: str = "",
        prompt_template: str = "",
    ) -> str:
        """Generate a response with RAG context documents."""
        context_text = "\n\n---\n\n".join(context_documents) if context_documents else "Không có tài liệu tham khảo."

        if prompt_template:
            user_prompt = prompt_template.format(
                customer_type=customer_type,
                query=query,
                context_documents=context_text,
            )
        else:
            from app.ai.prompts import TAX_CONSULTATION_PROMPT
            user_prompt = TAX_CONSULTATION_PROMPT.format(
                customer_type=customer_type,
                query=query,
                context_documents=context_text,
            )

        return await self.generate(user_prompt)

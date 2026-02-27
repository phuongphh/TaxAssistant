"""
LLM client for Tax Assistant.
Wraps Anthropic Claude API for tax consultation and RAG.
"""

import logging

from anthropic import AsyncAnthropic
import httpx

from app.config import settings
from app.ai.prompts import SYSTEM_PROMPT

logger = logging.getLogger(__name__)

# LLM call must complete well within the gRPC deadline (15-30s)
_LLM_TIMEOUT_SECONDS = 12


class LLMClient:
    """Async LLM client using Anthropic Claude API."""

    def __init__(self) -> None:
        if not settings.anthropic_api_key:
            raise ValueError(
                "ANTHROPIC_API_KEY is not set. "
                "LLM features will be disabled."
            )
        self.client = AsyncAnthropic(
            api_key=settings.anthropic_api_key,
            timeout=httpx.Timeout(_LLM_TIMEOUT_SECONDS, connect=5.0),
        )
        self.model = settings.llm_model
        self.temperature = settings.llm_temperature
        logger.info(
            "LLM client initialized (model=%s, timeout=%ds)",
            self.model,
            _LLM_TIMEOUT_SECONDS,
        )

    async def generate(
        self,
        user_prompt: str,
        system_prompt: str = SYSTEM_PROMPT,
        max_tokens: int = 1024,
    ) -> str:
        """Generate a response from Claude."""
        try:
            logger.debug("LLM generate: model=%s, prompt_len=%d", self.model, len(user_prompt))
            response = await self.client.messages.create(
                model=self.model,
                system=system_prompt,
                messages=[
                    {"role": "user", "content": user_prompt},
                ],
                temperature=self.temperature,
                max_tokens=max_tokens,
            )
            answer = response.content[0].text
            logger.debug("LLM generate OK: response_len=%d", len(answer))
            return answer
        except Exception as e:
            logger.error("LLM generation failed: %s: %s", type(e).__name__, e)
            raise

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

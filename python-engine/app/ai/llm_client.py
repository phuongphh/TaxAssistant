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

# Anthropic API can take 15-25s for complex prompts.
# read timeout must fit within gRPC deadline (60s) with room for retries.
_LLM_READ_TIMEOUT = 45.0
_LLM_CONNECT_TIMEOUT = 10.0


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
            timeout=httpx.Timeout(_LLM_READ_TIMEOUT, connect=_LLM_CONNECT_TIMEOUT),
            max_retries=0,  # no SDK retries; we handle fallback at RAG/engine level
        )
        self.model = settings.llm_model
        self.temperature = settings.llm_temperature
        logger.info(
            "LLM client initialized (model=%s, read_timeout=%.0fs, max_retries=0)",
            self.model,
            _LLM_READ_TIMEOUT,
        )

    async def generate(
        self,
        user_prompt: str,
        system_prompt: str = SYSTEM_PROMPT,
        max_tokens: int = 1024,
        conversation_history: list[dict] | None = None,
    ) -> str:
        """Generate a response from Claude.

        Args:
            conversation_history: Previous turns as [{"role": "user"|"assistant", "content": str}, ...].
                These are prepended to the messages array so Claude sees the full conversation.
        """
        try:
            messages = self._build_messages(conversation_history, user_prompt)
            logger.debug(
                "LLM generate: model=%s, turns=%d, prompt_len=%d",
                self.model, len(messages), len(user_prompt),
            )
            response = await self.client.messages.create(
                model=self.model,
                system=system_prompt,
                messages=messages,
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
        conversation_history: list[dict] | None = None,
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

        return await self.generate(user_prompt, conversation_history=conversation_history)

    @staticmethod
    def _build_messages(
        conversation_history: list[dict] | None,
        current_prompt: str,
    ) -> list[dict]:
        """Build Claude messages array with conversation history.

        Ensures the messages array follows Claude's alternating user/assistant
        format and always starts with a user message.
        """
        messages: list[dict] = []

        if conversation_history:
            for entry in conversation_history:
                role = entry.get("role", "")
                content = entry.get("content", "")
                if role in ("user", "assistant") and content:
                    messages.append({"role": role, "content": content})

            # Claude requires messages to start with "user" role.
            # Drop leading assistant messages if any.
            while messages and messages[0]["role"] == "assistant":
                messages.pop(0)

            # Claude requires strict alternation: merge consecutive same-role msgs.
            merged: list[dict] = []
            for msg in messages:
                if merged and merged[-1]["role"] == msg["role"]:
                    merged[-1]["content"] += "\n" + msg["content"]
                else:
                    merged.append(msg)
            messages = merged

        # Append current user prompt
        if messages and messages[-1]["role"] == "user":
            # Merge with last user message to maintain alternation
            messages[-1]["content"] += "\n\n" + current_prompt
        else:
            messages.append({"role": "user", "content": current_prompt})

        return messages

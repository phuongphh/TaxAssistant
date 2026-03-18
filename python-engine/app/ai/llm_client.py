"""
LLM client for Tax Assistant.
Supports multiple LLM providers:
  - Anthropic Claude API (provider="anthropic")
  - OpenAI-compatible APIs like Z.AI GLM-5 (provider="openai_compatible")
"""

import asyncio
import logging

import httpx

from app.config import settings
from app.ai.prompts import SYSTEM_PROMPT

logger = logging.getLogger(__name__)

# LLM API can take 30-60s+ for complex prompts with conversation history.
# Total time budget must fit within gRPC deadline (180s) with room for
# overhead (DB queries, ChromaDB search, proto serialisation ≈ 10-20s).
#
# Budget:  60s per attempt × 2 attempts + 2s delay = ~122s  (leaves ~58s headroom)
# Previous: 120s × 4 attempts + 14s delays = ~494s → ALWAYS exceeded gRPC deadline!
_LLM_READ_TIMEOUT = 60.0
_LLM_CONNECT_TIMEOUT = 10.0

# Retry settings for transient errors (rate limit, server errors)
_MAX_RETRIES = 1  # 1 retry = 2 total attempts (fits within gRPC deadline)
_RETRY_BASE_DELAY = 2.0  # seconds, doubles each retry


class LLMError(Exception):
    """Base error for LLM-related failures."""

    def __init__(self, message: str, error_type: str = "unknown", retryable: bool = False):
        super().__init__(message)
        self.error_type = error_type
        self.retryable = retryable


class LLMCreditError(LLMError):
    """Raised when API credits are exhausted or billing issue occurs."""

    def __init__(self, message: str = "API credit exhausted or billing issue"):
        super().__init__(message, error_type="credit_exhausted", retryable=False)


class LLMAuthError(LLMError):
    """Raised when the API key is invalid or lacks permissions."""

    def __init__(self, message: str = "Invalid API key or insufficient permissions"):
        super().__init__(message, error_type="auth_error", retryable=False)


class LLMRateLimitError(LLMError):
    """Raised when rate-limited after exhausting retries."""

    def __init__(self, message: str = "Rate limited by API after retries"):
        super().__init__(message, error_type="rate_limited", retryable=True)


class LLMOverloadedError(LLMError):
    """Raised when the API is overloaded (529)."""

    def __init__(self, message: str = "API is temporarily overloaded"):
        super().__init__(message, error_type="overloaded", retryable=True)


class LLMClient:
    """Async LLM client supporting Anthropic and OpenAI-compatible APIs."""

    def __init__(self) -> None:
        self.provider = settings.llm_provider
        self.model = settings.llm_model
        self.temperature = settings.llm_temperature

        if self.provider == "anthropic":
            self._init_anthropic()
        elif self.provider == "openai_compatible":
            self._init_openai_compatible()
        else:
            raise ValueError(f"Unsupported LLM provider: {self.provider}")

        logger.info(
            "LLM client initialized (provider=%s, model=%s, read_timeout=%.0fs)",
            self.provider,
            self.model,
            _LLM_READ_TIMEOUT,
        )

    def _init_anthropic(self) -> None:
        if not settings.anthropic_api_key:
            raise ValueError("ANTHROPIC_API_KEY is not set.")
        from anthropic import AsyncAnthropic
        self._anthropic = AsyncAnthropic(
            api_key=settings.anthropic_api_key,
            timeout=httpx.Timeout(_LLM_READ_TIMEOUT, connect=_LLM_CONNECT_TIMEOUT),
            max_retries=0,
        )

    def _init_openai_compatible(self) -> None:
        if not settings.openai_api_key:
            raise ValueError(
                "OPENAI_API_KEY is not set. "
                "Required for OpenAI-compatible providers (Z.AI, etc.)."
            )
        from openai import AsyncOpenAI
        self._openai = AsyncOpenAI(
            api_key=settings.openai_api_key,
            base_url=settings.openai_base_url,
            timeout=httpx.Timeout(_LLM_READ_TIMEOUT, connect=_LLM_CONNECT_TIMEOUT),
            max_retries=0,
        )

    async def generate(
        self,
        user_prompt: str,
        system_prompt: str = SYSTEM_PROMPT,
        max_tokens: int = 2048,
        conversation_history: list[dict] | None = None,
    ) -> str:
        """Generate a response from the configured LLM provider.

        Raises:
            LLMCreditError: When API credits are exhausted (HTTP 400/402).
            LLMAuthError: When API key is invalid (HTTP 401/403).
            LLMRateLimitError: When rate-limited after all retries (HTTP 429).
            LLMOverloadedError: When API is overloaded after all retries (HTTP 529).
            LLMError: For other API failures.
        """
        messages = self._build_messages(conversation_history, user_prompt)
        logger.debug(
            "LLM generate: provider=%s, model=%s, turns=%d, prompt_len=%d",
            self.provider, self.model, len(messages), len(user_prompt),
        )

        if self.provider == "anthropic":
            return await self._generate_anthropic(messages, system_prompt, max_tokens)
        else:
            return await self._generate_openai(messages, system_prompt, max_tokens)

    async def _generate_anthropic(
        self,
        messages: list[dict],
        system_prompt: str,
        max_tokens: int,
    ) -> str:
        """Call Anthropic Claude API with retry logic."""
        from anthropic import APIStatusError, AuthenticationError, RateLimitError

        last_error: Exception | None = None

        for attempt in range(_MAX_RETRIES + 1):
            try:
                response = await self._anthropic.messages.create(
                    model=self.model,
                    system=system_prompt,
                    messages=messages,
                    temperature=self.temperature,
                    max_tokens=max_tokens,
                )
                answer = response.content[0].text
                logger.debug("LLM generate OK: response_len=%d", len(answer))
                return answer

            except AuthenticationError as e:
                logger.error("LLM auth error (status=%d): %s", e.status_code, e.message)
                raise LLMAuthError(f"Authentication failed: {e.message}") from e

            except RateLimitError as e:
                last_error = e
                if attempt < _MAX_RETRIES:
                    delay = _RETRY_BASE_DELAY * (2 ** attempt)
                    logger.warning("LLM rate limited (attempt %d/%d), retrying in %.1fs",
                                   attempt + 1, _MAX_RETRIES + 1, delay)
                    await asyncio.sleep(delay)
                    continue
                raise LLMRateLimitError() from e

            except APIStatusError as e:
                if e.status_code == 402 or (
                    e.status_code == 400
                    and any(kw in e.message.lower() for kw in ("credit", "balance", "billing", "payment", "insufficient"))
                ):
                    logger.error("LLM credit/billing error (status=%d): %s", e.status_code, e.message)
                    raise LLMCreditError(f"Credit/billing issue: {e.message}") from e

                if e.status_code in (429, 529) or e.status_code >= 500:
                    last_error = e
                    if attempt < _MAX_RETRIES:
                        delay = _RETRY_BASE_DELAY * (2 ** attempt)
                        logger.warning("LLM server error %d (attempt %d/%d), retrying in %.1fs",
                                       e.status_code, attempt + 1, _MAX_RETRIES + 1, delay)
                        await asyncio.sleep(delay)
                        continue
                    if e.status_code == 529:
                        raise LLMOverloadedError() from e

                logger.error("LLM API error (status=%d): %s", e.status_code, e.message)
                raise LLMError(f"API error {e.status_code}: {e.message}", error_type="api_error") from e

            except httpx.TimeoutException as e:
                last_error = e
                if attempt < _MAX_RETRIES:
                    delay = _RETRY_BASE_DELAY * (2 ** attempt)
                    logger.warning("LLM timeout (attempt %d/%d), retrying in %.1fs",
                                   attempt + 1, _MAX_RETRIES + 1, delay)
                    await asyncio.sleep(delay)
                    continue
                raise LLMError("Request timed out after retries", error_type="timeout", retryable=True) from e

            except Exception as e:
                logger.error("LLM unexpected error: %s: %s", type(e).__name__, e)
                raise LLMError(f"Unexpected: {type(e).__name__}: {e}") from e

        raise LLMError(f"Failed after {_MAX_RETRIES + 1} attempts: {last_error}", error_type="exhausted_retries")

    async def _generate_openai(
        self,
        messages: list[dict],
        system_prompt: str,
        max_tokens: int,
    ) -> str:
        """Call OpenAI-compatible API (Z.AI GLM-5, etc.) with retry logic."""
        from openai import APIStatusError, AuthenticationError, RateLimitError

        # OpenAI format: system prompt goes as a system message
        openai_messages = [{"role": "system", "content": system_prompt}] + messages
        last_error: Exception | None = None

        for attempt in range(_MAX_RETRIES + 1):
            try:
                response = await self._openai.chat.completions.create(
                    model=self.model,
                    messages=openai_messages,
                    temperature=self.temperature,
                    max_tokens=max_tokens,
                )
                answer = response.choices[0].message.content or ""
                logger.debug("LLM generate OK: response_len=%d", len(answer))
                return answer

            except AuthenticationError as e:
                logger.error("LLM auth error (status=%d): %s", e.status_code, e.message)
                raise LLMAuthError(f"Authentication failed: {e.message}") from e

            except RateLimitError as e:
                last_error = e
                if attempt < _MAX_RETRIES:
                    delay = _RETRY_BASE_DELAY * (2 ** attempt)
                    logger.warning("LLM rate limited (attempt %d/%d), retrying in %.1fs",
                                   attempt + 1, _MAX_RETRIES + 1, delay)
                    await asyncio.sleep(delay)
                    continue
                raise LLMRateLimitError() from e

            except APIStatusError as e:
                if e.status_code == 402 or (
                    e.status_code == 400
                    and any(kw in e.message.lower() for kw in ("credit", "balance", "billing", "payment", "insufficient", "quota"))
                ):
                    logger.error("LLM credit/billing error (status=%d): %s", e.status_code, e.message)
                    raise LLMCreditError(f"Credit/billing issue: {e.message}") from e

                if e.status_code in (429, 529) or e.status_code >= 500:
                    last_error = e
                    if attempt < _MAX_RETRIES:
                        delay = _RETRY_BASE_DELAY * (2 ** attempt)
                        logger.warning("LLM server error %d (attempt %d/%d), retrying in %.1fs",
                                       e.status_code, attempt + 1, _MAX_RETRIES + 1, delay)
                        await asyncio.sleep(delay)
                        continue
                    if e.status_code == 529:
                        raise LLMOverloadedError() from e

                logger.error("LLM API error (status=%d): %s", e.status_code, e.message)
                raise LLMError(f"API error {e.status_code}: {e.message}", error_type="api_error") from e

            except httpx.TimeoutException as e:
                last_error = e
                if attempt < _MAX_RETRIES:
                    delay = _RETRY_BASE_DELAY * (2 ** attempt)
                    logger.warning("LLM timeout (attempt %d/%d), retrying in %.1fs",
                                   attempt + 1, _MAX_RETRIES + 1, delay)
                    await asyncio.sleep(delay)
                    continue
                raise LLMError("Request timed out after retries", error_type="timeout", retryable=True) from e

            except Exception as e:
                logger.error("LLM unexpected error: %s: %s", type(e).__name__, e)
                raise LLMError(f"Unexpected: {type(e).__name__}: {e}") from e

        raise LLMError(f"Failed after {_MAX_RETRIES + 1} attempts: {last_error}", error_type="exhausted_retries")

    async def generate_with_context(
        self,
        query: str,
        context_documents: list[str],
        customer_type: str = "",
        prompt_template: str = "",
        conversation_history: list[dict] | None = None,
        system_prompt: str | None = None,
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

        kwargs: dict = {"conversation_history": conversation_history}
        if system_prompt:
            kwargs["system_prompt"] = system_prompt
        return await self.generate(user_prompt, **kwargs)

    @staticmethod
    def _build_messages(
        conversation_history: list[dict] | None,
        current_prompt: str,
    ) -> list[dict]:
        """Build messages array with conversation history.

        Ensures the messages array follows the alternating user/assistant
        format and always starts with a user message.
        """
        messages: list[dict] = []

        if conversation_history:
            for entry in conversation_history:
                role = entry.get("role", "")
                content = entry.get("content", "")
                if role in ("user", "assistant") and content:
                    messages.append({"role": role, "content": content})

            # Messages must start with "user" role.
            # Drop leading assistant messages if any.
            while messages and messages[0]["role"] == "assistant":
                messages.pop(0)

            # Strict alternation: merge consecutive same-role msgs.
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

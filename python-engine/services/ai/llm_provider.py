"""
Abstract LLM provider interface for the Tax Assistant.

Allows injection of different LLM backends (Anthropic Claude, OpenAI-compatible,
local LLMs) without changing orchestration logic.
"""

from abc import ABC, abstractmethod


class LLMProvider(ABC):
    """Abstract interface for LLM providers.

    Implementations: LLMClient (Anthropic + OpenAI-compatible).
    """

    @abstractmethod
    async def generate(
        self,
        user_prompt: str,
        system_prompt: str = "",
        max_tokens: int = 2048,
        conversation_history: list[dict] | None = None,
    ) -> str:
        """Generate a response from the LLM.

        Args:
            user_prompt: The user's input prompt.
            system_prompt: Optional system/instruction prompt.
            max_tokens: Maximum tokens in response.
            conversation_history: Prior turns as [{"role": "user"|"assistant", "content": str}].

        Returns:
            Generated text response.

        Raises:
            LLMError: On API failures.
        """
        ...

    @abstractmethod
    async def generate_with_context(
        self,
        query: str,
        context_documents: list[str],
        customer_type: str = "",
        prompt_template: str = "",
        conversation_history: list[dict] | None = None,
        system_prompt: str | None = None,
    ) -> str:
        """Generate a response enriched with RAG context documents.

        Args:
            query: The user's question.
            context_documents: Retrieved regulation documents to inject.
            customer_type: Customer segment (sme, household, individual).
            prompt_template: Optional template string with {query}/{context_documents} placeholders.
            conversation_history: Prior turns.
            system_prompt: Override the default system prompt.

        Returns:
            Generated text response.
        """
        ...

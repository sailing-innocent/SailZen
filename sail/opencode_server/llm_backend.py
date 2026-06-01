# -*- coding: utf-8 -*-
# @file llm_backend.py
# @brief LLM backend abstraction + Moonshot (Kimi) and Mock implementations.
# @author sailing-innocent
# @date 2026-05-31
# @version 1.0
# ---------------------------------

from __future__ import annotations

import asyncio
import logging
from abc import ABC, abstractmethod
from typing import AsyncIterator, Optional

logger = logging.getLogger(__name__)


class LLMBackend(ABC):
    """Abstract backend that turns a prompt into streamed text chunks."""

    @abstractmethod
    async def complete_stream(
        self, session_id: str, prompt: str
    ) -> AsyncIterator[str]:
        """Yield text chunks (tokens / sentences) for *prompt*."""
        ...


class MockBackend(LLMBackend):
    """Mock backend that yields a canned response in chunks.

    Useful for unit / e2e tests without burning real API keys.
    """

    def __init__(self, response_text: Optional[str] = None) -> None:
        self.response_text = response_text or (
            "Hello! I am a mock LLM. This is a streamed response "
            "for testing the opencode-compatible dummy server."
        )

    async def complete_stream(
        self, session_id: str, prompt: str
    ) -> AsyncIterator[str]:
        # Give clients a moment to connect to the SSE stream before emitting
        await asyncio.sleep(0.15)
        # Split into ~10-character chunks to exercise streaming
        chunk_size = 10
        for i in range(0, len(self.response_text), chunk_size):
            chunk = self.response_text[i : i + chunk_size]
            await asyncio.sleep(0.01)  # tiny delay to mimic latency
            yield chunk


class MoonshotBackend(LLMBackend):
    """Backend using ``sail.llm`` Moonshot (Kimi) provider.

    Requires ``MOONSHOT_API_KEY`` in the environment.
    """

    def __init__(self, model: Optional[str] = None) -> None:
        self._model = model or "kimi-k2.5"
        self._gateway = None
        self._provider_name = "moonshot"

    def _ensure_gateway(self):
        if self._gateway is not None:
            return
        from sail.llm.gateway import LLMGateway
        from sail.llm.providers import ProviderConfig
        import os

        api_key = os.getenv("MOONSHOT_API_KEY")
        if not api_key:
            raise RuntimeError(
                "MOONSHOT_API_KEY not set — cannot use MoonshotBackend"
            )

        self._gateway = LLMGateway()
        self._gateway.register_provider(
            self._provider_name,
            ProviderConfig(
                provider_name=self._provider_name,
                model=self._model,
                api_key=api_key,
                api_base=os.getenv("MOONSHOT_API_BASE", "https://api.moonshot.cn/v1"),
                temperature=1.0,
                max_tokens=4096,
            ),
        )

    async def complete_stream(
        self, session_id: str, prompt: str
    ) -> AsyncIterator[str]:
        self._ensure_gateway()
        from sail.llm.gateway import LLMExecutionConfig

        config = LLMExecutionConfig(
            provider=self._provider_name,
            model=self._model,
            temperature=1.0,
            max_tokens=4096,
            enable_streaming=True,
        )
        # Gateway.execute is async but not streaming; use provider directly
        provider = self._gateway._providers.get(self._provider_name)
        if provider is None:
            raise RuntimeError("Moonshot provider not registered")

        # BaseProvider.complete_stream yields str chunks
        async for chunk in provider.complete_stream(prompt):
            yield chunk

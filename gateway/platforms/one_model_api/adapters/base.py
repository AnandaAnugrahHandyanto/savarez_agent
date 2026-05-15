"""Base protocol adapter interface for API Server passthrough mode."""

from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Any, ClassVar, Mapping

from aiohttp import web


class PassthroughProtocolAdapter(ABC):
    """Protocol-only adapter for the one-model API passthrough surface.

    Adapters translate between the public OpenAI-compatible API surface and an
    already-resolved Hermes upstream runtime. They must not select accounts,
    persist credentials, maintain cooldown tables, or implement failover pools.
    """

    protocol: ClassVar[str]
    api_modes: ClassVar[set[str]]

    @classmethod
    def supports_runtime(cls, runtime: Mapping[str, Any]) -> bool:
        api_mode = str(runtime.get("api_mode") or "").strip().lower()
        return api_mode in cls.api_modes or (not api_mode and "" in cls.api_modes)

    @abstractmethod
    async def chat_completion(
        self,
        *,
        server: Any,
        request: web.Request,
        client: Any,
        runtime: Mapping[str, Any],
        payload: dict[str, Any],
        requested_model: str,
    ) -> web.Response:
        """Handle public POST /v1/chat/completions."""

    @abstractmethod
    async def responses(
        self,
        *,
        server: Any,
        request: web.Request,
        client: Any,
        runtime: Mapping[str, Any],
        body: dict[str, Any],
        chat_payload: dict[str, Any],
        requested_model: str,
    ) -> web.Response:
        """Handle public POST /v1/responses."""

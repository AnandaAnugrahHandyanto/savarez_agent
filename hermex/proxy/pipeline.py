from __future__ import annotations

import asyncio
from collections.abc import AsyncIterator, Callable
from typing import Any

import httpx

from hermex.core.session import SessionFingerprintor
from hermex.core.store.base import CoreStore
from hermex.proxy.stages.ambient import AmbientContextInjector
from hermex.proxy.trace import TraceExtractor


class ProxyPipeline:
    def __init__(
        self,
        store: CoreStore,
        upstream_base: str,
        api_key: str,
        http_client_factory: Callable[[], httpx.AsyncClient] | None = None,
    ) -> None:
        self._store = store
        self._upstream_base = upstream_base.rstrip("/")
        self._api_key = api_key
        self._fingerprint = SessionFingerprintor()
        self._ambient = AmbientContextInjector(store)
        self._tracer = TraceExtractor(store)
        self._http_client_factory = http_client_factory or (
            lambda: httpx.AsyncClient(timeout=httpx.Timeout(connect=15.0, read=600.0, write=30.0, pool=30.0))
        )

    async def handle(self, raw_body: dict[str, Any]) -> AsyncIterator[bytes]:
        session_id = self._fingerprint.derive(raw_body)
        session = await self._store.sessions.load_or_create(session_id)
        body = await self._ambient.process(dict(raw_body), session)
        buffer: list[bytes] = []

        async with self._http_client_factory() as client:
            async with client.stream(
                "POST",
                f"{self._upstream_base}/v1/messages",
                headers=self._headers(),
                json=body,
            ) as response:
                async for chunk in response.aiter_bytes():
                    buffer.append(chunk)
                    yield chunk

        asyncio.create_task(self._tracer.process(b"".join(buffer), session_id=session_id))

    def _headers(self) -> dict[str, str]:
        return {
            "x-api-key": self._api_key,
            "authorization": f"Bearer {self._api_key}",
            "anthropic-version": "2023-06-01",
            "content-type": "application/json",
        }

"""OpenAI-compatible Chat Completions upstream adapter."""

from __future__ import annotations

from typing import Any, ClassVar, Mapping

from aiohttp import web

from ..conversions import apply_stop_to_chat_data, chat_to_response_payload
from ..streams import stream_openai_chat_as_chat_sse, stream_openai_chat_as_responses_sse
from .base import PassthroughProtocolAdapter


_UNSUPPORTED_UPSTREAM_PARAMS = {"temperature", "top_p"}


def _sanitize_chat_payload(payload: dict[str, Any]) -> dict[str, Any]:
    clean = dict(payload)
    for key in _UNSUPPORTED_UPSTREAM_PARAMS:
        clean.pop(key, None)
    return clean


class OpenAIChatAdapter(PassthroughProtocolAdapter):
    """Adapter for upstreams that already speak OpenAI Chat Completions."""

    protocol: ClassVar[str] = "openai_chat"
    api_modes: ClassVar[set[str]] = {"", "chat_completions", "openai", "openai_compatible"}

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
        stop = payload.get("stop")
        payload = _sanitize_chat_payload(payload)
        if bool(payload.get("stream", False)):
            return await stream_openai_chat_as_chat_sse(
                request,
                client=client,
                payload=payload,
                requested_model=requested_model,
                stop=stop,
            )

        response = await client.chat.completions.create(**payload)
        data = response.model_dump(exclude_none=True) if hasattr(response, "model_dump") else dict(response)
        if requested_model:
            data["model"] = requested_model
        data = apply_stop_to_chat_data(data, stop)
        return web.json_response(data)

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
        chat_payload = _sanitize_chat_payload(chat_payload)
        if bool(body.get("stream", False)):
            return await stream_openai_chat_as_responses_sse(
                request,
                client=client,
                chat_payload=chat_payload,
                requested_model=requested_model,
                default_model=server._model_name,
            )

        chat_payload["stream"] = False
        response = await client.chat.completions.create(**chat_payload)
        chat_data = response.model_dump(exclude_none=True) if hasattr(response, "model_dump") else dict(response)
        return web.json_response(
            chat_to_response_payload(chat_data, requested_model, default_model=server._model_name)
        )

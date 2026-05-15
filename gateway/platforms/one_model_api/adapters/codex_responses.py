"""Codex/OpenAI Responses upstream adapter."""

from __future__ import annotations

from typing import Any, ClassVar, Mapping

from aiohttp import web

from ..conversions import (
    chat_payload_to_codex_responses_kwargs,
    codex_to_chat_payload,
    codex_to_response_payload,
    collect_codex_stream,
)
from ..streams import stream_codex_as_chat_sse, stream_codex_as_responses_sse
from .base import PassthroughProtocolAdapter


class CodexResponsesAdapter(PassthroughProtocolAdapter):
    """Adapter for Hermes runtimes using api_mode=codex_responses."""

    protocol: ClassVar[str] = "codex_responses"
    api_modes: ClassVar[set[str]] = {"codex_responses"}

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
        try:
            codex_kwargs = chat_payload_to_codex_responses_kwargs(
                payload,
                runtime=runtime,
                default_model=server._model_name,
                stream=True,
            )
        except ValueError as exc:
            return web.json_response(server._openai_error(str(exc), code="unsupported_feature"), status=400)

        if bool(payload.get("stream", False)):
            return await stream_codex_as_chat_sse(
                request,
                client=client,
                codex_kwargs=codex_kwargs,
                requested_model=requested_model,
                default_model=server._model_name,
                stop=payload.get("stop"),
            )

        response = await collect_codex_stream(client, codex_kwargs)
        return web.json_response(
            codex_to_chat_payload(
                response,
                requested_model=requested_model,
                default_model=server._model_name,
                stop=payload.get("stop"),
                tool_choice=payload.get("tool_choice") or payload.get("function_call"),
                tools=codex_kwargs.get("tools"),
            )
        )

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
        try:
            codex_kwargs = chat_payload_to_codex_responses_kwargs(
                chat_payload,
                runtime=runtime,
                default_model=server._model_name,
                stream=True,
            )
        except ValueError as exc:
            return web.json_response(server._openai_error(str(exc), code="unsupported_feature"), status=400)

        if bool(body.get("stream", False)):
            return await stream_codex_as_responses_sse(
                request,
                client=client,
                codex_kwargs=codex_kwargs,
                requested_model=requested_model,
                default_model=server._model_name,
            )

        response = await collect_codex_stream(client, codex_kwargs)
        return web.json_response(
            codex_to_response_payload(
                response,
                requested_model=requested_model,
                default_model=server._model_name,
                stop=chat_payload.get("stop"),
            )
        )

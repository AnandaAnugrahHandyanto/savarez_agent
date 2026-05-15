"""SSE stream translators for the one-model API passthrough layer."""

from __future__ import annotations

import json
import logging
import time
from typing import Any

from aiohttp import web

from .conversions import chat_completion_id, make_id, response_to_dict

logger = logging.getLogger(__name__)


def sse_event(event: str, data: dict[str, Any]) -> bytes:
    payload = json.dumps(data, ensure_ascii=False)
    return f"event: {event}\ndata: {payload}\n\n".encode("utf-8")


def openai_error(message: str, type_: str = "invalid_request_error", code: str | None = None) -> dict[str, Any]:
    error: dict[str, Any] = {"message": message, "type": type_}
    if code:
        error["code"] = code
    return {"error": error}


def _sse_headers() -> dict[str, str]:
    return {
        "Content-Type": "text/event-stream",
        "Cache-Control": "no-cache",
        "Connection": "keep-alive",
        "X-Accel-Buffering": "no",
    }


async def stream_openai_chat_as_chat_sse(
    request: web.Request,
    *,
    client: Any,
    payload: dict[str, Any],
    requested_model: str,
) -> web.StreamResponse:
    """Stream upstream OpenAI-compatible chunks as Chat Completions SSE."""
    response = web.StreamResponse(status=200, headers=_sse_headers())
    await response.prepare(request)
    try:
        stream = await client.chat.completions.create(**payload)
        async for chunk in stream:
            data = chunk.model_dump(exclude_none=True) if hasattr(chunk, "model_dump") else dict(chunk)
            if requested_model:
                data["model"] = requested_model
            await response.write(f"data: {json.dumps(data, ensure_ascii=False)}\n\n".encode("utf-8"))
        await response.write(b"data: [DONE]\n\n")
    except Exception as exc:
        logger.exception("Passthrough streaming chat completion failed")
        err = openai_error(f"Passthrough upstream stream failed: {exc}", code="upstream_stream_failed")
        await response.write(f"data: {json.dumps(err, ensure_ascii=False)}\n\n".encode("utf-8"))
        await response.write(b"data: [DONE]\n\n")
    finally:
        try:
            await response.write_eof()
        except Exception:
            pass
    return response


async def stream_codex_as_chat_sse(
    request: web.Request,
    *,
    client: Any,
    codex_kwargs: dict[str, Any],
    requested_model: str,
    default_model: str,
) -> web.StreamResponse:
    """Stream a Codex Responses upstream as OpenAI Chat Completions SSE."""
    response = web.StreamResponse(status=200, headers=_sse_headers())
    await response.prepare(request)
    completion_id = chat_completion_id()
    created = int(time.time())
    try:
        stream = await client.responses.create(**codex_kwargs)
        async for event in stream:
            event_type = getattr(event, "type", None)
            if not event_type and isinstance(event, dict):
                event_type = event.get("type")
            piece = ""
            if event_type == "response.output_text.delta":
                piece = getattr(event, "delta", "")
                if not piece and isinstance(event, dict):
                    piece = event.get("delta", "") or ""
            elif event_type == "response.failed":
                data = response_to_dict(event)
                await response.write(
                    f"data: {json.dumps(openai_error(str(data), code='upstream_response_failed'), ensure_ascii=False)}\n\n".encode("utf-8")
                )
                break
            if not piece:
                continue
            chunk = {
                "id": completion_id,
                "object": "chat.completion.chunk",
                "created": created,
                "model": requested_model or default_model,
                "choices": [{"index": 0, "delta": {"content": piece}, "finish_reason": None}],
            }
            await response.write(f"data: {json.dumps(chunk, ensure_ascii=False)}\n\n".encode("utf-8"))

        done_chunk = {
            "id": completion_id,
            "object": "chat.completion.chunk",
            "created": created,
            "model": requested_model or default_model,
            "choices": [{"index": 0, "delta": {}, "finish_reason": "stop"}],
        }
        await response.write(f"data: {json.dumps(done_chunk, ensure_ascii=False)}\n\n".encode("utf-8"))
        await response.write(b"data: [DONE]\n\n")
    except Exception as exc:
        logger.exception("Passthrough Codex streaming chat completion failed")
        err = openai_error(f"Passthrough Codex upstream stream failed: {exc}", code="upstream_stream_failed")
        await response.write(f"data: {json.dumps(err, ensure_ascii=False)}\n\n".encode("utf-8"))
        await response.write(b"data: [DONE]\n\n")
    finally:
        try:
            await response.write_eof()
        except Exception:
            pass
    return response


async def stream_codex_as_responses_sse(
    request: web.Request,
    *,
    client: Any,
    codex_kwargs: dict[str, Any],
    requested_model: str,
    default_model: str,
) -> web.StreamResponse:
    """Stream a Codex Responses upstream as minimal OpenAI Responses SSE."""
    response_id = make_id("resp")
    message_id = make_id("msg")
    created_at = int(time.time())
    sse_resp = web.StreamResponse(status=200, headers=_sse_headers())
    await sse_resp.prepare(request)
    full_text = ""
    try:
        await sse_resp.write(sse_event("response.created", {
            "type": "response.created",
            "response": {
                "id": response_id,
                "object": "response",
                "created_at": created_at,
                "status": "in_progress",
                "model": requested_model or default_model,
                "output": [],
            },
        }))
        await sse_resp.write(sse_event("response.output_item.added", {
            "type": "response.output_item.added",
            "response_id": response_id,
            "output_index": 0,
            "item": {"id": message_id, "type": "message", "status": "in_progress", "role": "assistant", "content": []},
        }))

        stream = await client.responses.create(**codex_kwargs)
        async for event in stream:
            event_type = getattr(event, "type", None)
            if not event_type and isinstance(event, dict):
                event_type = event.get("type")
            if event_type == "response.output_text.delta":
                piece = getattr(event, "delta", "")
                if not piece and isinstance(event, dict):
                    piece = event.get("delta", "") or ""
                if not piece:
                    continue
                full_text += piece
                await sse_resp.write(sse_event("response.output_text.delta", {
                    "type": "response.output_text.delta",
                    "response_id": response_id,
                    "item_id": message_id,
                    "output_index": 0,
                    "content_index": 0,
                    "delta": piece,
                }))
            elif event_type == "response.failed":
                data = response_to_dict(event)
                await sse_resp.write(sse_event("response.failed", {
                    "type": "response.failed",
                    "response": {
                        "id": response_id,
                        "object": "response",
                        "created_at": created_at,
                        "status": "failed",
                        "model": requested_model or default_model,
                        "error": {"message": json.dumps(data, ensure_ascii=False), "type": "upstream_error"},
                    },
                }))
                return sse_resp

        await sse_resp.write(sse_event("response.output_text.done", {
            "type": "response.output_text.done",
            "response_id": response_id,
            "item_id": message_id,
            "output_index": 0,
            "content_index": 0,
            "text": full_text,
        }))
        await sse_resp.write(sse_event("response.completed", {
            "type": "response.completed",
            "response": _completed_response(response_id, message_id, created_at, requested_model or default_model, full_text),
        }))
    except Exception as exc:
        logger.exception("Passthrough Codex streaming responses failed")
        await sse_resp.write(sse_event("response.failed", {
            "type": "response.failed",
            "response": {
                "id": response_id,
                "object": "response",
                "created_at": created_at,
                "status": "failed",
                "model": requested_model or default_model,
                "error": {"message": str(exc), "type": "upstream_stream_failed"},
            },
        }))
    finally:
        try:
            await sse_resp.write_eof()
        except Exception:
            pass
    return sse_resp


async def stream_openai_chat_as_responses_sse(
    request: web.Request,
    *,
    client: Any,
    chat_payload: dict[str, Any],
    requested_model: str,
    default_model: str,
) -> web.StreamResponse:
    """Stream OpenAI chat chunks as minimal OpenAI Responses SSE."""
    response_id = make_id("resp")
    message_id = make_id("msg")
    created_at = int(time.time())
    sse_resp = web.StreamResponse(status=200, headers=_sse_headers())
    await sse_resp.prepare(request)
    try:
        await sse_resp.write(sse_event("response.created", {
            "type": "response.created",
            "response": {
                "id": response_id,
                "object": "response",
                "created_at": created_at,
                "status": "in_progress",
                "model": requested_model or default_model,
                "output": [],
            },
        }))
        await sse_resp.write(sse_event("response.output_item.added", {
            "type": "response.output_item.added",
            "response_id": response_id,
            "output_index": 0,
            "item": {"id": message_id, "type": "message", "status": "in_progress", "role": "assistant", "content": []},
        }))

        full_text = ""
        stream = await client.chat.completions.create(**chat_payload)
        async for chunk in stream:
            chunk_data = chunk.model_dump(exclude_none=True) if hasattr(chunk, "model_dump") else dict(chunk)
            choices = chunk_data.get("choices") or []
            if not choices:
                continue
            delta = choices[0].get("delta") or {}
            piece = delta.get("content")
            if not piece:
                continue
            full_text += piece
            await sse_resp.write(sse_event("response.output_text.delta", {
                "type": "response.output_text.delta",
                "response_id": response_id,
                "item_id": message_id,
                "output_index": 0,
                "content_index": 0,
                "delta": piece,
            }))

        await sse_resp.write(sse_event("response.output_text.done", {
            "type": "response.output_text.done",
            "response_id": response_id,
            "item_id": message_id,
            "output_index": 0,
            "content_index": 0,
            "text": full_text,
        }))
        await sse_resp.write(sse_event("response.completed", {
            "type": "response.completed",
            "response": _completed_response(response_id, message_id, created_at, requested_model or default_model, full_text),
        }))
    except Exception as exc:
        logger.exception("Passthrough streaming responses failed")
        await sse_resp.write(sse_event("response.failed", {
            "type": "response.failed",
            "response": {
                "id": response_id,
                "object": "response",
                "created_at": created_at,
                "status": "failed",
                "model": requested_model or default_model,
                "error": {"message": str(exc), "type": "upstream_error"},
            },
        }))
    finally:
        try:
            await sse_resp.write_eof()
        except Exception:
            pass
    return sse_resp


def _completed_response(response_id: str, message_id: str, created_at: int, model: str, text: str) -> dict[str, Any]:
    return {
        "id": response_id,
        "object": "response",
        "created_at": created_at,
        "status": "completed",
        "model": model,
        "output": [
            {
                "id": message_id,
                "type": "message",
                "status": "completed",
                "role": "assistant",
                "content": [{"type": "output_text", "text": text, "annotations": []}],
            }
        ],
        "output_text": text,
    }

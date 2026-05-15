"""SSE stream translators for the one-model API passthrough layer."""

from __future__ import annotations

import json
import logging
import time
from typing import Any

from aiohttp import web

from .conversions import chat_completion_id, forced_tool_call_fallback, make_id, response_to_dict, truncate_at_stop_sequence

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


def _stop_sequences(stop: Any) -> list[str]:
    if isinstance(stop, str):
        return [stop] if stop else []
    if isinstance(stop, list):
        return [seq for seq in stop if isinstance(seq, str) and seq]
    return []


def _stream_stop_filter_piece(piece: str, state: dict[str, Any], stop: Any) -> str:
    """Return safe text to emit while holding a tail for split stop sequences."""
    if not piece or state.get("stop_seen"):
        return ""
    sequences = _stop_sequences(stop)
    if not sequences:
        return piece

    pending = str(state.get("stop_pending", "")) + piece
    earliest = -1
    for seq in sequences:
        pos = pending.find(seq)
        if pos >= 0 and (earliest < 0 or pos < earliest):
            earliest = pos
    if earliest >= 0:
        state["stop_seen"] = True
        state["stop_pending"] = ""
        return pending[:earliest]

    hold = max(len(seq) for seq in sequences) - 1
    if hold <= 0:
        state["stop_pending"] = ""
        return pending
    if len(pending) <= hold:
        state["stop_pending"] = pending
        return ""
    state["stop_pending"] = pending[-hold:]
    return pending[:-hold]


def _stream_stop_flush(state: dict[str, Any], stop: Any) -> str:
    if state.get("stop_seen") or not _stop_sequences(stop):
        state["stop_pending"] = ""
        return ""
    pending = str(state.get("stop_pending", ""))
    state["stop_pending"] = ""
    return truncate_at_stop_sequence(pending, stop)


async def stream_openai_chat_as_chat_sse(
    request: web.Request,
    *,
    client: Any,
    payload: dict[str, Any],
    requested_model: str,
    stop: Any = None,
) -> web.StreamResponse:
    """Stream upstream OpenAI-compatible chunks as Chat Completions SSE."""
    try:
        stream = await client.chat.completions.create(**payload)
    except Exception as exc:
        logger.exception("Passthrough streaming chat completion failed before SSE started")
        err = openai_error(f"Passthrough upstream stream failed: {exc}", code="upstream_stream_failed")
        return web.json_response(err, status=502)

    iterator = stream.__aiter__()
    try:
        first_chunk = await iterator.__anext__()
    except StopAsyncIteration:
        first_chunk = None
    except Exception as exc:
        logger.exception("Passthrough streaming chat completion failed before SSE started")
        err = openai_error(f"Passthrough upstream stream failed: {exc}", code="upstream_stream_failed")
        return web.json_response(err, status=502)

    response = web.StreamResponse(status=200, headers=_sse_headers())
    await response.prepare(request)
    stop_state: dict[str, Any] = {}

    async def write_filtered_chunk(chunk_obj: Any) -> None:
        data = chunk_obj.model_dump(exclude_none=True) if hasattr(chunk_obj, "model_dump") else dict(chunk_obj)
        if requested_model:
            data["model"] = requested_model
        choices = data.get("choices")
        if isinstance(choices, list):
            new_choices = []
            for choice in choices:
                if not isinstance(choice, dict):
                    new_choices.append(choice)
                    continue
                new_choice = dict(choice)
                delta = new_choice.get("delta")
                if isinstance(delta, dict) and isinstance(delta.get("content"), str):
                    filtered = _stream_stop_filter_piece(delta.get("content") or "", stop_state, stop)
                    if filtered:
                        new_delta = dict(delta)
                        new_delta["content"] = filtered
                        new_choice["delta"] = new_delta
                        new_choices.append(new_choice)
                    continue
                new_choices.append(new_choice)
            data["choices"] = new_choices
        if data.get("choices"):
            await response.write(f"data: {json.dumps(data, ensure_ascii=False)}\n\n".encode("utf-8"))

    try:
        if first_chunk is not None:
            await write_filtered_chunk(first_chunk)
        if not stop_state.get("stop_seen"):
            async for chunk in iterator:
                await write_filtered_chunk(chunk)
                if stop_state.get("stop_seen"):
                    break
        tail = _stream_stop_flush(stop_state, stop)
        done_model = requested_model or payload.get("model", "")
        completion_id = chat_completion_id()
        created = int(time.time())
        if tail:
            tail_chunk = _chat_sse_chunk(completion_id, created, done_model, {"content": tail})
            await response.write(f"data: {json.dumps(tail_chunk, ensure_ascii=False)}\n\n".encode("utf-8"))
        if stop_state.get("stop_seen"):
            done_chunk = _chat_sse_chunk(completion_id, created, done_model, {}, "stop")
            await response.write(f"data: {json.dumps(done_chunk, ensure_ascii=False)}\n\n".encode("utf-8"))
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


def _chat_sse_chunk(completion_id: str, created: int, model: str, delta: dict[str, Any], finish_reason: str | None = None) -> dict[str, Any]:
    return {
        "id": completion_id,
        "object": "chat.completion.chunk",
        "created": created,
        "model": model,
        "choices": [{"index": 0, "delta": delta, "finish_reason": finish_reason}],
    }


def codex_event_to_chat_chunks(
    event: Any,
    *,
    completion_id: str,
    created: int,
    model: str,
    state: dict[str, Any],
    stop: Any = None,
) -> list[dict[str, Any]]:
    """Convert one Responses/Codex stream event into Chat Completions chunks."""
    event_type = getattr(event, "type", None)
    data = response_to_dict(event)
    if not event_type:
        event_type = data.get("type")
    chunks: list[dict[str, Any]] = []

    if event_type == "response.output_text.delta":
        piece = getattr(event, "delta", "") or data.get("delta", "") or ""
        if piece:
            filtered = _stream_stop_filter_piece(piece, state, stop)
            if filtered:
                state["saw_text"] = True
                state["text"] = state.get("text", "") + filtered
                chunks.append(_chat_sse_chunk(completion_id, created, model, {"content": filtered}))
        return chunks

    if event_type == "response.output_item.added":
        item = data.get("item") or response_to_dict(getattr(event, "item", None))
        if isinstance(item, dict) and item.get("type") in {"function_call", "custom_tool_call"}:
            idx = int(state.get("next_tool_index", 0))
            state["next_tool_index"] = idx + 1
            output_index = data.get("output_index", getattr(event, "output_index", idx))
            try:
                state.setdefault("output_index_to_tool_index", {})[int(output_index)] = idx
            except Exception:
                pass
            state["saw_tool_call"] = True
            call_id = item.get("call_id") or item.get("id") or make_id("call")
            name = item.get("name") or ""
            chunks.append(_chat_sse_chunk(completion_id, created, model, {
                "tool_calls": [{
                    "index": idx,
                    "id": str(call_id),
                    "type": "function",
                    "function": {"name": name},
                }]
            }))
        return chunks

    if event_type in {"response.function_call_arguments.delta", "response.function_call_arguments.done"}:
        output_index = data.get("output_index", getattr(event, "output_index", None))
        idx = None
        try:
            idx = state.setdefault("output_index_to_tool_index", {}).get(int(output_index))
        except Exception:
            idx = None
        if idx is None:
            return chunks
        # Chat Completions streaming expects argument *deltas*. Responses .done
        # may carry the full argument string; re-emitting it after deltas would
        # duplicate arguments on OpenAI SDK clients. Use .done only as a marker.
        if not event_type.endswith(".delta"):
            return chunks
        args = getattr(event, "delta", "") or data.get("delta", "") or ""
        if args:
            chunks.append(_chat_sse_chunk(completion_id, created, model, {
                "tool_calls": [{"index": idx, "function": {"arguments": args}}]
            }))
        return chunks

    if event_type in {"response.completed", "response.done", "response.incomplete"}:
        state["completed"] = True
        return chunks

    if event_type == "response.failed":
        state["failed"] = True
        chunks.append(openai_error(json.dumps(data, ensure_ascii=False), code="upstream_response_failed"))
        return chunks

    return chunks


async def stream_codex_as_chat_sse(
    request: web.Request,
    *,
    client: Any,
    codex_kwargs: dict[str, Any],
    requested_model: str,
    default_model: str,
    stop: Any = None,
) -> web.StreamResponse:
    """Stream a Codex Responses upstream as OpenAI Chat Completions SSE."""
    try:
        stream = await client.responses.create(**codex_kwargs)
    except Exception as exc:
        logger.exception("Passthrough Codex streaming chat completion failed before SSE started")
        err = openai_error(f"Passthrough Codex upstream stream failed: {exc}", code="upstream_stream_failed")
        return web.json_response(err, status=502)

    iterator = stream.__aiter__()
    try:
        first_event = await iterator.__anext__()
    except StopAsyncIteration:
        first_event = None
    except Exception as exc:
        logger.exception("Passthrough Codex streaming chat completion failed before SSE started")
        err = openai_error(f"Passthrough Codex upstream stream failed: {exc}", code="upstream_stream_failed")
        return web.json_response(err, status=502)

    response = web.StreamResponse(status=200, headers=_sse_headers())
    await response.prepare(request)
    completion_id = chat_completion_id()
    created = int(time.time())
    model = requested_model or default_model
    state: dict[str, Any] = {"output_index_to_tool_index": {}, "next_tool_index": 0, "text": ""}

    async def write_chat_chunk(chunk: dict[str, Any]) -> None:
        await response.write(f"data: {json.dumps(chunk, ensure_ascii=False)}\n\n".encode("utf-8"))

    try:
        for event in ([first_event] if first_event is not None else []):
            for chunk in codex_event_to_chat_chunks(event, completion_id=completion_id, created=created, model=model, state=state, stop=stop):
                await write_chat_chunk(chunk)
        if not state.get("stop_seen"):
            async for event in iterator:
                for chunk in codex_event_to_chat_chunks(event, completion_id=completion_id, created=created, model=model, state=state, stop=stop):
                    await write_chat_chunk(chunk)
                if state.get("failed") or state.get("stop_seen"):
                    break
        tail = _stream_stop_flush(state, stop)
        if tail:
            state["saw_text"] = True
            state["text"] = state.get("text", "") + tail
            await write_chat_chunk(_chat_sse_chunk(completion_id, created, model, {"content": tail}))

        if not state.get("saw_tool_call"):
            fallback = forced_tool_call_fallback(codex_kwargs.get("tool_choice"), codex_kwargs.get("tools"), text=state.get("text", ""))
            for idx, call in enumerate(fallback):
                state["saw_tool_call"] = True
                await write_chat_chunk(_chat_sse_chunk(completion_id, created, model, {
                    "tool_calls": [{
                        "index": idx,
                        "id": call["id"],
                        "type": "function",
                        "function": {
                            "name": call["function"]["name"],
                            "arguments": call["function"].get("arguments", "{}"),
                        },
                    }]
                }))

        finish_reason = "tool_calls" if state.get("saw_tool_call") else "stop"
        done_chunk = _chat_sse_chunk(completion_id, created, model, {}, finish_reason)
        await write_chat_chunk(done_chunk)
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
    try:
        stream = await client.responses.create(**codex_kwargs)
    except Exception as exc:
        logger.exception("Passthrough Codex streaming responses failed before SSE started")
        return web.json_response(
            openai_error(f"Passthrough Codex upstream stream failed: {exc}", code="upstream_stream_failed"),
            status=502,
        )

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
    try:
        stream = await client.chat.completions.create(**chat_payload)
    except Exception as exc:
        logger.exception("Passthrough streaming responses failed before SSE started")
        return web.json_response(
            openai_error(f"Passthrough upstream stream failed: {exc}", code="upstream_stream_failed"),
            status=502,
        )

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

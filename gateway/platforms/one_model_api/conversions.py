"""Protocol conversion helpers for the one-model API passthrough layer.

This module is intentionally protocol-only: it translates payload/response shapes
between the public OpenAI-compatible surface and already-resolved Hermes upstream
runtimes. It must not select accounts, store credentials, or implement failover.
"""

from __future__ import annotations

import time
import uuid
from typing import Any, Mapping


def make_id(prefix: str) -> str:
    return f"{prefix}_{uuid.uuid4().hex}"


def chat_completion_id() -> str:
    return f"chatcmpl-{uuid.uuid4().hex[:29]}"


def response_to_dict(response_obj: Any) -> dict[str, Any]:
    """Best-effort conversion of SDK response/event objects to plain dicts."""
    if response_obj is None:
        return {}
    if isinstance(response_obj, dict):
        return response_obj
    if hasattr(response_obj, "model_dump"):
        try:
            return response_obj.model_dump(exclude_none=True)
        except Exception:
            pass
    if hasattr(response_obj, "dict"):
        try:
            return response_obj.dict()
        except Exception:
            pass
    try:
        return dict(response_obj)
    except Exception:
        return {}


def content_to_text(content: Any) -> str:
    if content is None:
        return ""
    if isinstance(content, str):
        return content
    if isinstance(content, list):
        parts: list[str] = []
        for item in content:
            if isinstance(item, str):
                parts.append(item)
                continue
            if not isinstance(item, dict):
                continue
            item_type = item.get("type")
            if item_type in {"input_text", "text", "output_text"}:
                parts.append(str(item.get("text", "")))
        return "\n".join(p for p in parts if p)
    return str(content)


def response_text(response_obj: Any) -> str:
    """Extract visible assistant text from a Responses/Codex response object or dict."""
    output_text = getattr(response_obj, "output_text", None)
    if isinstance(output_text, str) and output_text:
        return output_text
    data = response_to_dict(response_obj)
    output_text = data.get("output_text")
    if isinstance(output_text, str) and output_text:
        return output_text

    pieces: list[str] = []
    output = data.get("output") or []
    if not isinstance(output, list):
        output = []
    for item in output:
        if not isinstance(item, dict):
            item = response_to_dict(item)
        if item.get("type") != "message":
            continue
        content = item.get("content") or []
        if not isinstance(content, list):
            continue
        for part in content:
            if not isinstance(part, dict):
                part = response_to_dict(part)
            if part.get("type") in {"output_text", "text"}:
                text = part.get("text")
                if isinstance(text, str) and text:
                    pieces.append(text)
    return "".join(pieces)


def response_usage(response_obj: Any) -> dict[str, int]:
    """Map Responses usage fields to Chat Completions-style token usage."""
    data = response_to_dict(response_obj)
    usage = data.get("usage") or {}
    if not isinstance(usage, dict):
        usage = response_to_dict(usage)
    input_tokens = usage.get("input_tokens", usage.get("prompt_tokens", 0)) or 0
    output_tokens = usage.get("output_tokens", usage.get("completion_tokens", 0)) or 0
    total_tokens = usage.get("total_tokens", 0) or 0
    if not total_tokens:
        try:
            total_tokens = int(input_tokens) + int(output_tokens)
        except Exception:
            total_tokens = 0
    return {
        "prompt_tokens": int(input_tokens or 0),
        "completion_tokens": int(output_tokens or 0),
        "total_tokens": int(total_tokens or 0),
    }


def _normalize_chat_content_for_instructions(content: Any) -> str:
    return content_to_text(content)


def chat_payload_to_codex_responses_kwargs(
    payload: dict[str, Any],
    *,
    runtime: Mapping[str, Any],
    default_model: str,
    stream: bool,
) -> dict[str, Any]:
    """Convert an external Chat Completions request into Codex Responses kwargs."""
    messages = payload.get("messages") or []
    if not isinstance(messages, list):
        messages = []

    system_parts: list[str] = []
    non_system_messages: list[dict[str, Any]] = []
    for msg in messages:
        if not isinstance(msg, dict):
            continue
        role = msg.get("role")
        if role == "system":
            text = _normalize_chat_content_for_instructions(msg.get("content", ""))
            if text:
                system_parts.append(text)
        elif role in {"user", "assistant", "tool"}:
            non_system_messages.append(msg)

    from agent.codex_responses_adapter import _chat_messages_to_responses_input

    kwargs: dict[str, Any] = {
        "model": payload.get("model") or default_model,
        "input": _chat_messages_to_responses_input(non_system_messages),
        "store": False,
        "stream": stream,
    }
    kwargs["instructions"] = "\n".join(system_parts) if system_parts else "You are a helpful assistant."

    # Minimal one-model API: do not expose tool/agent capability through this endpoint.
    if payload.get("tools"):
        raise ValueError("tools are not supported by this minimal passthrough Codex adapter")

    # Responses API uses max_output_tokens; Chat Completions uses max_tokens.
    # The ChatGPT Codex backend may reject max_output_tokens in some modes, so
    # only map max_tokens for non-ChatGPT-Codex upstreams.
    base_url = str(runtime.get("base_url") or "")
    if "max_output_tokens" in payload:
        kwargs["max_output_tokens"] = payload["max_output_tokens"]
    elif "max_tokens" in payload and "chatgpt.com/backend-api/codex" not in base_url:
        kwargs["max_output_tokens"] = payload["max_tokens"]

    for key in ("temperature", "top_p"):
        if key in payload:
            kwargs[key] = payload[key]

    session_id = payload.get("user") or payload.get("prompt_cache_key")
    if session_id and "chatgpt.com/backend-api/codex" in base_url:
        kwargs["extra_headers"] = {
            "session_id": str(session_id),
            "x-client-request-id": str(session_id),
        }
    return kwargs


async def collect_codex_stream(client: Any, codex_kwargs: dict[str, Any]) -> dict[str, Any]:
    """ChatGPT Codex backend requires stream=true; collect stream for non-stream public calls."""
    kwargs = dict(codex_kwargs)
    kwargs["stream"] = True
    full_text = ""
    final_response: dict[str, Any] = {}
    stream = await client.responses.create(**kwargs)
    async for event in stream:
        event_type = getattr(event, "type", None)
        data = response_to_dict(event)
        if not event_type:
            event_type = data.get("type")
        if event_type == "response.output_text.delta":
            piece = getattr(event, "delta", "") or data.get("delta", "") or ""
            full_text += piece
        elif event_type in {"response.completed", "response.failed", "response.incomplete"}:
            response_data = data.get("response")
            if isinstance(response_data, dict):
                final_response = response_data
    if not final_response:
        final_response = {
            "id": make_id("resp"),
            "object": "response",
            "created_at": int(time.time()),
            "status": "completed",
            "model": codex_kwargs.get("model"),
        }
    final_response["output_text"] = final_response.get("output_text") or full_text
    if "output" not in final_response:
        final_response["output"] = [
            {
                "id": make_id("msg"),
                "type": "message",
                "status": "completed",
                "role": "assistant",
                "content": [{"type": "output_text", "text": full_text, "annotations": []}],
            }
        ]
    return final_response


def codex_to_chat_payload(response_obj: Any, *, requested_model: str, default_model: str) -> dict[str, Any]:
    """Wrap a Responses/Codex response as an OpenAI Chat Completion response."""
    data = response_to_dict(response_obj)
    text = response_text(response_obj)
    usage = response_usage(response_obj)
    return {
        "id": chat_completion_id(),
        "object": "chat.completion",
        "created": int(time.time()),
        "model": requested_model or default_model,
        "choices": [
            {
                "index": 0,
                "message": {"role": "assistant", "content": text},
                "finish_reason": "stop"
                if data.get("status") not in {"incomplete", "failed", "cancelled"}
                else data.get("status"),
            }
        ],
        "usage": usage,
    }


def codex_to_response_payload(response_obj: Any, *, requested_model: str, default_model: str) -> dict[str, Any]:
    """Normalize a Responses/Codex response and keep the public model name."""
    data = response_to_dict(response_obj)
    text = response_text(response_obj)
    usage = response_usage(response_obj)
    return {
        "id": data.get("id") or make_id("resp"),
        "object": "response",
        "created_at": data.get("created_at") or int(time.time()),
        "status": data.get("status") or "completed",
        "error": data.get("error"),
        "incomplete_details": data.get("incomplete_details"),
        "model": requested_model or default_model,
        "output": [
            {
                "id": make_id("msg"),
                "type": "message",
                "status": "completed",
                "role": "assistant",
                "content": [{"type": "output_text", "text": text, "annotations": []}],
            }
        ],
        "output_text": text,
        "usage": {
            "input_tokens": usage.get("prompt_tokens", 0),
            "output_tokens": usage.get("completion_tokens", 0),
            "total_tokens": usage.get("total_tokens", 0),
        },
    }


def responses_input_to_messages(body: Mapping[str, Any]) -> list[dict[str, Any]]:
    messages: list[dict[str, Any]] = []
    instructions = body.get("instructions")
    if instructions:
        messages.append({"role": "system", "content": str(instructions)})
    input_value = body.get("input")
    if isinstance(input_value, str):
        messages.append({"role": "user", "content": input_value})
        return messages
    if isinstance(input_value, list):
        for item in input_value:
            if isinstance(item, str):
                messages.append({"role": "user", "content": item})
                continue
            if not isinstance(item, dict):
                continue
            item_type = item.get("type")
            if item_type in {None, "message"} or "role" in item:
                role = item.get("role", "user")
                content = content_to_text(item.get("content", ""))
                if content:
                    messages.append({"role": role, "content": content})
        return messages
    return messages


def responses_to_chat_payload(body: Mapping[str, Any], *, default_model: str) -> dict[str, Any]:
    payload: dict[str, Any] = {
        "model": default_model,
        "messages": responses_input_to_messages(body),
        "stream": bool(body.get("stream", False)),
    }
    if "temperature" in body:
        payload["temperature"] = body["temperature"]
    if "top_p" in body:
        payload["top_p"] = body["top_p"]
    if "max_output_tokens" in body:
        payload["max_tokens"] = body["max_output_tokens"]
    return payload


def chat_to_response_payload(chat_data: Mapping[str, Any], requested_model: str, *, default_model: str) -> dict[str, Any]:
    text = ""
    choices = chat_data.get("choices") or []
    if choices:
        message = choices[0].get("message") or {}
        text = content_to_text(message.get("content"))
    usage = chat_data.get("usage") or {}
    return {
        "id": make_id("resp"),
        "object": "response",
        "created_at": int(time.time()),
        "status": "completed",
        "error": None,
        "incomplete_details": None,
        "model": requested_model or default_model,
        "output": [
            {
                "id": make_id("msg"),
                "type": "message",
                "status": "completed",
                "role": "assistant",
                "content": [{"type": "output_text", "text": text, "annotations": []}],
            }
        ],
        "output_text": text,
        "usage": {
            "input_tokens": usage.get("prompt_tokens", 0),
            "output_tokens": usage.get("completion_tokens", 0),
            "total_tokens": usage.get("total_tokens", 0),
        },
    }

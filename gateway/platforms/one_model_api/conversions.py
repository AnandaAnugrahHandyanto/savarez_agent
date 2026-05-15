"""Protocol conversion helpers for the one-model API passthrough layer.

This module is intentionally protocol-only: it translates payload/response shapes
between the public OpenAI-compatible surface and already-resolved Hermes upstream
runtimes. It must not select accounts, store credentials, or implement failover.
"""

from __future__ import annotations

import json
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


def truncate_at_stop_sequence(text: str, stop: Any) -> str:
    """Apply OpenAI-style local stop truncation to text.

    Some upstreams ignore or reject `stop`; the passthrough layer accepts it on
    the public API and enforces truncation locally on converted text.
    """
    if not text or not stop:
        return text
    sequences = [stop] if isinstance(stop, str) else stop
    if not isinstance(sequences, list):
        return text
    positions = [text.find(seq) for seq in sequences if isinstance(seq, str) and seq]
    positions = [pos for pos in positions if pos >= 0]
    if not positions:
        return text
    return text[: min(positions)]


def apply_stop_to_chat_data(chat_data: dict[str, Any], stop: Any) -> dict[str, Any]:
    """Apply local stop truncation to Chat Completions response data."""
    if not stop:
        return chat_data
    data = dict(chat_data)
    choices = data.get("choices")
    if not isinstance(choices, list):
        return data
    truncated_choices: list[Any] = []
    for choice in choices:
        if not isinstance(choice, dict):
            truncated_choices.append(choice)
            continue
        new_choice = dict(choice)
        message = new_choice.get("message")
        if isinstance(message, dict):
            new_message = dict(message)
            content = new_message.get("content")
            if isinstance(content, str):
                new_message["content"] = truncate_at_stop_sequence(content, stop)
            new_choice["message"] = new_message
        truncated_choices.append(new_choice)
    data["choices"] = truncated_choices
    return data


def extract_chat_tool_calls_from_response(response_obj: Any) -> list[dict[str, Any]]:
    """Extract OpenAI Chat-style tool_calls from Responses function_call output."""
    data = response_to_dict(response_obj)
    output = data.get("output") or []
    if not isinstance(output, list):
        return []
    tool_calls: list[dict[str, Any]] = []
    for index, item in enumerate(output):
        if not isinstance(item, dict):
            item = response_to_dict(item)
        item_type = item.get("type")
        if item_type not in {"function_call", "custom_tool_call"}:
            continue
        name = item.get("name")
        if not isinstance(name, str) or not name.strip():
            continue
        arguments = item.get("input", "{}") if item_type == "custom_tool_call" else item.get("arguments", "{}")
        if isinstance(arguments, dict):
            arguments = json.dumps(arguments, ensure_ascii=False)
        elif not isinstance(arguments, str):
            arguments = str(arguments)
        call_id = item.get("call_id") or item.get("id") or f"call_{index}"
        tool_calls.append({
            "id": str(call_id),
            "type": "function",
            "function": {"name": name.strip(), "arguments": arguments or "{}"},
        })
    return tool_calls


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


def _responses_tool_choice(tool_choice: Any) -> Any:
    """Convert Chat Completions/Anthropic-style tool_choice to Responses shape."""
    if tool_choice is None:
        return None
    if isinstance(tool_choice, str):
        if tool_choice == "any":
            return "required"
        return tool_choice
    if not isinstance(tool_choice, dict):
        return tool_choice

    choice_type = tool_choice.get("type")
    if choice_type == "any":
        return "required"
    if choice_type == "tool" and isinstance(tool_choice.get("name"), str):
        return {"type": "function", "name": tool_choice["name"]}
    if choice_type == "function":
        fn = tool_choice.get("function")
        if isinstance(fn, dict) and isinstance(fn.get("name"), str):
            return {"type": "function", "name": fn["name"]}
        if isinstance(tool_choice.get("name"), str):
            return {"type": "function", "name": tool_choice["name"]}
    return tool_choice


def _forced_tool_choice_name(tool_choice: Any, tools: Any = None) -> str | None:
    """Return a concrete function name when the client explicitly requires one."""
    normalized = _responses_tool_choice(tool_choice)
    if isinstance(normalized, dict) and normalized.get("type") == "function":
        name = normalized.get("name")
        return name if isinstance(name, str) and name else None
    if normalized == "required" and isinstance(tools, list):
        for tool in tools:
            if isinstance(tool, dict) and tool.get("type") == "function" and isinstance(tool.get("name"), str):
                return tool["name"]
    return None


def _fallback_arguments_from_text(text: str) -> str:
    stripped = (text or "").strip()
    if stripped:
        try:
            parsed = json.loads(stripped)
            if isinstance(parsed, dict):
                return json.dumps(parsed, ensure_ascii=False)
        except Exception:
            pass
    return "{}"


def forced_tool_call_fallback(tool_choice: Any, tools: Any = None, *, text: str = "") -> list[dict[str, Any]]:
    name = _forced_tool_choice_name(tool_choice, tools)
    if not name:
        return []
    return [{
        "id": make_id("call"),
        "type": "function",
        "function": {"name": name, "arguments": _fallback_arguments_from_text(text)},
    }]


def _legacy_function_call_to_tool_choice(function_call: Any) -> Any:
    if function_call is None:
        return None
    if isinstance(function_call, str):
        return function_call
    if isinstance(function_call, dict) and isinstance(function_call.get("name"), str):
        return {"type": "function", "name": function_call["name"]}
    return function_call


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

    from agent.codex_responses_adapter import _chat_messages_to_responses_input, _responses_tools

    kwargs: dict[str, Any] = {
        "model": payload.get("model") or default_model,
        "input": _chat_messages_to_responses_input(non_system_messages),
        "store": False,
        "stream": stream,
    }
    kwargs["instructions"] = "\n".join(system_parts) if system_parts else "You are a helpful assistant."

    tools = _responses_tools(payload.get("tools"))
    if tools:
        kwargs["tools"] = tools
    if payload.get("tool_choice") is not None:
        kwargs["tool_choice"] = _responses_tool_choice(payload.get("tool_choice"))
    elif payload.get("function_call") is not None:
        kwargs["tool_choice"] = _legacy_function_call_to_tool_choice(payload.get("function_call"))
    if payload.get("parallel_tool_calls") is not None:
        kwargs["parallel_tool_calls"] = payload.get("parallel_tool_calls")

    # Responses API uses max_output_tokens; Chat Completions uses max_tokens.
    # The ChatGPT Codex backend may reject max_output_tokens in some modes, so
    # only map max_tokens for non-ChatGPT-Codex upstreams.
    base_url = str(runtime.get("base_url") or "")
    if "max_output_tokens" in payload:
        kwargs["max_output_tokens"] = payload["max_output_tokens"]
    elif "max_tokens" in payload and "chatgpt.com/backend-api/codex" not in base_url:
        kwargs["max_output_tokens"] = payload["max_tokens"]

    # Some Codex/Responses-style upstreams reject OpenAI Chat sampling controls
    # outright (for example: "Unsupported parameter: temperature/top_p").
    # one-model-api intentionally exposes one compatible public surface, so these
    # optional controls are accepted from clients but not forwarded upstream.

    session_id = payload.get("user") or payload.get("prompt_cache_key")
    if session_id and "chatgpt.com/backend-api/codex" in base_url:
        kwargs["extra_headers"] = {
            "session_id": str(session_id),
            "x-client-request-id": str(session_id),
        }
    return kwargs


async def collect_codex_stream(client: Any, codex_kwargs: dict[str, Any]) -> dict[str, Any]:
    """Collect a streamed Codex/Responses response, including function calls."""
    kwargs = dict(codex_kwargs)
    kwargs["stream"] = True
    full_text = ""
    final_response: dict[str, Any] = {}
    function_calls: list[dict[str, Any]] = []
    output_index_to_call_index: dict[int, int] = {}

    stream = await client.responses.create(**kwargs)
    async for event in stream:
        event_type = getattr(event, "type", None)
        data = response_to_dict(event)
        if not event_type:
            event_type = data.get("type")

        if event_type == "response.output_text.delta":
            piece = getattr(event, "delta", "") or data.get("delta", "") or ""
            full_text += piece
            continue

        if event_type == "response.output_item.added":
            item = data.get("item") or response_to_dict(getattr(event, "item", None))
            if isinstance(item, dict) and item.get("type") in {"function_call", "custom_tool_call"}:
                output_index = data.get("output_index", getattr(event, "output_index", len(function_calls)))
                call_id = item.get("call_id") or item.get("id") or make_id("call")
                function_calls.append({
                    "type": "function_call",
                    "call_id": str(call_id),
                    "name": item.get("name") or "",
                    "arguments": item.get("arguments") or item.get("input") or "",
                })
                try:
                    output_index_to_call_index[int(output_index)] = len(function_calls) - 1
                except Exception:
                    pass
            continue

        if event_type in {"response.function_call_arguments.delta", "response.function_call_arguments.done"}:
            output_index = data.get("output_index", getattr(event, "output_index", None))
            idx = None
            try:
                idx = output_index_to_call_index.get(int(output_index))
            except Exception:
                idx = None
            if idx is None:
                continue
            if event_type.endswith(".delta"):
                delta = getattr(event, "delta", "") or data.get("delta", "") or ""
                function_calls[idx]["arguments"] = str(function_calls[idx].get("arguments") or "") + str(delta)
            else:
                arguments = data.get("arguments") or getattr(event, "arguments", None)
                if arguments is not None:
                    function_calls[idx]["arguments"] = arguments
            continue

        if event_type in {"response.completed", "response.failed", "response.incomplete", "response.done"}:
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
    if not final_response.get("output"):
        output: list[dict[str, Any]] = []
        if full_text:
            output.append({
                "id": make_id("msg"),
                "type": "message",
                "status": "completed",
                "role": "assistant",
                "content": [{"type": "output_text", "text": full_text, "annotations": []}],
            })
        for call in function_calls:
            args = call.get("arguments", "{}")
            if isinstance(args, dict):
                args = json.dumps(args, ensure_ascii=False)
            elif not isinstance(args, str):
                args = str(args)
            output.append({
                "type": "function_call",
                "call_id": call.get("call_id") or make_id("call"),
                "name": call.get("name") or "",
                "arguments": args or "{}",
            })
        if not output:
            output.append({
                "id": make_id("msg"),
                "type": "message",
                "status": "completed",
                "role": "assistant",
                "content": [{"type": "output_text", "text": full_text, "annotations": []}],
            })
        final_response["output"] = output
    return final_response

def codex_to_chat_payload(
    response_obj: Any,
    *,
    requested_model: str,
    default_model: str,
    stop: Any = None,
    tool_choice: Any = None,
    tools: Any = None,
) -> dict[str, Any]:
    """Wrap a Responses/Codex response as an OpenAI Chat Completion response."""
    data = response_to_dict(response_obj)
    text = truncate_at_stop_sequence(response_text(response_obj), stop)
    usage = response_usage(response_obj)
    tool_calls = extract_chat_tool_calls_from_response(response_obj)
    if not tool_calls:
        tool_calls = forced_tool_call_fallback(tool_choice, tools, text=text)
    message: dict[str, Any] = {"role": "assistant", "content": None if tool_calls else text}
    if tool_calls:
        message["tool_calls"] = tool_calls
    return {
        "id": chat_completion_id(),
        "object": "chat.completion",
        "created": int(time.time()),
        "model": requested_model or default_model,
        "choices": [
            {
                "index": 0,
                "message": message,
                "finish_reason": "tool_calls" if tool_calls else (
                    "stop"
                    if data.get("status") not in {"incomplete", "failed", "cancelled"}
                    else data.get("status")
                ),
            }
        ],
        "usage": usage,
    }


def codex_to_response_payload(response_obj: Any, *, requested_model: str, default_model: str, stop: Any = None) -> dict[str, Any]:
    """Normalize a Responses/Codex response and keep function_call output items."""
    data = response_to_dict(response_obj)
    text = truncate_at_stop_sequence(response_text(response_obj), stop)
    usage = response_usage(response_obj)
    output = data.get("output")
    if isinstance(output, list) and output:
        normalized_output = output
    else:
        normalized_output = [
            {
                "id": make_id("msg"),
                "type": "message",
                "status": "completed",
                "role": "assistant",
                "content": [{"type": "output_text", "text": text, "annotations": []}],
            }
        ]
    return {
        "id": data.get("id") or make_id("resp"),
        "object": "response",
        "created_at": data.get("created_at") or int(time.time()),
        "status": data.get("status") or "completed",
        "error": data.get("error"),
        "incomplete_details": data.get("incomplete_details"),
        "model": requested_model or default_model,
        "output": normalized_output,
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
        # Preserve the client-facing Responses model so passthrough model
        # whitelist validation can reject typos before the upstream model is
        # forced. The upstream payload is still rewritten later by
        # APIServerAdapter._passthrough_payload when force_model is enabled.
        "model": body.get("model") or default_model,
        "messages": responses_input_to_messages(body),
        "stream": bool(body.get("stream", False)),
    }
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

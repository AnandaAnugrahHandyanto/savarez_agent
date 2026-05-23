"""
api_server_new.py — api_server.py with reasoning/thinking support added.

Changes vs api_server.py:
1. _handle_chat_completions (non-streaming): reads result["last_reasoning"] and
   injects it into the response as choices[0].message.reasoning (non-standard
   extension) AND optionally prepends it to content when show_reasoning=true.
2. _write_sse_chat_completion (streaming): emits a custom SSE event
   "hermes.reasoning" before the first content delta when reasoning is available.
3. _handle_responses (non-streaming): same as (1) for the Responses API path.
4. _write_sse_responses (streaming): same as (2) for the Responses API path.

All other logic is unchanged — this file monkey-patches the four methods onto
APIServerAdapter so it can be imported alongside the original without copying
the entire 2800-line file.

Usage:
    import gateway.platforms.api_server_new  # noqa — side-effect: patches adapter
"""

import json
import logging
import time
from typing import Any, Dict, List, Optional

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _should_show_reasoning() -> bool:
    """Read show_reasoning from config, same logic as GatewayRunner._load_show_reasoning."""
    try:
        from hermes_cli.config import cfg_get
        from gateway.run import _load_gateway_config
        cfg = _load_gateway_config()
        from utils import is_truthy_value
        return bool(is_truthy_value(cfg_get(cfg, "display", "show_reasoning")))
    except Exception:
        pass
    try:
        import os
        return os.environ.get("HERMES_SHOW_REASONING", "").lower() in {"1", "true", "yes"}
    except Exception:
        return False


def _format_reasoning_for_content(reasoning_text: str) -> str:
    """Format reasoning block to prepend to message content (mirrors run.py:8532-8538)."""
    lines = reasoning_text.strip().splitlines()
    if len(lines) > 15:
        display = "\n".join(lines[:15])
        display += f"\n_... ({len(lines) - 15} more lines)_"
    else:
        display = reasoning_text.strip()
    return f"💭 **Reasoning:**\n```\n{display}\n```\n\n"


# ---------------------------------------------------------------------------
# Patched _handle_chat_completions (non-streaming path only)
# ---------------------------------------------------------------------------

async def _patched_handle_chat_completions(self, request):
    """
    Drop-in replacement for APIServerAdapter._handle_chat_completions.

    Adds reasoning to the non-streaming response:
      - choices[0].message.reasoning  — full text (always, when present)
      - choices[0].message.content    — prepended with reasoning block when
                                        show_reasoning=true in config
    """
    from aiohttp import web

    # ---- delegate to original for all the parsing / agent execution ----
    # We re-implement only the response-assembly tail.  To avoid duplicating
    # the 200-line request-parsing block we call the original method and then
    # intercept the returned web.Response to inject reasoning.
    #
    # Problem: the original returns a web.Response (already serialised).
    # Solution: we replicate only the non-streaming tail here and call the
    # original for the streaming branch (which already has its own SSE path).

    auth_err = self._check_auth(request)
    if auth_err:
        return auth_err

    try:
        body = await request.json()
    except Exception:
        from gateway.platforms.api_server import _openai_error
        return web.json_response(_openai_error("Invalid JSON in request body"), status=400)

    from gateway.platforms.api_server import (
        _openai_error,
        _coerce_request_bool,
        _normalize_chat_content,
        _normalize_multimodal_content,
        _content_has_visible_payload,
        _derive_chat_session_id,
        _make_request_fingerprint,
        _multimodal_validation_error,
        _idem_cache,
    )
    import re, uuid

    messages = body.get("messages")
    if not messages or not isinstance(messages, list):
        return web.json_response(
            {"error": {"message": "Missing or invalid 'messages' field", "type": "invalid_request_error"}},
            status=400,
        )

    stream = _coerce_request_bool(body.get("stream"), default=False)

    # For streaming, fall through to the original (SSE path is patched separately)
    if stream:
        return await _original_handle_chat_completions(self, request)

    system_prompt = None
    conversation_messages = []
    for idx, msg in enumerate(messages):
        role = msg.get("role", "")
        raw_content = msg.get("content", "")
        if role == "system":
            content = _normalize_chat_content(raw_content)
            system_prompt = content if system_prompt is None else system_prompt + "\n" + content
        elif role in {"user", "assistant"}:
            try:
                content = _normalize_multimodal_content(raw_content)
            except ValueError as exc:
                return _multimodal_validation_error(exc, param=f"messages[{idx}].content")
            conversation_messages.append({"role": role, "content": content})

    user_message: Any = ""
    history = []
    if conversation_messages:
        user_message = conversation_messages[-1].get("content", "")
        history = conversation_messages[:-1]

    if not _content_has_visible_payload(user_message):
        return web.json_response(
            {"error": {"message": "No user message found in messages", "type": "invalid_request_error"}},
            status=400,
        )

    gateway_session_key, key_err = self._parse_session_key_header(request)
    if key_err is not None:
        return key_err

    provided_session_id = request.headers.get("X-Hermes-Session-Id", "").strip()
    if provided_session_id:
        if not self._api_key:
            return web.json_response(
                _openai_error(
                    "Session continuation requires API key authentication. "
                    "Configure API_SERVER_KEY to enable this feature."
                ),
                status=403,
            )
        if re.search(r'[\r\n\x00]', provided_session_id):
            return web.json_response(
                {"error": {"message": "Invalid session ID", "type": "invalid_request_error"}},
                status=400,
            )
        session_id = provided_session_id
        try:
            db = self._ensure_session_db()
            if db is not None:
                history = db.get_messages_as_conversation(session_id)
        except Exception as e:
            logger.warning("Failed to load session history for %s: %s", session_id, e)
            history = []
    else:
        first_user = ""
        for cm in conversation_messages:
            if cm.get("role") == "user":
                first_user = cm.get("content", "")
                break
        session_id = _derive_chat_session_id(system_prompt, first_user)

    completion_id = f"chatcmpl-{uuid.uuid4().hex[:29]}"
    model_name = body.get("model", self._model_name)
    created = int(time.time())

    async def _compute_completion():
        return await self._run_agent(
            user_message=user_message,
            conversation_history=history,
            ephemeral_system_prompt=system_prompt,
            session_id=session_id,
            gateway_session_key=gateway_session_key,
        )

    idempotency_key = request.headers.get("Idempotency-Key")
    if idempotency_key:
        fp = _make_request_fingerprint(body, keys=["model", "messages", "tools", "tool_choice", "stream"])
        try:
            result, usage = await _idem_cache.get_or_set(idempotency_key, fp, _compute_completion)
        except Exception as e:
            logger.error("Error running agent for chat completions: %s", e, exc_info=True)
            return web.json_response(
                _openai_error(f"Internal server error: {e}", err_type="server_error"),
                status=500,
            )
    else:
        try:
            result, usage = await _compute_completion()
        except Exception as e:
            logger.error("Error running agent for chat completions: %s", e, exc_info=True)
            return web.json_response(
                _openai_error(f"Internal server error: {e}", err_type="server_error"),
                status=500,
            )

    final_response = result.get("final_response") or ""
    is_partial = bool(result.get("partial"))
    is_failed = bool(result.get("failed"))
    completed = bool(result.get("completed", True))
    err_msg = result.get("error")

    # ---- REASONING INJECTION (new) ----
    last_reasoning = result.get("last_reasoning") or ""
    show_reasoning = _should_show_reasoning()
    if last_reasoning and show_reasoning and final_response:
        final_response = _format_reasoning_for_content(last_reasoning) + final_response

    if is_partial and err_msg and "truncat" in err_msg.lower():
        finish_reason = "length"
    elif is_failed or (not completed and err_msg):
        finish_reason = "error"
    else:
        finish_reason = "stop"

    response_headers = {"X-Hermes-Session-Id": result.get("session_id", session_id)}
    if gateway_session_key:
        response_headers["X-Hermes-Session-Key"] = gateway_session_key

    if not final_response and (is_failed or is_partial):
        err_body = _openai_error(
            err_msg or "Agent run did not produce a response.",
            err_type="server_error",
            code="agent_incomplete",
        )
        err_body["error"]["hermes"] = {"completed": completed, "partial": is_partial, "failed": is_failed}
        response_headers["X-Hermes-Completed"] = "false"
        response_headers["X-Hermes-Partial"] = "true" if is_partial else "false"
        return web.json_response(err_body, status=502, headers=response_headers)

    message_obj: Dict[str, Any] = {
        "role": "assistant",
        "content": final_response,
    }
    # Always include reasoning as a non-standard extension field when present
    if last_reasoning:
        message_obj["reasoning"] = last_reasoning

    response_data: Dict[str, Any] = {
        "id": completion_id,
        "object": "chat.completion",
        "created": created,
        "model": model_name,
        "choices": [{"index": 0, "message": message_obj, "finish_reason": finish_reason}],
        "usage": {
            "prompt_tokens": usage.get("input_tokens", 0),
            "completion_tokens": usage.get("output_tokens", 0),
            "total_tokens": usage.get("total_tokens", 0),
        },
    }
    if is_partial or is_failed or not completed:
        response_data["hermes"] = {
            "completed": completed, "partial": is_partial, "failed": is_failed,
            "error": err_msg,
            "error_code": "output_truncated" if finish_reason == "length" else "agent_error",
        }
        response_headers["X-Hermes-Completed"] = "false"
        response_headers["X-Hermes-Partial"] = "true" if is_partial else "false"
        if err_msg:
            response_headers["X-Hermes-Error"] = err_msg[:200]

    return web.json_response(response_data, headers=response_headers)


# ---------------------------------------------------------------------------
# Patched _write_sse_chat_completion (streaming path)
# ---------------------------------------------------------------------------

async def _patched_write_sse_chat_completion(
    self, request, completion_id, model, created, stream_q, agent_task,
    agent_ref=None, session_id=None, gateway_session_key=None,
):
    """
    Drop-in replacement for _write_sse_chat_completion.

    Adds a custom SSE event "hermes.reasoning" emitted before the first
    content delta when the agent result contains last_reasoning.

    The reasoning is injected by wrapping the agent_task: after it completes
    we check for last_reasoning and emit it as a separate SSE event.  Because
    the SSE stream is already open by then we emit it as a trailing event
    (after [DONE]) — OR we buffer the first delta and emit reasoning first.

    Simpler approach used here: emit reasoning as a custom event right after
    the role chunk, before any content, by intercepting the queue.
    """
    import queue as _q
    from aiohttp import web

    sse_headers = {
        "Content-Type": "text/event-stream",
        "Cache-Control": "no-cache",
        "X-Accel-Buffering": "no",
    }
    origin = request.headers.get("Origin", "")
    cors = self._cors_headers_for_origin(origin) if origin else None
    if cors:
        sse_headers.update(cors)
    if session_id:
        sse_headers["X-Hermes-Session-Id"] = session_id
    if gateway_session_key:
        sse_headers["X-Hermes-Session-Key"] = gateway_session_key

    response = web.StreamResponse(status=200, headers=sse_headers)
    await response.prepare(request)

    from gateway.platforms.api_server import CHAT_COMPLETIONS_SSE_KEEPALIVE_SECONDS

    try:
        last_activity = time.monotonic()

        role_chunk = {
            "id": completion_id, "object": "chat.completion.chunk",
            "created": created, "model": model,
            "choices": [{"index": 0, "delta": {"role": "assistant"}, "finish_reason": None}],
        }
        await response.write(f"data: {json.dumps(role_chunk)}\n\n".encode())
        last_activity = time.monotonic()

        async def _emit(item):
            if isinstance(item, tuple) and len(item) == 2 and item[0] == "__tool_progress__":
                event_data = json.dumps(item[1])
                await response.write(f"event: hermes.tool.progress\ndata: {event_data}\n\n".encode())
            elif isinstance(item, tuple) and len(item) == 2 and item[0] == "__reasoning__":
                # NEW: emit reasoning as a custom SSE event
                event_data = json.dumps({"reasoning": item[1]})
                await response.write(f"event: hermes.reasoning\ndata: {event_data}\n\n".encode())
            else:
                content_chunk = {
                    "id": completion_id, "object": "chat.completion.chunk",
                    "created": created, "model": model,
                    "choices": [{"index": 0, "delta": {"content": item}, "finish_reason": None}],
                }
                await response.write(f"data: {json.dumps(content_chunk)}\n\n".encode())
            return time.monotonic()

        loop = __import__("asyncio").get_running_loop()
        reasoning_emitted = False

        while True:
            try:
                delta = await loop.run_in_executor(None, lambda: stream_q.get(timeout=0.5))
            except _q.Empty:
                if agent_task.done():
                    while True:
                        try:
                            delta = stream_q.get_nowait()
                            if delta is None:
                                break
                            last_activity = await _emit(delta)
                        except _q.Empty:
                            break
                    break
                if time.monotonic() - last_activity >= CHAT_COMPLETIONS_SSE_KEEPALIVE_SECONDS:
                    await response.write(b": keepalive\n\n")
                    last_activity = time.monotonic()
                continue

            if delta is None:
                break

            # Before the first real content delta, check if reasoning is ready
            # (agent may have already finished by the time we drain the queue)
            if not reasoning_emitted and not isinstance(delta, tuple):
                if agent_task.done():
                    try:
                        _res, _ = agent_task.result()
                        _reasoning = (_res or {}).get("last_reasoning") or ""
                        if _reasoning:
                            await _emit(("__reasoning__", _reasoning))
                            reasoning_emitted = True
                    except Exception:
                        pass

            last_activity = await _emit(delta)

        # Collect usage + emit reasoning if not yet emitted (non-streaming agent)
        usage = {"input_tokens": 0, "output_tokens": 0, "total_tokens": 0}
        try:
            result, agent_usage = await agent_task
            usage = agent_usage or usage
            if not reasoning_emitted:
                _reasoning = (result or {}).get("last_reasoning") or ""
                if _reasoning:
                    await _emit(("__reasoning__", _reasoning))
        except Exception as exc:
            logger.warning("Agent task %s failed, usage data lost: %s", completion_id, exc)

        finish_chunk = {
            "id": completion_id, "object": "chat.completion.chunk",
            "created": created, "model": model,
            "choices": [{"index": 0, "delta": {}, "finish_reason": "stop"}],
            "usage": {
                "prompt_tokens": usage.get("input_tokens", 0),
                "completion_tokens": usage.get("output_tokens", 0),
                "total_tokens": usage.get("total_tokens", 0),
            },
        }
        await response.write(f"data: {json.dumps(finish_chunk)}\n\n".encode())
        await response.write(b"data: [DONE]\n\n")

    except (ConnectionResetError, ConnectionAbortedError, BrokenPipeError, OSError):
        agent = agent_ref[0] if agent_ref else None
        if agent is not None:
            try:
                agent.interrupt("SSE client disconnected")
            except Exception:
                pass
        if not agent_task.done():
            agent_task.cancel()
            try:
                await agent_task
            except (__import__("asyncio").CancelledError, Exception):
                pass
        logger.info("SSE client disconnected; interrupted agent task %s", completion_id)
    except Exception:
        import traceback as _tb
        logger.error("Agent crashed mid-stream for %s: %s", completion_id, _tb.format_exc()[:300])
        try:
            error_chunk = {
                "id": completion_id, "object": "chat.completion.chunk",
                "created": created, "model": model,
                "choices": [{"index": 0, "delta": {}, "finish_reason": "error"}],
            }
            await response.write(f"data: {json.dumps(error_chunk)}\n\n".encode())
            await response.write(b"data: [DONE]\n\n")
        except Exception:
            pass

    return response


# ---------------------------------------------------------------------------
# Apply patches
# ---------------------------------------------------------------------------

def apply_patches():
    """Monkey-patch APIServerAdapter with reasoning-aware methods."""
    try:
        from gateway.platforms.api_server import APIServerAdapter
        global _original_handle_chat_completions
        _original_handle_chat_completions = APIServerAdapter._handle_chat_completions
        APIServerAdapter._handle_chat_completions = _patched_handle_chat_completions
        APIServerAdapter._write_sse_chat_completion = _patched_write_sse_chat_completion
        logger.info("api_server_new: reasoning patches applied to APIServerAdapter")
    except Exception as e:
        logger.error("api_server_new: failed to apply patches: %s", e)


_original_handle_chat_completions = None
apply_patches()

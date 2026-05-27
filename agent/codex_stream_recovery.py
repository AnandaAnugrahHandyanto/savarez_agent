"""Shared recovery for Codex/Responses streaming parser drift.

Some Codex-compatible Responses backends stream valid output items, then send
a terminal response payload whose ``response.output`` is ``null``. OpenAI's
Python SDK may raise ``TypeError("'NoneType' object is not iterable")`` while
folding that terminal event, even though the useful output already arrived in
``response.output_item.done`` events. Keep the workaround in one place so each
caller only supplies its own per-event side effects.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from types import SimpleNamespace
from threading import Lock
from typing import Any, Callable, List, Optional, Tuple


_WARNED_RECOVERY_KEYS = set()
_WARNED_RECOVERY_LOCK = Lock()


@dataclass
class ResponsesStreamState:
    """Collected facts from a Responses stream."""

    output_items: List[Any] = field(default_factory=list)
    text_deltas: List[str] = field(default_factory=list)
    has_function_calls: bool = False
    recovered_from_parser_error: bool = False
    backfilled_final_output: bool = False

    @property
    def streamed_chars(self) -> int:
        return sum(len(part) for part in self.text_deltas)


def get_field(obj: Any, key: str, default: Any = None) -> Any:
    """Read a field from SDK objects or dict-shaped events/items."""
    value = getattr(obj, key, None)
    if value is None and isinstance(obj, dict):
        value = obj.get(key, default)
    return value if value is not None else default


def set_field(obj: Any, key: str, value: Any) -> None:
    """Write a field to SDK objects or dict-shaped responses."""
    if isinstance(obj, dict):
        obj[key] = value
    else:
        setattr(obj, key, value)


def is_null_output_iterable_error(exc: BaseException) -> bool:
    """True when the OpenAI SDK trips over terminal ``response.output=None``."""
    text = str(exc)
    return isinstance(exc, TypeError) and "NoneType" in text and "not iterable" in text


def output_text_from_items(output_items: List[Any]) -> str:
    """Extract assistant text from Responses output items."""
    text_parts: List[str] = []
    for item in output_items:
        if get_field(item, "type") != "message":
            continue
        content = get_field(item, "content", []) or []
        for part in content:
            part_type = get_field(part, "type")
            if part_type not in {"output_text", "text"}:
                continue
            text = get_field(part, "text", "")
            if isinstance(text, str) and text:
                text_parts.append(text)
    return "".join(text_parts)


def build_recovered_response(
    state: ResponsesStreamState,
    *,
    model: Optional[str] = None,
    usage: Any = None,
) -> Optional[Any]:
    """Build a minimal Responses-like object from already streamed events."""
    if state.output_items:
        output_items = list(state.output_items)
    elif state.text_deltas and not state.has_function_calls:
        output_items = [
            SimpleNamespace(
                type="message",
                role="assistant",
                status="completed",
                content=[
                    SimpleNamespace(
                        type="output_text",
                        text="".join(state.text_deltas),
                    )
                ],
            )
        ]
    else:
        return None

    return SimpleNamespace(
        output=output_items,
        output_text=output_text_from_items(output_items) or None,
        usage=usage,
        status="completed",
        model=model,
    )


def record_response_stream_event(event: Any, state: ResponsesStreamState) -> None:
    """Collect recovery data from one Responses stream event."""
    event_type = get_field(event, "type", "") or ""
    if event_type == "response.output_item.done":
        item = get_field(event, "item")
        if item is not None:
            state.output_items.append(item)
            if get_field(item, "type") == "function_call":
                state.has_function_calls = True
    elif "output_text.delta" in event_type:
        delta = get_field(event, "delta", "")
        if isinstance(delta, str) and delta:
            state.text_deltas.append(delta)
    elif "function_call" in event_type:
        state.has_function_calls = True


def backfill_response_output(
    response: Any,
    state: ResponsesStreamState,
    *,
    model: Optional[str] = None,
) -> Any:
    """Fill missing/empty final output from stream events when possible."""
    if response is None:
        return None

    output = get_field(response, "output")
    if output is not None and not (isinstance(output, list) and not output):
        if not get_field(response, "output_text"):
            text = output_text_from_items(list(output)) if isinstance(output, list) else ""
            if text:
                set_field(response, "output_text", text)
        return response

    recovered = build_recovered_response(state, model=model, usage=get_field(response, "usage"))
    if recovered is None:
        return response

    set_field(response, "output", recovered.output)
    if not get_field(response, "output_text"):
        set_field(response, "output_text", recovered.output_text)
    state.backfilled_final_output = True
    return response


def run_responses_stream_with_recovery(
    stream_factory: Callable[[], Any],
    *,
    on_event: Optional[Callable[[Any, ResponsesStreamState], None]] = None,
    model: Optional[str] = None,
    logger: Any = None,
    operation: str = "Codex Responses stream",
    log_context: str = "",
) -> Tuple[Any, ResponsesStreamState]:
    """Run a Responses stream and recover from terminal ``output=null`` drift.

    ``on_event`` runs after the shared collector has recorded the event, so
    callers can inspect ``state`` without duplicating parser-recovery state.
    """
    state = ResponsesStreamState()

    def _recover_or_raise(exc: TypeError) -> Any:
        if not is_null_output_iterable_error(exc):
            raise exc
        recovered = build_recovered_response(state, model=model)
        if recovered is None:
            raise exc
        state.recovered_from_parser_error = True
        if logger is not None:
            suffix = f" {log_context}" if log_context else ""
            log_method = logger.debug
            warn_key = (operation, model)
            with _WARNED_RECOVERY_LOCK:
                if warn_key not in _WARNED_RECOVERY_KEYS:
                    _WARNED_RECOVERY_KEYS.add(warn_key)
                    log_method = logger.warning
            log_method(
                "%s parser failed on terminal response.output=None; "
                "recovered %d output item(s), %d text delta part(s).%s",
                operation,
                len(state.output_items),
                len(state.text_deltas),
                suffix,
            )
        return recovered

    with stream_factory() as stream:
        try:
            iterator = iter(stream)
        except TypeError as exc:
            return _recover_or_raise(exc), state

        while True:
            try:
                event = next(iterator)
            except StopIteration:
                break
            except TypeError as exc:
                return _recover_or_raise(exc), state

            record_response_stream_event(event, state)
            if on_event is not None:
                on_event(event, state)

        try:
            final_response = stream.get_final_response()
        except TypeError as exc:
            return _recover_or_raise(exc), state

    final_response = backfill_response_output(final_response, state, model=model)
    if state.backfilled_final_output and logger is not None:
        suffix = f" {log_context}" if log_context else ""
        logger.debug(
            "%s backfilled missing final output from stream events "
            "(items=%d, text_parts=%d).%s",
            operation,
            len(state.output_items),
            len(state.text_deltas),
            suffix,
        )
    return final_response, state

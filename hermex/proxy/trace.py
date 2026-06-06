from __future__ import annotations

import json
from dataclasses import dataclass, field
from typing import Any

from hermex.core.embedding import embed_text
from hermex.core.store.base import CoreStore, TelemetryEvent


@dataclass
class ToolCallRecord:
    tool_name: str
    call_id: str | None = None
    param_keys: tuple[str, ...] = field(default_factory=tuple)

    @property
    def hash(self) -> str:
        return f"{self.tool_name}:{','.join(self.param_keys)}"


@dataclass
class ExtractedTrace:
    session_id: str
    tool_calls: list[ToolCallRecord] = field(default_factory=list)
    assistant_text: str = ""


class TraceExtractor:
    def __init__(self, store: CoreStore) -> None:
        self._store = store

    async def process(self, raw: bytes, session_id: str) -> None:
        trace = self._parse_sse(raw, session_id=session_id)
        if not trace.tool_calls and not trace.assistant_text.strip():
            return

        lowered = trace.assistant_text.lower()
        failed = any(marker in lowered for marker in ("error", "failed", "failure", "exception", "traceback"))
        summary = self._summarize(trace)
        tool_name = trace.tool_calls[0].tool_name if trace.tool_calls else None
        await self._store.telemetry.emit(
            TelemetryEvent(
                session_id=session_id,
                summary=summary,
                embedding=embed_text(summary),
                tool_name=tool_name,
                success=not failed,
                failure_reason=self._failure_reason(trace.assistant_text) if failed else None,
            )
        )

        hashes = [call.hash for call in trace.tool_calls]
        for left, right in zip(hashes, hashes[1:]):
            await self._store.patterns.increment((left, right), session_id)

    def _parse_sse(self, raw: bytes, session_id: str) -> ExtractedTrace:
        trace = ExtractedTrace(session_id=session_id)
        current_tool: dict[str, Any] | None = None
        input_accum = ""

        for line in raw.decode("utf-8", errors="replace").splitlines():
            if not line.startswith("data: "):
                continue
            payload = line[6:].strip()
            if not payload or payload == "[DONE]":
                continue
            try:
                event = json.loads(payload)
            except json.JSONDecodeError:
                continue

            event_type = event.get("type")
            if event_type == "content_block_start":
                block = event.get("content_block") or {}
                if block.get("type") == "tool_use":
                    current_tool = {"id": block.get("id"), "name": block.get("name")}
                    input_accum = ""
            elif event_type == "content_block_delta":
                delta = event.get("delta") or {}
                if delta.get("type") == "input_json_delta" and current_tool:
                    input_accum += str(delta.get("partial_json") or "")
                elif delta.get("type") == "text_delta":
                    trace.assistant_text += str(delta.get("text") or "")
            elif event_type == "content_block_stop" and current_tool:
                params = _parse_params(input_accum)
                trace.tool_calls.append(
                    ToolCallRecord(
                        tool_name=str(current_tool.get("name") or "unknown_tool"),
                        call_id=current_tool.get("id"),
                        param_keys=tuple(sorted(params.keys())),
                    )
                )
                current_tool = None
                input_accum = ""

        return trace

    @staticmethod
    def _summarize(trace: ExtractedTrace) -> str:
        tools = ", ".join(call.tool_name for call in trace.tool_calls)
        text = " ".join(trace.assistant_text.split())
        if tools and text:
            return f"Tools used: {tools}. Assistant observed: {text[:500]}"
        if tools:
            return f"Tools used: {tools}."
        return text[:500]

    @staticmethod
    def _failure_reason(text: str) -> str:
        cleaned = " ".join(text.split())
        return cleaned[:240] or "assistant indicated failure"


def _parse_params(raw: str) -> dict[str, Any]:
    if not raw:
        return {}
    try:
        parsed = json.loads(raw)
    except json.JSONDecodeError:
        return {}
    return parsed if isinstance(parsed, dict) else {}

"""Detect tool calls models emit inside the response ``content`` field (as JSON,
XML, or special tokens) instead of the structured ``tool_calls`` field, and
promote them to executed calls. Strict fallback: only consulted when the
transport returned no structured tool_calls.

Leaf module: imports only stdlib + agent.transports.types (itself a leaf).
Do NOT import agent.codex_responses_adapter — it pulls ~92 modules via
prompt_builder and this module sits on cli.py's import path.

See docs/plans/2026-05-29-content-bound-tool-call-extraction.md for rationale.
"""

from __future__ import annotations

import hashlib
import json
import logging
import os
import re
from dataclasses import dataclass
from typing import Any, Callable

from agent.transports.types import ToolCall, build_tool_call

logger = logging.getLogger(__name__)


def _deterministic_call_id(fn_name: str, arguments: str, index: int = 0) -> str:
    """``call_<sha256(name:args:index)[:12]>`` — stable id keeps the prompt cache
    warm. Mirrors agent/codex_responses_adapter.py (copied to keep this a leaf)."""
    digest = hashlib.sha256(f"{fn_name}:{arguments}:{index}".encode(errors="replace")).hexdigest()
    return f"call_{digest[:12]}"


@dataclass(frozen=True)
class RawCall:
    name: str
    arguments: Any  # dict or JSON string
    span: str  # exact substring matched (removed to form residual)


@dataclass(frozen=True)
class ContentFormat:
    name: str
    find_calls: Callable[[str], list[RawCall]]


FORMATS: list[ContentFormat] = []


def _loads_lenient(raw: str) -> Any | None:
    try:
        return json.loads(raw)
    except (json.JSONDecodeError, ValueError):
        return None


_TOOL_CALL_BLOCK_RE = re.compile(r"<tool_call>\s*(\{.*?\})\s*</tool_call>", re.DOTALL | re.IGNORECASE)


def find_tool_call_json(content: str) -> list[RawCall]:
    out: list[RawCall] = []
    for m in _TOOL_CALL_BLOCK_RE.finditer(content):
        obj = _loads_lenient(m.group(1))
        if isinstance(obj, dict) and isinstance(obj.get("name"), str):
            out.append(RawCall(name=obj["name"], arguments=obj.get("arguments", {}), span=m.group(0)))
    return out


FORMATS.append(ContentFormat("tool_call_json", find_tool_call_json))

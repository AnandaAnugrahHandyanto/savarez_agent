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


_MAX_BARE_JSON_ARGS = 16_000


def find_bare_json_object(content: str) -> list[RawCall]:
    s = content.strip()
    if not (s.startswith("{") and s.endswith("}")):  # whole-content-only
        return []
    obj = _loads_lenient(s)
    if not isinstance(obj, dict) or obj.keys() - {"name", "arguments"}:
        return []
    name, args = obj.get("name"), obj.get("arguments", {})
    if not name or not isinstance(name, str) or not isinstance(args, (dict, str)):
        return []
    serialized = json.dumps(args) if isinstance(args, dict) else args
    if len(serialized) > _MAX_BARE_JSON_ARGS:
        return []
    return [RawCall(name=name, arguments=args, span=content)]


FORMATS.append(ContentFormat("bare_json_object", find_bare_json_object))


_KIMI_SECTION_RE = re.compile(r"<\|tool_calls?_section_begin\|>(.*?)<\|tool_calls?_section_end\|>", re.DOTALL)
_KIMI_CALL_RE = re.compile(
    r"<\|tool_call_begin\|>\s*(?P<id>.*?)\s*<\|tool_call_argument_begin\|>(?P<args>.*?)<\|tool_call_end\|>",
    re.DOTALL,
)


def _kimi_name(raw_id: str) -> str:
    name = raw_id.strip().removeprefix("functions.")
    return name.rsplit(":", 1)[0].strip()


def find_kimi_k2(content: str) -> list[RawCall]:
    if "<|tool_call" not in content:
        return []
    out: list[RawCall] = []
    for section in _KIMI_SECTION_RE.finditer(content):
        for m in _KIMI_CALL_RE.finditer(section.group(1)):
            obj = _loads_lenient(m.group("args").strip())
            name = _kimi_name(m.group("id"))
            if name and isinstance(obj, dict):
                out.append(RawCall(name=name, arguments=obj, span=section.group(0)))
    return out


FORMATS.append(ContentFormat("kimi_k2", find_kimi_k2))


_INVOKE_RE = re.compile(r'<invoke\b[^>]*\bname\s*=\s*"([^"]+)"[^>]*>(.*?)</invoke>', re.DOTALL | re.IGNORECASE)
_PARAM_RE = re.compile(r'<parameter\b[^>]*\bname\s*=\s*"([^"]+)"[^>]*>(.*?)</parameter>', re.DOTALL | re.IGNORECASE)


def find_minimax_invoke(content: str) -> list[RawCall]:
    if "<invoke" not in content.lower():
        return []
    out: list[RawCall] = []
    for m in _INVOKE_RE.finditer(content):
        name = m.group(1).strip()
        args = {pn.strip(): pv.strip() for pn, pv in _PARAM_RE.findall(m.group(2))}
        if name:
            out.append(RawCall(name=name, arguments=args, span=m.group(0)))
    return out


FORMATS.append(ContentFormat("minimax_invoke", find_minimax_invoke))

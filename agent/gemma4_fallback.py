"""Gemma-4 special-token content fallback.

vLLM's ``gemma4`` tool-call / reasoning parsers intermittently fail to extract
Gemma-4's pipe-delimited markup, leaving it raw in ``message.content`` with an
empty ``message.tool_calls``. The agent then leaks the markup verbatim to the
user and never executes the tool. (Upstream: hermes-agent #6626 / #29115,
mlx-lm #1096.)

Gemma-4 emits (authoritative: ``tool_chat_template_gemma4.jinja``):

    tool call : ``<|tool_call>call:NAME{ARGS}<tool_call|>``
    reasoning : ``<|channel>thought\\n…\\n<channel|>``
    string    : wrapped in ``<|"|>…<|"|>`` (keys are BARE at every depth;
                numbers / booleans bare; objects ``{…}``; lists ``[…]``)

These helpers parse that markup back into structured tool_calls + reasoning so
the tool still executes and the visible message stays clean — with thinking
left ENABLED (no reasoning-off workaround). Pure stdlib, no agent imports, so
it is trivially unit-testable.
"""
from __future__ import annotations

import json
import re
from types import SimpleNamespace
from typing import List, Optional, Tuple

# String-literal delimiter (the only token that wraps free text).
_STR = '<|"|>'

# Complete spans.
_TOOLCALL_RE = re.compile(
    r'<\|tool_call>\s*call:\s*([A-Za-z0-9_.\-]+)\s*\{(.*?)\}\s*<tool_call\|>',
    re.DOTALL,
)
_CHANNEL_RE = re.compile(r'<\|channel>(.*?)<channel\|>', re.DOTALL)

# Unterminated spans (stream truncated / parser dropped the closer).
_TOOLCALL_OPEN_RE = re.compile(r'<\|tool_call>.*\Z', re.DOTALL)
_CHANNEL_OPEN_RE = re.compile(r'<\|channel>.*\Z', re.DOTALL)

# Residual bare Gemma special tokens (string delimiter + known opens/closes).
_RESIDUAL_RE = re.compile(
    r'<\|"\|>'
    r'|<\|(?:tool_call|channel|turn|tool|tool_response|think|image|audio|video)\b[^>]*>'
    r'|<(?:tool_call|channel|turn|tool|tool_response)\|>'
)

# Quote a bare key: identifier directly before ':' at start / after ',' or '{'.
_BARE_KEY_RE = re.compile(r'([{,]\s*|^\s*)([A-Za-z_][A-Za-z0-9_.\-]*)\s*:')


def _gemma_args_to_json(body: str) -> str:
    """Convert a Gemma-serialized argument body (text between the call's outer
    braces) into a JSON object string.

    Strings are extracted first (odd segments between ``<|"|>`` delimiters) and
    JSON-encoded, so any ``:`` / ``,`` / ``{`` / ``}`` inside a literal can't
    corrupt the structural parse. Bare keys are quoted per structural segment
    only — never inside an encoded string literal (which would otherwise
    mangle a value like ``"a,b:c"``).
    """
    if not body.strip():
        return "{}"
    segs = body.split(_STR)
    out: List[str] = []
    for i, seg in enumerate(segs):
        if i % 2 == 1:
            # String literal — JSON-encode (handles quotes, newlines, etc.).
            out.append(json.dumps(seg))
        else:
            # Structural skeleton — quote bare keys, normalise Python ``None``.
            seg = _BARE_KEY_RE.sub(lambda m: f'{m.group(1)}"{m.group(2)}":', seg)
            seg = re.sub(r':\s*None\b', ':null', seg)
            out.append(seg)
    return "{" + "".join(out) + "}"


def parse_gemma_tool_calls(content: str) -> Tuple[List[SimpleNamespace], str]:
    """Parse ``<|tool_call>call:NAME{…}<tool_call|>`` blocks out of *content*.

    Returns ``(tool_calls, cleaned_content)`` where each tool call is a
    ``SimpleNamespace`` shaped like an OpenAI tool call (``.id``, ``.type``,
    ``.function.name``, ``.function.arguments`` as a JSON string). Empty list
    when no complete block is present. ``cleaned_content`` has the parsed
    blocks (and any unterminated trailing open) removed.
    """
    if not content or "<|tool_call>" not in content:
        return [], content
    calls: List[SimpleNamespace] = []
    for i, m in enumerate(_TOOLCALL_RE.finditer(content)):
        name = m.group(1)
        try:
            args_json = _gemma_args_to_json(m.group(2))
            json.loads(args_json)  # validate
        except (ValueError, TypeError):
            # Best-effort: run the tool with empty args and let the model
            # recover from the tool error — far better than leaking markup.
            args_json = "{}"
        calls.append(
            SimpleNamespace(
                id=f"call_gemma_{i}",
                type="function",
                function=SimpleNamespace(name=name, arguments=args_json),
            )
        )
    cleaned = _TOOLCALL_RE.sub("", content)
    cleaned = _TOOLCALL_OPEN_RE.sub("", cleaned)
    return calls, cleaned


def extract_gemma_reasoning(content: str) -> Tuple[Optional[str], str]:
    """Pull ``<|channel>…<channel|>`` reasoning out of *content*.

    Returns ``(reasoning_text_or_None, cleaned_content)``. A leading channel
    label line (e.g. ``thought``) is dropped from the captured reasoning.
    """
    if not content or "<|channel>" not in content:
        return None, content
    chunks: List[str] = []
    for m in _CHANNEL_RE.finditer(content):
        body = m.group(1)
        # Drop a leading channel-name label ("thought\n…").
        body = re.sub(r'^[ \t]*[A-Za-z0-9_\-]+[ \t]*\n', '', body, count=1)
        body = body.strip()
        if body:
            chunks.append(body)
    cleaned = _CHANNEL_RE.sub("", content)
    cleaned = _CHANNEL_OPEN_RE.sub("", cleaned)
    return ("\n\n".join(chunks) or None), cleaned


def strip_gemma_markup(content: str) -> str:
    """Remove every Gemma-4 pipe-delimited special-token span from *content*.

    Defence-in-depth for ``strip_think_blocks``: complete + unterminated
    tool-call and channel spans, then any residual bare special token.
    """
    if not content or ("<|" not in content and "|>" not in content):
        return content
    content = _TOOLCALL_RE.sub("", content)
    content = _CHANNEL_RE.sub("", content)
    content = _TOOLCALL_OPEN_RE.sub("", content)
    content = _CHANNEL_OPEN_RE.sub("", content)
    content = _RESIDUAL_RE.sub("", content)
    return content


def apply_gemma_fallback(assistant_message) -> bool:
    """Recover a Gemma-4 tool call that leaked into content.

    Mutates *assistant_message* in place: when ``tool_calls`` is empty and the
    content carries ``<|tool_call>`` markup, parse it into structured
    ``tool_calls`` and strip that markup from ``content``. Returns ``True`` if a
    tool call was recovered. No-op (``False``) when tool_calls already exist or
    no markup is found. Channel/reasoning markup is intentionally left in
    content for the reasoning-extraction layer (``build_assistant_message`` /
    ``strip_think_blocks``) to handle.
    """
    if getattr(assistant_message, "tool_calls", None):
        return False
    content = getattr(assistant_message, "content", None)
    if not content or "<|tool_call>" not in content:
        return False
    calls, cleaned = parse_gemma_tool_calls(content)
    if not calls:
        return False
    assistant_message.tool_calls = calls
    try:
        assistant_message.content = cleaned
    except Exception:
        pass
    return True

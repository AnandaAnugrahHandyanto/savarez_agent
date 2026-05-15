"""Tool result persistence -- preserves large outputs instead of truncating.

Defense against context-window overflow operates at three levels:

1. **Per-tool output cap** (inside each tool): Tools like search_files
   pre-truncate their own output before returning. This is the first line
   of defense and the only one the tool author controls.

2. **Per-result persistence** (maybe_persist_tool_result): After a tool
   returns, if its output exceeds the tool's registered threshold
   (registry.get_max_result_size), the full output is written INTO THE
   SANDBOX temp dir (for example /tmp/hermes-results/{tool_use_id}.txt on
   standard Linux, or $TMPDIR/hermes-results/{tool_use_id}.txt on Termux)
   via env.execute(). The in-context content is replaced with a preview +
   file path reference. The model can read_file to access the full output
   on any backend.

3. **Per-turn aggregate budget** (enforce_turn_budget): After all tool
   results in a single assistant turn are collected, if the total exceeds
   MAX_TURN_BUDGET_CHARS (200K), the largest non-persisted results are
   spilled to disk until the aggregate is under budget. This catches cases
   where many medium-sized results combine to overflow context.
"""

import json
import logging
import os
import shlex
import uuid

from tools.budget_config import (
    DEFAULT_PREVIEW_SIZE_CHARS,
    BudgetConfig,
    DEFAULT_BUDGET,
)

logger = logging.getLogger(__name__)
PERSISTED_OUTPUT_TAG = "<persisted-output>"
PERSISTED_OUTPUT_CLOSING_TAG = "</persisted-output>"
STORAGE_DIR = "/tmp/hermes-results"
HEREDOC_MARKER = "HERMES_PERSIST_EOF"
_BUDGET_TOOL_NAME = "__budget_enforcement__"
_MAX_STRUCTURED_DEPTH = 3
_MAX_STRUCTURED_ITEMS = 8
_MAX_STRUCTURED_STRING = 160
_BULKY_KEYS = {
    "audio",
    "audio_base64",
    "base64",
    "blob",
    "content_base64",
    "data_uri",
    "html",
    "image",
    "image_base64",
    "media",
    "raw",
    "raw_content",
    "raw_html",
    "raw_output",
    "screenshot",
    "screenshot_base64",
    "video",
    "video_base64",
}
_PRIORITY_KEYS = (
    "success",
    "status",
    "error",
    "message",
    "exit_code",
    "returncode",
    "path",
    "file_path",
    "url",
    "source",
    "source_url",
    "source_id",
    "document_id",
    "title",
    "total",
    "total_count",
    "count",
    "line",
    "line_number",
    "results",
    "matches",
    "items",
    "data",
    "output",
)
_MAX_OMITTED_KEY_NAMES = 20


def _resolve_storage_dir(env) -> str:
    """Return the best temp-backed storage dir for this environment."""
    if env is not None:
        get_temp_dir = getattr(env, "get_temp_dir", None)
        if callable(get_temp_dir):
            try:
                temp_dir = get_temp_dir()
            except Exception as exc:
                logger.debug("Could not resolve env temp dir: %s", exc)
            else:
                if temp_dir:
                    temp_dir = temp_dir.rstrip("/") or "/"
                    return f"{temp_dir}/hermes-results"
    return STORAGE_DIR


def _truncate_text(text: str, max_chars: int = _MAX_STRUCTURED_STRING) -> str:
    """Return a bounded text snippet that preserves head/tail context."""
    if len(text) <= max_chars:
        return text
    half = max(1, max_chars // 2)
    omitted = len(text) - (half * 2)
    return f"{text[:half]}… [omitted {omitted:,} chars] …{text[-half:]}"


def _looks_like_base64(text: str) -> bool:
    """Heuristic for bulky media/blob strings that should not enter context."""
    if len(text) < 512:
        return False
    sample = text[:2048]
    allowed = set("ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz0123456789+/=\n\r")
    if any(ch not in allowed for ch in sample):
        return False
    non_ws = sum(1 for ch in sample if not ch.isspace())
    return non_ws / max(1, len(sample)) > 0.90


def _looks_like_data_uri(text: str) -> bool:
    """Detect embedded data URI media regardless of which JSON key carries it."""
    prefix = text[:128].lower()
    return prefix.startswith("data:") and ";base64," in prefix


def _describe_omitted_value(value) -> str:
    """Describe omitted data without stringifying large nested containers."""
    if isinstance(value, str):
        return f"{len(value):,} chars"
    if isinstance(value, dict):
        return f"{len(value):,} keys"
    if isinstance(value, list):
        return f"{len(value):,} items"
    return type(value).__name__


def _summarize_json_key(key: str) -> tuple[str, bool]:
    """Bound/redact JSON object keys before they enter preview context."""
    if _looks_like_data_uri(key):
        return f"[omitted data URI key: {len(key):,} chars]", True
    if _looks_like_base64(key):
        return f"[omitted base64-like key: {len(key):,} chars]", True
    if len(key) > _MAX_STRUCTURED_STRING:
        return _truncate_text(key), True
    return key, False


def _summarize_json_value(value, *, key: str | None = None, depth: int = 0) -> tuple[object, bool]:
    """Build a compact, source-handle-preserving preview for JSON-like data."""
    lowered_key = (key or "").lower()
    if lowered_key in _BULKY_KEYS:
        return f"[omitted bulky field {lowered_key!r}: {_describe_omitted_value(value)}]", True

    if isinstance(value, str):
        if _looks_like_data_uri(value):
            return f"[omitted data URI: {len(value):,} chars]", True
        if _looks_like_base64(value):
            return f"[omitted base64-like string: {len(value):,} chars]", True
        if len(value) > _MAX_STRUCTURED_STRING:
            return _truncate_text(value), True
        return value, False
    if value is None or isinstance(value, (bool, int, float)):
        return value, False
    if depth >= _MAX_STRUCTURED_DEPTH:
        return f"[{type(value).__name__} omitted at depth {depth}: {_describe_omitted_value(value)}]", True
    if isinstance(value, list):
        summarized = []
        reduced = len(value) > _MAX_STRUCTURED_ITEMS
        for item in value[:_MAX_STRUCTURED_ITEMS]:
            item_summary, item_reduced = _summarize_json_value(item, depth=depth + 1)
            summarized.append(item_summary)
            reduced = reduced or item_reduced
        if len(value) > _MAX_STRUCTURED_ITEMS:
            summarized.append(f"… {len(value) - _MAX_STRUCTURED_ITEMS:,} more items omitted")
        return summarized, reduced
    if isinstance(value, dict):
        ordered_keys: list[str] = []
        for priority in _PRIORITY_KEYS:
            if priority in value:
                ordered_keys.append(priority)
        for existing_key in value:
            if existing_key not in ordered_keys:
                ordered_keys.append(existing_key)

        summarized: dict[str, object] = {}
        reduced = len(ordered_keys) > _MAX_STRUCTURED_ITEMS
        for existing_key in ordered_keys[:_MAX_STRUCTURED_ITEMS]:
            preview_key, key_was_reduced = _summarize_json_key(str(existing_key))
            key_summary, key_reduced = _summarize_json_value(
                value[existing_key],
                key=existing_key,
                depth=depth + 1,
            )
            summarized[preview_key] = key_summary
            reduced = reduced or key_reduced or key_was_reduced
        if len(ordered_keys) > _MAX_STRUCTURED_ITEMS:
            omitted_keys = ordered_keys[_MAX_STRUCTURED_ITEMS:]
            omitted_key_previews = []
            for omitted_key in omitted_keys[:_MAX_OMITTED_KEY_NAMES]:
                preview_key, key_was_reduced = _summarize_json_key(str(omitted_key))
                omitted_key_previews.append(preview_key)
                reduced = reduced or key_was_reduced
            summarized["_omitted_keys"] = omitted_key_previews
            if len(omitted_keys) > _MAX_OMITTED_KEY_NAMES:
                summarized["_omitted_key_count"] = len(omitted_keys)
        return summarized, reduced
    return _truncate_text(str(value)), True


def _generate_structured_preview(content: str, max_chars: int) -> tuple[str, bool] | None:
    """Return a compact JSON preview when content is parseable structured data."""
    stripped = content.strip()
    if not stripped or stripped[0] not in "[{":
        return None
    try:
        parsed = json.loads(stripped)
    except Exception:
        return None

    summary, reduced = _summarize_json_value(parsed)
    preview = json.dumps(summary, ensure_ascii=False, indent=2)
    if len(preview) <= max_chars:
        return preview, reduced
    text_preview, _ = _generate_text_preview(preview, max_chars=max_chars)
    return text_preview, True


def _generate_text_preview(content: str, max_chars: int = DEFAULT_PREVIEW_SIZE_CHARS) -> tuple[str, bool]:
    """Truncate at last newline within max_chars. Returns (preview, has_more)."""
    if len(content) <= max_chars:
        return content, False
    truncated = content[:max_chars]
    last_nl = truncated.rfind("\n")
    if last_nl > max_chars // 2:
        truncated = truncated[:last_nl + 1]
    return truncated, True


def generate_preview(content: str, max_chars: int = DEFAULT_PREVIEW_SIZE_CHARS) -> tuple[str, bool]:
    """Generate a compact context preview for a persisted tool result.

    Structured JSON gets summarized so source handles, counts, and errors stay
    visible while raw payload/media fields are omitted from the model context.
    Plain text keeps the legacy newline-aware preview behavior.
    """
    structured = _generate_structured_preview(content, max_chars=max_chars)
    if structured is not None:
        return structured
    return _generate_text_preview(content, max_chars=max_chars)


def _heredoc_marker(content: str) -> str:
    """Return a heredoc delimiter that doesn't collide with content."""
    if HEREDOC_MARKER not in content:
        return HEREDOC_MARKER
    return f"HERMES_PERSIST_{uuid.uuid4().hex[:8]}"


def _write_to_sandbox(content: str, remote_path: str, env) -> bool:
    """Write content into the sandbox via env.execute(). Returns True on success.

    Pushes ``content`` through stdin rather than embedding it in the command
    string. Linux's ``MAX_ARG_STRLEN`` caps any single argv element at 128 KB
    (32 * PAGE_SIZE), so the previous heredoc-in-the-command-string approach
    silently failed with ``OSError: [Errno 7] Argument list too long`` for any
    tool result over ~128 KB — exactly the case persistence exists to handle.
    Routing through stdin removes that ceiling on local + ssh (``_stdin_mode
    == "pipe"``); remote backends with ``_stdin_mode == "heredoc"`` keep their
    existing API-body sized limit, which is orders of magnitude larger than
    the exec-arg ceiling.
    """
    storage_dir = os.path.dirname(remote_path)
    cmd = f"mkdir -p {shlex.quote(storage_dir)} && cat > {shlex.quote(remote_path)}"
    result = env.execute(cmd, timeout=30, stdin_data=content)
    return result.get("returncode", 1) == 0


def _build_persisted_message(
    preview: str,
    has_more: bool,
    original_size: int,
    file_path: str,
) -> str:
    """Build the <persisted-output> replacement block."""
    size_kb = original_size / 1024
    if size_kb >= 1024:
        size_str = f"{size_kb / 1024:.1f} MB"
    else:
        size_str = f"{size_kb:.1f} KB"

    msg = f"{PERSISTED_OUTPUT_TAG}\n"
    msg += f"This tool result was too large ({original_size:,} characters, {size_str}).\n"
    msg += f"Full output saved to: {file_path}\n"
    msg += "Use the read_file tool with offset and limit to access specific sections of this output.\n\n"
    msg += f"Preview (first {len(preview)} chars):\n"
    msg += preview
    if has_more:
        msg += "\n..."
    msg += f"\n{PERSISTED_OUTPUT_CLOSING_TAG}"
    return msg


def maybe_persist_tool_result(
    content: str,
    tool_name: str,
    tool_use_id: str,
    env=None,
    config: BudgetConfig = DEFAULT_BUDGET,
    threshold: int | float | None = None,
) -> str:
    """Layer 2: persist oversized result into the sandbox, return preview + path.

    Writes via env.execute() so the file is accessible from any backend
    (local, Docker, SSH, Modal, Daytona). Falls back to inline truncation
    if write fails or no env is available.

    Args:
        content: Raw tool result string.
        tool_name: Name of the tool (used for threshold lookup).
        tool_use_id: Unique ID for this tool call (used as filename).
        env: The active BaseEnvironment instance, or None.
        config: BudgetConfig controlling thresholds and preview size.
        threshold: Explicit override; takes precedence over config resolution.

    Returns:
        Original content if small, or <persisted-output> replacement.
    """
    effective_threshold = threshold if threshold is not None else config.resolve_threshold(tool_name)

    if effective_threshold == float("inf"):
        return content

    if len(content) <= effective_threshold:
        return content

    storage_dir = _resolve_storage_dir(env)
    remote_path = f"{storage_dir}/{tool_use_id}.txt"
    preview, has_more = generate_preview(content, max_chars=config.preview_size)

    if env is not None:
        try:
            if _write_to_sandbox(content, remote_path, env):
                logger.info(
                    "Persisted large tool result: %s (%s, %d chars -> %s)",
                    tool_name, tool_use_id, len(content), remote_path,
                )
                return _build_persisted_message(preview, has_more, len(content), remote_path)
        except Exception as exc:
            logger.warning("Sandbox write failed for %s: %s", tool_use_id, exc)

    logger.info(
        "Inline-truncating large tool result: %s (%d chars, no sandbox write)",
        tool_name, len(content),
    )
    return (
        f"{preview}\n\n"
        f"[Truncated: tool response was {len(content):,} chars. "
        f"Full output could not be saved to sandbox.]"
    )


def enforce_turn_budget(
    tool_messages: list[dict],
    env=None,
    config: BudgetConfig = DEFAULT_BUDGET,
) -> list[dict]:
    """Layer 3: enforce aggregate budget across all tool results in a turn.

    If total chars exceed budget, persist the largest non-persisted results
    first (via sandbox write) until under budget. Already-persisted results
    are skipped.

    Mutates the list in-place and returns it.
    """
    candidates = []
    total_size = 0
    for i, msg in enumerate(tool_messages):
        content = msg.get("content", "")
        size = len(content)
        total_size += size
        if PERSISTED_OUTPUT_TAG not in content:
            candidates.append((i, size))

    if total_size <= config.turn_budget:
        return tool_messages

    candidates.sort(key=lambda x: x[1], reverse=True)

    for idx, size in candidates:
        if total_size <= config.turn_budget:
            break
        msg = tool_messages[idx]
        content = msg["content"]
        tool_use_id = msg.get("tool_call_id", f"budget_{idx}")

        replacement = maybe_persist_tool_result(
            content=content,
            tool_name=_BUDGET_TOOL_NAME,
            tool_use_id=tool_use_id,
            env=env,
            config=config,
            threshold=0,
        )
        if replacement != content:
            total_size -= size
            total_size += len(replacement)
            tool_messages[idx]["content"] = replacement
            logger.info(
                "Budget enforcement: persisted tool result %s (%d chars)",
                tool_use_id, size,
            )

    return tool_messages

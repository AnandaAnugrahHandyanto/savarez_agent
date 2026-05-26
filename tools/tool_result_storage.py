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

import logging
import os
import re
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
TERMINAL_TOOL_NAME = "terminal"
TERMINAL_ERROR_PATTERN = re.compile(
    r"\b(ERROR|WARN|WARNING|FATAL|Exception|Traceback|error:|failed|FAILED|AssertionError)\b",
    re.IGNORECASE,
)


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


def _smart_terminal_summary(
    content: str,
    *,
    file_path: str | None = None,
    head_lines: int = 50,
    tail_lines: int = 50,
    max_error_lines: int = 50,
) -> str:
    """Build head/tail/error summary for large terminal output."""
    lines = content.splitlines(keepends=True)
    total_lines = len(lines)
    total_chars = len(content)
    head = lines[:head_lines]
    tail = lines[-tail_lines:] if total_lines > head_lines else []

    seen = set()
    error_lines = []
    for line in lines:
        if not TERMINAL_ERROR_PATTERN.search(line):
            continue
        key = line.strip()
        if key in seen:
            continue
        seen.add(key)
        error_lines.append(line)
        if len(error_lines) >= max_error_lines:
            break

    location = f" — full output saved to {file_path}" if file_path else ""
    parts = [
        f"[TERMINAL OUTPUT SUMMARY — {total_lines} lines, {total_chars} chars{location}]\n\n"
    ]
    if head:
        parts.append(f"=== HEAD ({min(head_lines, total_lines)} lines) ===\n")
        parts.extend(head)
        parts.append("\n")
    if total_lines > head_lines + tail_lines:
        parts.append(f"... [{total_lines - head_lines - tail_lines} lines omitted — see full file] ...\n\n")
    if tail and total_lines > head_lines:
        parts.append(f"=== TAIL ({min(tail_lines, total_lines)} lines) ===\n")
        parts.extend(tail)
        parts.append("\n")
    if error_lines:
        parts.append(f"=== ERRORS/WARNINGS ({len(error_lines)} unique matches) ===\n")
        parts.extend(error_lines)
        parts.append("\n")
    elif total_lines > head_lines:
        parts.append("=== ERRORS/WARNINGS: none found ===\n")
    if file_path:
        parts.append(f"Full output: {file_path}\n")
    return "".join(parts)


def generate_preview(
    content: str,
    max_chars: int = DEFAULT_PREVIEW_SIZE_CHARS,
    tool_name: str | None = None,
    file_path: str | None = None,
) -> tuple[str, bool]:
    """Truncate at last newline within max_chars. Returns (preview, has_more)."""
    if tool_name == TERMINAL_TOOL_NAME:
        try:
            from tools.tool_output_limits import get_terminal_summary_config
            summary_cfg = get_terminal_summary_config()
        except Exception:
            summary_cfg = {
                "threshold": 5_000,
                "head_lines": 50,
                "tail_lines": 50,
                "max_error_lines": 50,
            }
        if len(content) > summary_cfg["threshold"]:
            return (
                _smart_terminal_summary(
                    content,
                    file_path=file_path,
                    head_lines=summary_cfg["head_lines"],
                    tail_lines=summary_cfg["tail_lines"],
                    max_error_lines=summary_cfg["max_error_lines"],
                ),
                True,
            )
    if len(content) <= max_chars:
        return content, False
    truncated = content[:max_chars]
    last_nl = truncated.rfind("\n")
    if last_nl > max_chars // 2:
        truncated = truncated[:last_nl + 1]
    return truncated, True


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
    if preview.startswith("[TERMINAL OUTPUT SUMMARY"):
        msg += "Preview:\n"
    else:
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

    if tool_name == TERMINAL_TOOL_NAME and effective_threshold != float("inf"):
        try:
            from tools.tool_output_limits import get_terminal_summary_config
            terminal_threshold = get_terminal_summary_config()["threshold"]
        except Exception:
            terminal_threshold = 5_000
        effective_threshold = min(int(effective_threshold), terminal_threshold)

    if effective_threshold == float("inf"):
        return content

    if len(content) <= effective_threshold:
        return content

    storage_dir = _resolve_storage_dir(env)
    remote_path = f"{storage_dir}/{tool_use_id}.txt"
    preview, has_more = generate_preview(
        content,
        max_chars=config.preview_size,
        tool_name=tool_name,
        file_path=remote_path,
    )

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

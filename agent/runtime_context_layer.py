from __future__ import annotations

from datetime import datetime
from pathlib import Path
from typing import Any

from agent.timeline_sync import (
    _decode_preview,
    _default_db_path,
    _format_duration,
    _format_time,
    _coerce_now,
    describe_elapsed,
    get_last_user_message_time,
    get_recent_events,
)


def _block(name: str, lines: list[str]) -> str:
    return "\n".join([f"[{name}]", *lines, f"[/{name}]"])


def _bool_text(value: bool) -> str:
    return "true" if value else "false"


def _as_text_list(values: list[str]) -> str:
    return ", ".join(v for v in values if v)


def _gap_short_label(seconds: float | None) -> str:
    if seconds is None:
        return "unknown"
    seconds = max(0.0, float(seconds))
    if seconds < 120:
        return "immediate"
    if seconds < 30 * 60:
        return "short_pause"
    if seconds < 6 * 3600:
        return "same_day_pause"
    if seconds < 24 * 3600:
        return "long_same_day_pause"
    return "older_pause"


def _reply_mode_for_gap(seconds: float | None) -> str:
    if seconds is None:
        return "direct_answer"
    if seconds < 120:
        return "direct_answer"
    if seconds < 30 * 60:
        return "light_resume"
    if seconds < 6 * 3600:
        return "recap_resume"
    return "full_recap"


def _timing_phrase_guidance(seconds: float | None) -> tuple[list[str], list[str], str]:
    if seconds is None:
        return ["earlier", "to continue", "to pick this back up"], ["just now"], "Use neutral continuation wording."
    if seconds < 120:
        return ["to continue", "on that"], ["last time"], "Treat as a live continuation."
    if seconds < 30 * 60:
        return ["earlier", "to continue", "picking this up"], ["just now", "right now"], "Use light continuation wording without over-recapping."
    return ["earlier", "to pick this back up", "returning to this"], ["just now", "right now", "a moment ago"], "Briefly restore context before continuing."


def _korean_phrase_guidance(seconds: float | None) -> tuple[list[str], list[str]]:
    if seconds is not None and seconds < 120:
        return ["이어가면", "그 흐름에서"], ["지난번", "오랜만"]
    if seconds is not None and seconds < 30 * 60:
        return ["아까", "조금 전", "이어가면"], ["오랜만", "지난번"]
    return ["전에", "이어가면", "다시 잡아보면"], ["방금", "지금 막", "바로 전", "바로"]


def _recent_user_previews(conversation_history: list[dict[str, Any]] | None, user_message: str = "") -> list[str]:
    previews: list[str] = []
    for msg in reversed(conversation_history or []):
        if not isinstance(msg, dict) or msg.get("role") != "user":
            continue
        preview = _decode_preview(msg.get("content"), max_chars=90)
        if preview and preview not in previews:
            previews.append(preview)
        if len(previews) >= 3:
            break
    current_preview = _decode_preview(user_message, max_chars=90) if user_message else ""
    if current_preview and current_preview not in previews:
        previews.insert(0, current_preview)
    return previews[:3]


def build_timeline_sync_block(
    *,
    db_path: str | Path | None = None,
    now: Any = None,
    session_id: str = "",
    platform: str = "",
    recent_window_minutes: int = 30,
    max_events: int = 8,
    include_other_platforms: bool = True,
) -> str:
    current = _coerce_now(now)
    path = Path(db_path) if db_path else _default_db_path()
    current_ts = current.timestamp()
    last_user_ts = get_last_user_message_time(db_path=path, session_id=session_id)
    elapsed = describe_elapsed(current_ts - last_user_ts) if last_user_ts else None

    lines = [f"Current real time: {current.strftime('%Y-%m-%d %H:%M:%S %Z').strip()}."]
    if platform:
        lines.append(f"Current platform: {platform}.")
    if session_id:
        lines.append(f"Current session: {session_id}.")
    if elapsed:
        lines.append(f"Elapsed since last user message in this session: {elapsed.text}.")
        lines.append(f"Interpretation: {elapsed.guidance}")
    else:
        lines.append("Elapsed since last user message in this session: unknown.")

    if include_other_platforms:
        since_ts = current_ts - max(0, int(recent_window_minutes)) * 60
        events = get_recent_events(
            db_path=path,
            since_ts=since_ts,
            limit=max_events,
            exclude_session_id=session_id or None,
        )
        if events:
            lines.append(f"Recent cross-platform events in the last {recent_window_minutes} minutes:")
            for event in events:
                source = str(event.get("source") or "unknown").upper()
                when = _format_time(float(event["timestamp"]), current)
                preview = event.get("preview") or "(empty)"
                lines.append(f"- {when} {source}: {preview}")
        else:
            lines.append(f"Recent cross-platform events in the last {recent_window_minutes} minutes: none found.")
    lines.append('Instruction: use real elapsed time when saying "just now", "earlier", or "last time". Avoid saying "just now" when the gap is not immediate.')
    return _block("Timeline sync", lines)


def build_rhythm_context_block(
    *,
    now: Any = None,
    last_user_ts: float | None = None,
    platform: str = "",
    recent_events: list[dict[str, Any]] | None = None,
) -> str:
    current = _coerce_now(now)
    elapsed_seconds = current.timestamp() - last_user_ts if last_user_ts else None
    gap = describe_elapsed(elapsed_seconds) if elapsed_seconds is not None else None
    reply_mode = _reply_mode_for_gap(elapsed_seconds)
    gap_bucket = _gap_short_label(elapsed_seconds)
    gap_display = gap.text if gap else "unknown"
    baseline_seconds = 5 * 60
    gap_vs_baseline = "unknown"
    if elapsed_seconds is not None:
        gap_vs_baseline = "longer_than_usual" if elapsed_seconds > baseline_seconds * 1.5 else "within_baseline"
    lines = [
        f"Gap: {gap_display} ({gap_bucket})",
        f"Baseline gap: {_format_duration(baseline_seconds)}",
        f"Gap vs baseline: {gap_vs_baseline}",
        "Burst score: 0.00",
        "Crossed day boundary: false",
        "Silence meaning: attention_shift" if elapsed_seconds and elapsed_seconds >= 120 else "Silence meaning: continuous_thread",
        f"Reply mode: {reply_mode}",
        "Instruction: Acknowledge the pause only if useful, then continue the thread.",
    ]
    if recent_events:
        lines.append("Recent rhythm events:")
        for event in recent_events[:5]:
            event_ts = float(event.get("timestamp") or 0.0)
            age = describe_elapsed(current.timestamp() - event_ts).text
            source = event.get("source") or platform or "unknown"
            role = event.get("role") or "user"
            preview = event.get("preview") or "(empty)"
            lines.append(f"- {age} ago {source}/{role} — {preview}")
    return _block("Rhythm context", lines)


def build_expression_context_block(*, elapsed_seconds: float | None = None) -> str:
    prefer, avoid = _korean_phrase_guidance(elapsed_seconds)
    _, _, instruction = _timing_phrase_guidance(elapsed_seconds)
    return _block(
        "Expression context",
        [
            f"Prefer: {_as_text_list(prefer)}",
            f"Avoid: {_as_text_list(avoid)}",
            f"Instruction: {instruction}",
        ],
    )


def build_first_line_context_block(*, reply_mode: str, elapsed_seconds: float | None = None) -> str:
    suggested = "이어가면" if reply_mode in {"light_resume", "recap_resume", "full_recap"} else ""
    lines = [
        f"Suggested first line: {suggested or '(none)'}",
        "Task mode: answer_request",
        "Instruction: Use only when it fits the answer; do not force it.",
    ]
    return _block("First-line context", lines)


def build_reply_hygiene_block(*, platform: str = "") -> str:
    chat_platform = platform.lower() in {"telegram", "slack", "discord", "whatsapp", "signal", "matrix"}
    return _block(
        "Reply hygiene",
        [
            f"Send progress: {_bool_text(not chat_platform)}",
            "Repeat source quote: false",
            "Final report style: grouped_completion",
            "Allow question: false",
            "Max question count: 0",
            "Keep thread context: false",
            "Instruction: Avoid progress bubbles and repeated quotes; put the useful result in the final answer.",
        ],
    )


def build_tone_precision_block(*, reply_mode: str) -> str:
    level = "neutral" if reply_mode in {"direct_answer", "light_resume"} else "careful"
    return _block(
        "Tone precision",
        [
            f"Level: {level}",
            "Do: answer_request, avoid_wrapper_echo",
            "Avoid: unsupported_timeline_claim, repeated_source_quote",
            "Instruction: Answer the request without echoing platform or context wrapper text.",
        ],
    )


def build_return_tone_block(*, reply_mode: str) -> str:
    state_gap = reply_mode in {"recap_resume", "full_recap"}
    return _block(
        "Return tone",
        [
            "Style: neutral_helpful" if not state_gap else "Style: warm_grounded_reentry",
            "Opening intent: answer_normally" if not state_gap else "Opening intent: restore_then_continue",
            f"State gap: {_bool_text(state_gap)}",
            "Cautions: avoid_wrapper_echo, avoid_unverified_memory_claim",
            "Instruction: Answer normally and keep platform wrapper text out of the reply." if not state_gap else "Instruction: Briefly restore the working context, then continue in a warm but grounded tone.",
        ],
    )


def build_presence_guard_block(*, elapsed_seconds: float | None = None) -> str:
    risk = "low" if elapsed_seconds is not None and elapsed_seconds < 120 else "guarded"
    return _block(
        "Presence guard",
        [
            f"Risk level: {risk}",
            "Avoid presence claims: 방금, 지금 막, 바로",
            "Instruction: Avoid claiming real-time presence or immediate continuity unless the gap is short.",
        ],
    )


def build_scratchpad_leak_guard_block() -> str:
    return _block(
        "Scratchpad leak guard",
        [
            "Risk level: strict",
            "Do not send internal planning notes, scratchpad fragments, or tool-operation comments to the user.",
            "Avoid examples: Need..., Run..., Implement..., Add in build, Tool warning, patch notes before final.",
            "Instruction: Use tool calls silently; send only the final user-facing summary after verification.",
        ],
    )


def build_platform_digest_block(*, platform: str = "", conversation_history: list[dict[str, Any]] | None = None, user_message: str = "") -> str:
    previews = _recent_user_previews(conversation_history, user_message)
    if not previews:
        previews = ["(none)"]
    lines = [f"{platform or 'current'}:"]
    for preview in previews:
        lines.append(f"- user: {preview}")
    return _block("Platform digest", lines)


def build_memory_guard_block(*, user_message: str = "") -> str:
    text = str(user_message or "").strip()
    lower = text.lower()
    wrapper_markers = ("[timeline sync]", "[rhythm context]", "[reply hygiene]", "[memory guard]")
    category = "do_not_persist" if lower.startswith(wrapper_markers) else "needs_review"
    persist = "false"
    return _block(
        "Memory guard",
        [
            f"User message category: {category}",
            "Requires live verification: false",
            f"Persist to memory: {persist}",
            "Instruction: Do not save live wrappers, temporary work state, or scratchpad leaks as durable memory.",
        ],
    )


def build_runtime_context(
    *,
    db_path: str | Path | None = None,
    now: Any = None,
    session_id: str = "",
    platform: str = "",
    user_message: str = "",
    conversation_history: list[dict[str, Any]] | None = None,
    recent_window_minutes: int = 30,
    max_events: int = 8,
    include_other_platforms: bool = True,
) -> str:
    """Build the full ephemeral runtime context layer for one model turn."""
    current = _coerce_now(now)
    path = Path(db_path) if db_path else _default_db_path()
    current_ts = current.timestamp()
    last_user_ts = get_last_user_message_time(db_path=path, session_id=session_id)
    elapsed_seconds = current_ts - last_user_ts if last_user_ts else None
    since_ts = current_ts - max(0, int(recent_window_minutes)) * 60
    recent_events = get_recent_events(
        db_path=path,
        since_ts=since_ts,
        limit=max_events,
        exclude_session_id=None,
    )
    reply_mode = _reply_mode_for_gap(elapsed_seconds)

    blocks = [
        build_timeline_sync_block(
            db_path=path,
            now=current,
            session_id=session_id,
            platform=platform,
            recent_window_minutes=recent_window_minutes,
            max_events=max_events,
            include_other_platforms=include_other_platforms,
        ),
        build_rhythm_context_block(
            now=current,
            last_user_ts=last_user_ts,
            platform=platform,
            recent_events=recent_events,
        ),
        build_expression_context_block(elapsed_seconds=elapsed_seconds),
        build_first_line_context_block(reply_mode=reply_mode, elapsed_seconds=elapsed_seconds),
        build_reply_hygiene_block(platform=platform),
        build_tone_precision_block(reply_mode=reply_mode),
        build_return_tone_block(reply_mode=reply_mode),
        build_presence_guard_block(elapsed_seconds=elapsed_seconds),
        build_scratchpad_leak_guard_block(),
        build_platform_digest_block(platform=platform, conversation_history=conversation_history, user_message=user_message),
        build_memory_guard_block(user_message=user_message),
    ]
    return "\n\n".join(block for block in blocks if block)

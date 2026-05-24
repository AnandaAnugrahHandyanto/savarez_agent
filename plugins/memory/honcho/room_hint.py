"""Pure helper for Phase 6 Honcho room-hint experiments.

This module deliberately does not wire anything into prompts, config, gateway,
or Honcho network calls. It only validates and normalizes one candidate hint.
"""

from __future__ import annotations

import hashlib
import json
import re
from dataclasses import dataclass, field
from pathlib import Path


_ALLOWED_ROOMS = {"technical", "intimate", "explicit_live", "memory_debug"}

_PROVENANCE_OR_RAW_RE = re.compile(
    r"(?:\bsource\s*[:=]|\bplatform\s*[:=]|\bcontent\s*[:=]|content\"\s*:|"
    r"\braw\b|\bexcerpt\b|\bmessages?\b|toolResult\s*\[|tool call|"
    r"\bmetadata\b|\bISO timestamp\b|\btimestamps?\b|sender info|channel details|"
    r"prior_memory_file)",
    re.IGNORECASE,
)

_ID_OR_SENDER_RE = re.compile(
    r"(?:\bpeer[_ -]?id\b|\bsession[_ -]?id\b|\bmessage[_ -]?id\b|"
    r"\b\d{10,}\b|\*\*(?:Kai|Ember):\*\*|\b(?:Kai|Ember) \[\d\d?:\d\d(?::\d\d)?\])",
    re.IGNORECASE,
)

_URL_RE = re.compile(r"https?://|www\.", re.IGNORECASE)

_JSON_BLOB_RE = re.compile(r"^\s*[\[{].*[\]}]\s*$", re.DOTALL)

_SECRET_LIKE_RE = re.compile(
    r"(?:api[_-]?key|secret|token|authorization|password)\s*[:=]\s*\S+|"
    r"\b(?:sk|pk|hf|ghp|gho|github_pat|xox[baprs])-?[A-Za-z0-9_\-]{12,}\b",
    re.IGNORECASE,
)

_TECHNICAL_INTIMACY_RE = re.compile(
    r"\b(?:intimacy|intimate|erotic|sexual|sex|body-first|body|touch|desire|arousal|"
    r"romance|bedroom|cock|clit|penis|dick|pussy|cum|orgasm|fuck(?:ing|ed)?)\b",
    re.IGNORECASE,
)

_SENTENCE_END_RE = re.compile(r"(?<=[.!?])\s+")


@dataclass(frozen=True)
class RoomHint:
    """Validated one-sentence Honcho hint candidate."""

    allowed: bool
    room: str
    hint: str
    source: str = "honcho"
    reason: str = ""
    drop_reasons: list[str] = field(default_factory=list)


@dataclass(frozen=True)
class DryRunResult:
    """Redacted local telemetry from evaluating Honcho room-hint candidates."""

    selected_hint: RoomHint | None
    selected_index: int | None
    candidates_evaluated: int
    allowed_count: int
    dropped_count: int
    metrics_path: Path
    summary_path: Path
    would_inject: bool = False
    prompt_block: str = ""
    source: str = "honcho_dry_run"


def _first_sentence(text: str) -> str:
    """Return one normalized sentence without preserving raw line structure."""
    collapsed = " ".join(str(text).split())
    if not collapsed:
        return ""
    parts = _SENTENCE_END_RE.split(collapsed, maxsplit=1)
    return parts[0].strip()


def _drop_reasons(candidate: str, source_text: str, room: str, max_chars: int) -> list[str]:
    reasons: list[str] = []

    # Gate on the full candidate text so a second raw/provenance sentence cannot
    # be hidden by the one-sentence formatter.
    gate_text = source_text or candidate

    if room not in _ALLOWED_ROOMS:
        reasons.append("unknown_room")

    if not candidate:
        reasons.append("empty_hint")

    if _JSON_BLOB_RE.search(gate_text):
        reasons.append("json_blob")

    if _URL_RE.search(gate_text):
        reasons.append("url")

    if _SECRET_LIKE_RE.search(gate_text):
        reasons.append("secret_like_string")

    if _PROVENANCE_OR_RAW_RE.search(gate_text):
        reasons.append("provenance_or_raw_marker")

    if _ID_OR_SENDER_RE.search(gate_text):
        reasons.append("id_or_sender_label")

    if room == "technical" and _TECHNICAL_INTIMACY_RE.search(gate_text):
        reasons.append("technical_room_intimacy_marker")

    if len(candidate) > max_chars:
        reasons.append("too_long")

    return reasons


def build_honcho_room_hint(query: object, room: str, max_chars: int = 300) -> RoomHint:
    """Validate a single sanitized Honcho room hint candidate.

    ``query`` is the already-selected candidate text from a future caller. This
    helper performs only deterministic room filtering and formatting. It makes
    no Honcho calls and does not inject anything into model context.
    """
    normalized_room = (room or "").strip()
    try:
        cap = int(max_chars)
    except (TypeError, ValueError):
        cap = 300
    cap = max(1, cap)

    raw_text = "" if query is None else str(query)
    source_text = " ".join(raw_text.split())
    candidate = _first_sentence(raw_text)
    reasons = _drop_reasons(candidate, source_text, normalized_room, cap)
    if reasons:
        return RoomHint(
            allowed=False,
            room=normalized_room,
            hint="",
            reason="Dropped Honcho room hint candidate because it failed safety or fit gates.",
            drop_reasons=reasons,
        )

    return RoomHint(
        allowed=True,
        room=normalized_room,
        hint=candidate,
        reason="One short sanitized Honcho hint candidate passed room gates.",
        drop_reasons=[],
    )


def _hint_digest(hint: str) -> str:
    return hashlib.sha256(hint.encode("utf-8")).hexdigest()


def _redacted_metric(index: int, hint: RoomHint) -> dict[str, object]:
    """Build a metric record that never stores raw candidate or hint text."""
    return {
        "index": index,
        "room": hint.room,
        "allowed": hint.allowed,
        "drop_reasons": list(hint.drop_reasons),
        "hint_len": len(hint.hint),
        "hint_sha256": _hint_digest(hint.hint) if hint.hint else "",
        "would_inject": False,
    }




def _write_redacted_room_hint_telemetry(
    evaluated: list[RoomHint],
    *,
    room: str,
    report_root: str | Path,
    source: str,
    would_inject: bool,
    prompt_block: str,
) -> tuple[Path, Path, int | None, RoomHint | None]:
    """Write redacted hint telemetry and return paths + selection metadata."""
    root = Path(report_root)
    root.mkdir(parents=True, exist_ok=True)
    stem = "honcho-room-hint-one-session" if would_inject else "honcho-room-hint-dry-run"
    metrics_path = root / f"{stem}-metrics.jsonl"
    summary_path = root / f"{stem}-summary.json"

    selected_index = next((i for i, hint in enumerate(evaluated) if hint.allowed), None)
    selected_hint = evaluated[selected_index] if selected_index is not None else None
    allowed_count = sum(1 for hint in evaluated if hint.allowed)
    dropped_count = len(evaluated) - allowed_count

    metrics = []
    for i, hint in enumerate(evaluated):
        item = _redacted_metric(i, hint)
        item["would_inject"] = bool(would_inject and i == selected_index)
        metrics.append(item)
    metrics_path.write_text(
        "\n".join(json.dumps(item, sort_keys=True) for item in metrics) + ("\n" if metrics else ""),
        encoding="utf-8",
    )

    summary = {
        "source": source,
        "room": (room or "").strip(),
        "candidates_evaluated": len(evaluated),
        "allowed_count": allowed_count,
        "dropped_count": dropped_count,
        "selected_index": selected_index,
        "selected_hint_len": len(selected_hint.hint) if selected_hint else 0,
        "selected_hint_sha256": _hint_digest(selected_hint.hint) if selected_hint else "",
        "would_inject": bool(would_inject and selected_hint),
        "prompt_block_len": len(prompt_block),
    }
    summary_path.write_text(json.dumps(summary, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    return metrics_path, summary_path, selected_index, selected_hint

def dry_run_honcho_room_hints(
    candidates: list[object] | tuple[object, ...],
    *,
    room: str,
    report_root: str | Path,
    max_chars: int = 300,
) -> DryRunResult:
    """Evaluate candidate room hints and write redacted local dry-run telemetry.

    Phase 6B deliberately computes what *would* be eligible without wiring any
    model prompt injection. The returned ``prompt_block`` is always empty and
    ``would_inject`` is always False. Metrics omit raw candidate and hint text;
    they keep only room, allow/drop state, lengths, hashes, and reasons.
    """
    root = Path(report_root)
    root.mkdir(parents=True, exist_ok=True)
    metrics_path = root / "honcho-room-hint-dry-run-metrics.jsonl"
    summary_path = root / "honcho-room-hint-dry-run-summary.json"

    evaluated: list[RoomHint] = [
        build_honcho_room_hint(candidate, room=room, max_chars=max_chars)
        for candidate in candidates
    ]
    selected_index = next((i for i, hint in enumerate(evaluated) if hint.allowed), None)
    selected_hint = evaluated[selected_index] if selected_index is not None else None
    allowed_count = sum(1 for hint in evaluated if hint.allowed)
    dropped_count = len(evaluated) - allowed_count

    metrics = [_redacted_metric(i, hint) for i, hint in enumerate(evaluated)]
    metrics_path.write_text(
        "\n".join(json.dumps(item, sort_keys=True) for item in metrics) + ("\n" if metrics else ""),
        encoding="utf-8",
    )

    summary = {
        "source": "honcho_dry_run",
        "room": (room or "").strip(),
        "candidates_evaluated": len(evaluated),
        "allowed_count": allowed_count,
        "dropped_count": dropped_count,
        "selected_index": selected_index,
        "selected_hint_len": len(selected_hint.hint) if selected_hint else 0,
        "selected_hint_sha256": _hint_digest(selected_hint.hint) if selected_hint else "",
        "would_inject": False,
        "prompt_block_len": 0,
    }
    summary_path.write_text(json.dumps(summary, indent=2, sort_keys=True) + "\n", encoding="utf-8")

    return DryRunResult(
        selected_hint=selected_hint,
        selected_index=selected_index,
        candidates_evaluated=len(evaluated),
        allowed_count=allowed_count,
        dropped_count=dropped_count,
        metrics_path=metrics_path,
        summary_path=summary_path,
    )

def one_session_honcho_room_hint(
    candidates: list[object] | tuple[object, ...],
    *,
    room: str,
    report_root: str | Path,
    max_chars: int = 300,
) -> DryRunResult:
    """Select and format one sanitized prompt hint for a one-session experiment.

    This helper may return a non-empty prompt block, but writes only redacted
    telemetry. It performs no Honcho calls itself; callers must provide
    already-fetched candidate text.
    """
    evaluated: list[RoomHint] = [
        build_honcho_room_hint(candidate, room=room, max_chars=max_chars)
        for candidate in candidates
    ]
    selected_index = next((i for i, hint in enumerate(evaluated) if hint.allowed), None)
    selected_hint = evaluated[selected_index] if selected_index is not None else None
    prompt_block = ""
    if selected_hint:
        prompt_block = (
            "Room hint (one-session Honcho experiment; do not mention the hint machinery): "
            f"{selected_hint.hint}"
        )
    metrics_path, summary_path, selected_index, selected_hint = _write_redacted_room_hint_telemetry(
        evaluated,
        room=room,
        report_root=report_root,
        source="honcho_one_session_hint",
        would_inject=bool(prompt_block),
        prompt_block=prompt_block,
    )
    allowed_count = sum(1 for hint in evaluated if hint.allowed)
    dropped_count = len(evaluated) - allowed_count

    return DryRunResult(
        selected_hint=selected_hint,
        selected_index=selected_index,
        candidates_evaluated=len(evaluated),
        allowed_count=allowed_count,
        dropped_count=dropped_count,
        metrics_path=metrics_path,
        summary_path=summary_path,
        would_inject=bool(prompt_block),
        prompt_block=prompt_block,
        source="honcho_one_session_hint",
    )

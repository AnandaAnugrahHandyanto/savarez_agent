"""Optional skill-candidate detection for episodic memory.

Stage 1 is deterministic and zero-LLM: mine repeated tool workflows from session JSONL.
Stage 2 drafting is intentionally separate and optional.
"""

from __future__ import annotations

import hashlib
import json
import logging
from collections import Counter
from pathlib import Path
from typing import Any, Dict, Iterable, List

from .config import SESSIONS_DIR

logger = logging.getLogger(__name__)


def _load_turns_from_jsonl(jsonl_path: Path) -> List[dict]:
    turns: List[dict] = []
    if not jsonl_path.exists():
        return turns
    for line in jsonl_path.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line:
            continue
        try:
            turns.append(json.loads(line))
        except json.JSONDecodeError:
            logger.debug("Skipping unreadable JSONL line in %s", jsonl_path)
    return turns


def _iter_tool_names(turns: Iterable[dict]) -> List[str]:
    names: List[str] = []
    for turn in turns:
        tool_name = (turn.get("tool_name") or "").strip().lower()
        if tool_name:
            names.append(tool_name)
        for call in turn.get("tool_calls") or []:
            if not isinstance(call, dict):
                continue
            call_name = (
                call.get("name")
                or (call.get("function") or {}).get("name")
                or ""
            ).strip().lower()
            if call_name:
                names.append(call_name)
    return names


def _build_candidate_from_sessions(session_ids: List[str], tool_names: List[str]) -> dict | None:
    filtered = [name for name in tool_names if name]
    if len(filtered) < 2:
        return None
    sequence = filtered[:4]
    fingerprint = "workflow:" + ">".join(sequence)
    digest = hashlib.sha1(fingerprint.encode("utf-8")).hexdigest()[:12]
    occurrence_count = len(session_ids)
    confidence = min(0.99, 0.45 + 0.1 * occurrence_count)
    return {
        "id": f"cand-{digest}",
        "fingerprint": fingerprint,
        "title": f"Repeated workflow using {' + '.join(sequence)}",
        "pattern_type": "workflow",
        "confidence": round(confidence, 2),
        "occurrence_count": occurrence_count,
        "source_sessions": session_ids,
        "evidence": [
            {"type": "tool_sequence", "value": sequence},
            {"type": "session_count", "value": occurrence_count},
        ],
        "metadata": {"scan_source": "jsonl"},
    }


def detect_skill_candidates_for_session(store, session_id: str, settings: Dict[str, Any]) -> List[dict]:
    """Detect repeated workflows anchored on the current session.

    v0.30 intentionally keeps this deterministic and conservative:
    - source: JSONL session files
    - signal: repeated prefix tool sequences across sessions
    - threshold: min_occurrences from settings
    """
    min_occurrences = max(2, int(settings.get("min_occurrences", 3)))
    current_path = SESSIONS_DIR / f"{session_id}.jsonl"
    current_turns = _load_turns_from_jsonl(current_path)
    current_tools = _iter_tool_names(current_turns)
    if len(current_tools) < 2:
        return []

    current_prefix = tuple(current_tools[:4])
    if len(current_prefix) < 2:
        return []

    matches: List[str] = []
    for jsonl_path in sorted(SESSIONS_DIR.glob("*.jsonl")):
        turns = _load_turns_from_jsonl(jsonl_path)
        tools = _iter_tool_names(turns)
        if tuple(tools[: len(current_prefix)]) == current_prefix:
            matches.append(jsonl_path.stem)

    unique_matches = list(dict.fromkeys(matches))
    if len(unique_matches) < min_occurrences:
        return []

    candidate = _build_candidate_from_sessions(unique_matches, list(current_prefix))
    if not candidate:
        return []

    stored = store.upsert_skill_candidate(candidate)
    return [stored]


def draft_skill_candidate(store, candidate_id: str, settings: Dict[str, Any] | None = None) -> dict:
    """Placeholder explicit drafting hook for later LLM integration.

    v0.30 keeps the call surface stable but does not auto-draft in background.
    """
    candidate = store.get_skill_candidate(candidate_id)
    if not candidate:
        raise ValueError(f"Unknown skill candidate: {candidate_id}")

    draft_markdown = (
        f"# {candidate['title']}\n\n"
        f"- Pattern type: {candidate['pattern_type']}\n"
        f"- Occurrences: {candidate['occurrence_count']}\n"
        f"- Source sessions: {', '.join(candidate['source_sessions_json'])}\n"
    )
    updated = store.update_skill_candidate_status(
        candidate_id,
        "drafted",
        draft_markdown=draft_markdown,
        draft_generated_at=__import__("time").time(),
    )
    return updated or candidate

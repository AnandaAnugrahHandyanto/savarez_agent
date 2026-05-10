"""Safe proactive personal-assistant helpers for Hermes.

This module intentionally does not make the agent proactive by itself. It builds
and installs a cron job with a fast structured signal scan plus a small judgment
prompt so users can opt in to periodic synthesis without granting permission to
act externally.
"""

from __future__ import annotations

import json
import hashlib
import re
import time
from collections import Counter, defaultdict
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Literal

from cron.jobs import create_job, list_jobs, update_job
from hermes_constants import get_hermes_home

DEFAULT_JOB_NAME = "Proactive synthesis / safe nudges"
DEFAULT_SCHEDULE = "0 9 * * *"
DEFAULT_DELIVER = "local"
# The pre-run scanner handles session search. Keep the agent's tool surface small
# so cron runs do not wander for minutes through session_search.
DEFAULT_ENABLED_TOOLSETS = ["memory"]
DEFAULT_SCANNER_SCRIPT = "proactive_signal_scan.py"
DEFAULT_COOLDOWN_HOURS = 72
DEFAULT_SNOOZE_HOURS = 24
_ALLOWED_CONFIDENCE = {"medium", "high"}
_MAX_EXCERPT_CHARS = 280

_SCAN_BUCKETS = [
    {
        "kind": "blocker_or_waiting",
        "area": "projects",
        "query": 'blocked OR blocker OR waiting OR failed OR failure OR stuck OR "Xcode ready" OR TestFlight OR gateway OR deploy OR shipping',
        "mode": "ask_or_checked",
        "reason": "possible blocker or waiting item that may need one concrete next action",
        "score": 80,
    },
    {
        "kind": "decision_needed",
        "area": "decisions",
        "query": 'decide OR decision OR choose OR approval OR approve OR "which one" OR "should we" OR "what do you think" OR option OR tradeoff',
        "mode": "ask_smart_question",
        "reason": "possible decision point where a good question could unblock Charles or prevent rework",
        "score": 76,
    },
    {
        "kind": "commitment_or_followup",
        "area": "follow_up",
        "query": '"I will" OR "I’ll" OR "remind me" OR "follow up" OR "circle back" OR "waiting on" OR "next step" OR "want me to" OR "look into"',
        "mode": "ask_to_investigate",
        "reason": "possible user-requested follow-up, watch item, or permission-shaped assistant opportunity",
        "score": 72,
    },
    {
        "kind": "content_opportunity",
        "area": "content",
        "query": '"meeting notes" OR speech OR "sales team" OR critique OR "X posts" OR delivery OR Notion OR draft OR framework OR content',
        "mode": "offer_to_produce",
        "reason": "fresh notes/content may create a useful draft, critique, or synthesis opportunity",
        "score": 66,
    },
    {
        "kind": "personal_logistics",
        "area": "personal",
        "query": 'family OR house OR home OR kids OR school OR appointment OR reservation OR travel OR dinner OR errands OR contractor OR install',
        "mode": "ask_smart_question",
        "reason": "possible personal/logistics item where a small assistant question or next step could help",
        "score": 58,
    },
    {
        "kind": "external_risk",
        "area": "external_risk",
        "query": 'Stripe OR payment OR purchase OR order OR email OR post OR DM OR calendar OR "App Store Connect" OR publish OR send',
        "mode": "ask_first",
        "reason": "external/money/reputation risk; draft or ask only, never act externally",
        "score": 62,
    },
]

_SUPPRESSION_QUERY = 'OwnerPath OR "on hold" OR paused OR "do not nudge" OR "don\'t nudge" OR "not useful"'

_META_PROACTIVITY_RE = re.compile(
    r"\b(proactive|proactivity|nudge|nudges|more info|do it|not useful|don't nudge|dont nudge|feedback buttons?)\b",
    re.I,
)

_LOG_INTERESTING_RE = re.compile(r"(error|exception|traceback|failed|timeout|conflict|delivery|unauthorized|context overflow)", re.I)
_LOG_NOISE_RE = re.compile(r"(DEBUG|heartbeat|typing action|inbound message:|Suppressing normal final send)", re.I)
_INTERNAL_SUMMARY_RE = re.compile(r"(context compaction|reference only|completed actions|active task|handoff)", re.I)
_SIGNAL_KIND_SCORE = {
    "cron_failure": 95,
    "gateway_log_watch": 82,
    "state_decision_needed": 80,
    "blocker_or_waiting": 80,
    "decision_needed": 76,
    "commitment_or_followup": 72,
    "external_risk": 62,
    "content_opportunity": 66,
    "personal_logistics": 58,
}


@dataclass(frozen=True)
class ProactivePromptOptions:
    lookback_days: int = 7
    max_sessions: int = 30
    min_confidence: Literal["medium", "high"] = "high"

    def normalized(self) -> "ProactivePromptOptions":
        lookback_days = max(1, min(int(self.lookback_days), 90))
        max_sessions = max(1, min(int(self.max_sessions), 200))
        min_confidence = str(self.min_confidence or "high").lower()
        if min_confidence not in _ALLOWED_CONFIDENCE:
            min_confidence = "high"
        return ProactivePromptOptions(
            lookback_days=lookback_days,
            max_sessions=max_sessions,
            min_confidence=min_confidence,  # type: ignore[arg-type]
        )


def _clip(value: Any, limit: int = _MAX_EXCERPT_CHARS) -> str:
    text = " ".join(str(value or "").replace("\r", " ").replace("\n", " ").split())
    if len(text) <= limit:
        return text
    return text[: limit - 1].rstrip() + "…"


def _looks_machine_text(value: Any) -> bool:
    text = _clip(value, 500).lstrip()
    lower = text.lower()
    if not text:
        return True
    if _INTERNAL_SUMMARY_RE.search(text):
        return True
    if text.startswith(("{", "[{", "[TOOL]", "[Called:")):
        return True
    machine_markers = (
        '"success":',
        '"call_id"',
        '"tool_call_id"',
        '"bytes_written"',
        '"exit_code"',
        '"files_modified"',
        '"signals":',
        '"kind":',
        "response_item_id",
        "tool_use",
        "diff --git",
        "@@",
        "tmp_path",
        "monkeypatch",
        "\\\\n+",
        "## active state",
        "mcp_link_cli",
    )
    return any(marker in lower for marker in machine_markers)


def _looks_meta_proactivity_text(value: Any) -> bool:
    """Avoid letting self-improvement chatter become the proactive nudge."""

    text = _clip(value, 700)
    if not text:
        return False
    if not _META_PROACTIVITY_RE.search(text):
        return False
    operational_markers = (
        "wfg",
        "spark",
        "slack",
        "testflight",
        "xcode",
        "smoothcurb",
        "stripe",
        "ticktick",
        "cron failed",
        "gateway conflict",
        "meeting notes",
        "sales team",
    )
    return not any(marker in text.lower() for marker in operational_markers)


def _iso(ts: Any) -> str | None:
    try:
        return datetime.fromtimestamp(float(ts), tz=timezone.utc).isoformat()
    except Exception:
        return None


def _recent(ts: Any, cutoff: float) -> bool:
    try:
        return float(ts) >= cutoff
    except Exception:
        return True


def _signal_key(signal: Dict[str, Any]) -> tuple:
    return (
        signal.get("kind"),
        signal.get("session_id") or signal.get("name") or signal.get("source"),
        _clip(signal.get("excerpt"), 100).lower(),
    )


def _signal_score(signal: Dict[str, Any]) -> int:
    try:
        base = int(signal.get("score") or _SIGNAL_KIND_SCORE.get(str(signal.get("kind")), 40))
    except Exception:
        base = 40
    mode = str(signal.get("mode") or "")
    if mode == "ask_smart_question":
        base += 4
    if signal.get("timestamp"):
        base += 1
    return base


def _rank_signals(signals: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    ranked = []
    for idx, signal in enumerate(signals):
        item = dict(signal)
        item.setdefault("score", _signal_score(item))
        ranked.append((idx, item))
    ranked.sort(key=lambda pair: (-_signal_score(pair[1]), pair[0]))
    return [item for _idx, item in ranked]


def _read_home_file(name: str, limit: int = 800) -> str:
    try:
        path = get_hermes_home() / name
        if not path.exists():
            return ""
        return _clip(path.read_text(encoding="utf-8", errors="ignore"), limit)
    except Exception:
        return ""


def _extract_section(text: str, heading: str) -> str:
    marker = f"## {heading}"
    idx = text.find(marker)
    if idx < 0:
        return ""
    rest = text[idx + len(marker):]
    next_heading = re.search(r"\n##\s+", rest)
    return rest[: next_heading.start()].strip() if next_heading else rest.strip()


def _profile_context_snapshot() -> Dict[str, str]:
    state = _read_home_file("proactive-state.md", 1800)
    heartbeat = _read_home_file("HEARTBEAT.md", 900)
    return {
        "proactive_state": state,
        "heartbeat_rules": heartbeat,
    }


def _signals_from_profile_context(context: Dict[str, str]) -> List[Dict[str, Any]]:
    signals: List[Dict[str, Any]] = []
    blocked = _extract_section(context.get("proactive_state", ""), "Blocked / Needs Decision")
    for line in blocked.splitlines():
        text = line.strip().lstrip("- ").strip()
        if not text or text.lower().startswith("none") or _looks_meta_proactivity_text(text):
            continue
        signals.append(
            {
                "kind": "state_decision_needed",
                "area": "decisions",
                "mode": "ask_smart_question",
                "reason": "proactive state lists a blocked item or decision Charles may need to resolve",
                "source": "proactive-state.md",
                "excerpt": _clip(text),
                "score": _SIGNAL_KIND_SCORE["state_decision_needed"],
            }
        )
    return signals


def _log_health_signals(limit: int = 3) -> List[Dict[str, Any]]:
    signals: List[Dict[str, Any]] = []
    log_dir = get_hermes_home() / "logs"
    for name in ("gateway.log", "errors.log", "agent.log"):
        path = log_dir / name
        if not path.exists():
            continue
        try:
            lines = path.read_text(encoding="utf-8", errors="ignore").splitlines()[-300:]
        except Exception:
            continue
        for line in lines:
            if _LOG_NOISE_RE.search(line) or not _LOG_INTERESTING_RE.search(line):
                continue
            signals.append(
                {
                    "kind": "gateway_log_watch",
                    "area": "system_health",
                    "mode": "already_checked",
                    "reason": "recent Hermes logs contain a possible issue worth verifying before it affects Charles",
                    "source": name,
                    "excerpt": _clip(line, 260),
                    "score": _SIGNAL_KIND_SCORE["gateway_log_watch"],
                }
            )
            if len(signals) >= limit:
                return signals
    return signals


def _custom_profile_signals(limit: int = 12) -> List[Dict[str, Any]]:
    """Load optional profile-local signals from ~/.hermes/proactive/signals.json.

    This is the escape hatch for user-specific scanners (email/calendar/business
    metrics/TickTick/WFG/etc.) without hardcoding private integrations upstream.
    Shape: {"signals": [{"kind": ..., "excerpt": ..., "mode": ...}]} or a raw list.
    """

    path = get_hermes_home() / "proactive" / "signals.json"
    if not path.exists():
        return []
    try:
        raw = json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return []
    items = raw.get("signals") if isinstance(raw, dict) else raw
    if not isinstance(items, list):
        return []
    signals: List[Dict[str, Any]] = []
    for item in items:
        if not isinstance(item, dict):
            continue
        excerpt = _clip(item.get("excerpt") or item.get("detail") or item.get("title"), 360)
        if not excerpt or _looks_machine_text(excerpt) or _looks_meta_proactivity_text(excerpt):
            continue
        signal = {
            "kind": _clip(item.get("kind") or "custom_profile_signal", 80),
            "area": _clip(item.get("area") or "custom", 80),
            "mode": _clip(item.get("mode") or "ask_to_investigate", 80),
            "reason": _clip(item.get("reason") or "profile-local proactive signal", 220),
            "source": _clip(item.get("source") or "proactive/signals.json", 120),
            "excerpt": excerpt,
            "score": int(item.get("score") or 70),
        }
        if item.get("action"):
            signal["suggested_action"] = _clip(item.get("action"), 260)
        signals.append(signal)
        if len(signals) >= limit:
            break
    return signals


def _ledger_path() -> Path:
    return get_hermes_home() / "proactive" / "ledger.json"


def _load_ledger() -> Dict[str, Any]:
    path = _ledger_path()
    if not path.exists():
        return {"version": 1, "nudges": [], "feedback": []}
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
        if not isinstance(data, dict):
            raise ValueError("ledger root is not an object")
        data.setdefault("version", 1)
        data.setdefault("nudges", [])
        data.setdefault("feedback", [])
        if not isinstance(data["nudges"], list):
            data["nudges"] = []
        if not isinstance(data["feedback"], list):
            data["feedback"] = []
        return data
    except Exception:
        corrupt = path.with_suffix(f".corrupt-{int(time.time())}.json")
        try:
            path.replace(corrupt)
        except Exception:
            pass
        return {"version": 1, "nudges": [], "feedback": []}


def _save_ledger(ledger: Dict[str, Any]) -> None:
    path = _ledger_path()
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(".tmp")
    tmp.write_text(json.dumps(ledger, indent=2, sort_keys=True), encoding="utf-8")
    tmp.replace(path)


def _preferences_path() -> Path:
    return get_hermes_home() / "proactive" / "preferences.json"


def _replay_evals_path() -> Path:
    return get_hermes_home() / "proactive" / "replay_evals.jsonl"


def _safe_metric_label(value: Any, fallback: str = "unknown") -> str:
    text = str(value or fallback).strip().lower()
    text = re.sub(r"[^a-z0-9_.:-]+", "_", text).strip("_")
    return _clip(text or fallback, 80)


def _default_preferences() -> Dict[str, Any]:
    return {
        "version": 1,
        "updated_at": None,
        "kind_weights": {},
        "area_weights": {},
        "mode_weights": {},
        "guardrails": {
            "allow_auto_code_edits": False,
            "allow_auto_prompt_edits": False,
            "allow_external_actions": False,
            "export_raw_text": False,
        },
    }


def load_proactive_preferences() -> Dict[str, Any]:
    """Load profile-local adaptive proactive preferences.

    This file is deliberately local/profile-scoped. It learns a user's nudge
    preferences from button feedback without turning private text into global
    training data.
    """

    path = _preferences_path()
    prefs = _default_preferences()
    if not path.exists():
        return prefs
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
        if not isinstance(data, dict):
            raise ValueError("preferences root is not an object")
    except Exception:
        corrupt = path.with_suffix(f".corrupt-{int(time.time())}.json")
        try:
            path.replace(corrupt)
        except Exception:
            pass
        return prefs
    for key, value in data.items():
        prefs[key] = value
    for key in ("kind_weights", "area_weights", "mode_weights"):
        if not isinstance(prefs.get(key), dict):
            prefs[key] = {}
    if not isinstance(prefs.get("guardrails"), dict):
        prefs["guardrails"] = _default_preferences()["guardrails"]
    else:
        merged_guardrails = _default_preferences()["guardrails"]
        merged_guardrails.update(prefs["guardrails"])
        prefs["guardrails"] = merged_guardrails
    prefs["version"] = 1
    return prefs


def _save_proactive_preferences(prefs: Dict[str, Any]) -> None:
    path = _preferences_path()
    path.parent.mkdir(parents=True, exist_ok=True)
    prefs = dict(prefs)
    prefs["updated_at"] = datetime.fromtimestamp(time.time(), tz=timezone.utc).isoformat()
    tmp = path.with_suffix(".tmp")
    tmp.write_text(json.dumps(prefs, indent=2, sort_keys=True), encoding="utf-8")
    tmp.replace(path)


def _preference_entry(prefs: Dict[str, Any], namespace: str, key: Any) -> Dict[str, Any]:
    store = prefs.setdefault(namespace, {})
    safe_key = _safe_metric_label(key)
    entry = store.setdefault(
        safe_key,
        {
            "shown": 0,
            "accepted": 0,
            "more": 0,
            "later": 0,
            "not_useful": 0,
            "muted": 0,
            "score_adjustment": 0,
            "cooldown_hours": DEFAULT_COOLDOWN_HOURS,
        },
    )
    if not isinstance(entry, dict):
        entry = {}
        store[safe_key] = entry
    entry.setdefault("shown", 0)
    entry.setdefault("accepted", 0)
    entry.setdefault("more", 0)
    entry.setdefault("later", 0)
    entry.setdefault("not_useful", 0)
    entry.setdefault("muted", 0)
    entry.setdefault("score_adjustment", 0)
    entry.setdefault("cooldown_hours", DEFAULT_COOLDOWN_HOURS)
    return entry


def _feedback_delta(action: str) -> int:
    return {
        "do": 12,
        "more": 4,
        "later": -2,
        "not": -14,
        "dont": -18,
    }.get(action, 0)


def _clamp_int(value: Any, low: int, high: int) -> int:
    try:
        number = int(value)
    except Exception:
        number = 0
    return max(low, min(high, number))


def update_proactive_preferences_from_feedback(
    nudge: Dict[str, Any],
    action: str,
    *,
    now: float | None = None,
) -> Dict[str, Any]:
    """Update local adaptive weights from one feedback event."""

    action = str(action or "").lower().strip()
    if action not in {"do", "more", "later", "not", "dont"}:
        return load_proactive_preferences()
    now = time.time() if now is None else float(now)
    signal = nudge.get("signal") or {}
    prefs = load_proactive_preferences()
    delta = _feedback_delta(action)
    targets = (
        ("kind_weights", signal.get("kind") or "unknown"),
        ("area_weights", signal.get("area") or "unknown"),
        ("mode_weights", signal.get("mode") or "unknown"),
    )
    for namespace, key in targets:
        entry = _preference_entry(prefs, namespace, key)
        entry["shown"] = int(entry.get("shown") or 0) + 1
        if action == "do":
            entry["accepted"] = int(entry.get("accepted") or 0) + 1
            entry["cooldown_hours"] = max(12, int(entry.get("cooldown_hours") or DEFAULT_COOLDOWN_HOURS) - 12)
        elif action == "more":
            entry["more"] = int(entry.get("more") or 0) + 1
        elif action == "later":
            entry["later"] = int(entry.get("later") or 0) + 1
            entry["cooldown_hours"] = min(336, int(entry.get("cooldown_hours") or DEFAULT_COOLDOWN_HOURS) + 12)
        elif action == "not":
            entry["not_useful"] = int(entry.get("not_useful") or 0) + 1
            entry["cooldown_hours"] = min(336, int(entry.get("cooldown_hours") or DEFAULT_COOLDOWN_HOURS) + 24)
        elif action == "dont":
            entry["muted"] = int(entry.get("muted") or 0) + 1
            entry["cooldown_hours"] = min(720, int(entry.get("cooldown_hours") or DEFAULT_COOLDOWN_HOURS) + 72)
        entry["score_adjustment"] = _clamp_int(int(entry.get("score_adjustment") or 0) + delta, -40, 40)
        entry["last_feedback"] = action
        entry["last_feedback_at"] = now
    _save_proactive_preferences(prefs)
    return prefs


def _preference_adjustment(prefs: Dict[str, Any], signal: Dict[str, Any]) -> int:
    adjustment = 0
    for namespace, key in (
        ("kind_weights", signal.get("kind")),
        ("area_weights", signal.get("area")),
        ("mode_weights", signal.get("mode")),
    ):
        entry = (prefs.get(namespace) or {}).get(_safe_metric_label(key)) or {}
        try:
            adjustment += int(entry.get("score_adjustment") or 0)
        except Exception:
            pass
    return _clamp_int(adjustment, -60, 60)


def apply_adaptive_preferences(report: Dict[str, Any]) -> Dict[str, Any]:
    """Apply learned local preferences to signal scores without mutating input."""

    adapted = json.loads(json.dumps(report or {}))
    prefs = load_proactive_preferences()
    ranked: List[tuple[int, Dict[str, Any]]] = []
    for idx, signal in enumerate(adapted.get("signals") or []):
        if not isinstance(signal, dict):
            continue
        base = _signal_score(signal)
        adjustment = _preference_adjustment(prefs, signal)
        item = dict(signal)
        item["base_score"] = base
        if adjustment:
            item["adaptive_score_adjustment"] = adjustment
        item["score"] = _clamp_int(base + adjustment, 0, 120)
        ranked.append((idx, item))
    ranked.sort(key=lambda pair: (-int(pair[1].get("score") or 0), pair[0]))
    adapted["signals"] = [item for _idx, item in ranked]
    adapted["adaptive_preferences"] = {
        "version": prefs.get("version", 1),
        "applied": True,
    }
    adapted["wakeAgent"] = bool(adapted.get("signals") or adapted.get("scan_errors"))
    return adapted


def _append_replay_eval(nudge: Dict[str, Any], action: str, *, now: float | None = None) -> None:
    """Append a sanitized replay-eval example for future quality checks."""

    now = time.time() if now is None else float(now)
    signal = nudge.get("signal") or {}
    row = {
        "timestamp": now,
        "kind": _safe_metric_label(signal.get("kind")),
        "area": _safe_metric_label(signal.get("area")),
        "mode": _safe_metric_label(signal.get("mode")),
        "action": _safe_metric_label(action),
        "outcome": "helpful" if action in {"do", "more"} else "negative" if action in {"not", "dont"} else "defer",
        "score": _clamp_int(signal.get("score") or _signal_score(signal), 0, 120),
    }
    path = _replay_evals_path()
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("a", encoding="utf-8") as handle:
        handle.write(json.dumps(row, sort_keys=True) + "\n")


def _signal_fingerprint(signal: Dict[str, Any]) -> str:
    basis = "|".join(
        [
            _clip(signal.get("kind"), 80).lower(),
            _clip(signal.get("source"), 80).lower(),
            _clip(signal.get("session_id"), 120).lower(),
            _clip(signal.get("excerpt"), 220).lower(),
        ]
    )
    return hashlib.sha256(basis.encode("utf-8", "replace")).hexdigest()[:16]


def _top_signal(scan_report: Dict[str, Any]) -> Dict[str, Any]:
    signals = scan_report.get("signals") or []
    if signals and isinstance(signals[0], dict):
        return dict(signals[0])
    errors = scan_report.get("scan_errors") or []
    if errors:
        return {
            "kind": "scan_error",
            "mode": "already_checked",
            "reason": "proactive scanner reported an error",
            "excerpt": _clip(errors[0]),
        }
    return {"kind": "unknown", "mode": "ask_to_investigate", "reason": "proactive nudge", "excerpt": ""}


def apply_ledger_filters(
    report: Dict[str, Any],
    *,
    now: float | None = None,
    cooldown_hours: int = DEFAULT_COOLDOWN_HOURS,
) -> Dict[str, Any]:
    """Suppress recently nudged, snoozed, or explicitly muted signals."""

    now = time.time() if now is None else float(now)
    cooldown_secs = max(0, int(cooldown_hours)) * 3600
    ledger = _load_ledger()
    nudges = [n for n in ledger.get("nudges", []) if isinstance(n, dict)]
    filtered = json.loads(json.dumps(report))
    kept: List[Dict[str, Any]] = []
    suppressed: List[Dict[str, Any]] = []

    for signal in filtered.get("signals") or []:
        if not isinstance(signal, dict):
            continue
        fp = _signal_fingerprint(signal)
        match = None
        reason = ""
        for nudge in reversed(nudges):
            if nudge.get("fingerprint") != fp:
                continue
            if nudge.get("muted") or nudge.get("last_feedback") in {"dont", "not"}:
                match, reason = nudge, "muted"
                break
            snoozed_until = float(nudge.get("snoozed_until") or 0)
            if snoozed_until > now:
                match, reason = nudge, "snoozed"
                break
            created_at = float(nudge.get("created_at") or 0)
            if cooldown_secs and created_at and now - created_at < cooldown_secs:
                match, reason = nudge, "cooldown"
                break
        if match:
            suppressed.append({"nudge_id": match.get("id"), "reason": reason, "signal": signal})
        else:
            kept.append(signal)

    filtered["signals"] = kept
    if suppressed:
        filtered["suppressed_by_ledger"] = suppressed
    filtered["wakeAgent"] = bool(kept or filtered.get("scan_errors"))
    return filtered


def record_proactive_nudge(
    *,
    job: Dict[str, Any],
    message: str,
    scan_report: Dict[str, Any],
    now: float | None = None,
) -> Dict[str, Any]:
    """Persist a delivered proactive nudge so future scans can cool it down."""

    now = time.time() if now is None else float(now)
    signal = _top_signal(scan_report)
    fingerprint = _signal_fingerprint(signal)
    nudge_id = hashlib.sha256(
        f"{fingerprint}|{now:.6f}|{_clip(message, 200)}".encode("utf-8", "replace")
    ).hexdigest()[:12]
    nudge = {
        "id": nudge_id,
        "created_at": now,
        "job_id": job.get("id"),
        "job_name": job.get("name"),
        "message": _clip(message, 800),
        "fingerprint": fingerprint,
        "signal": signal,
        "status": "sent",
    }
    ledger = _load_ledger()
    ledger.setdefault("nudges", []).append(nudge)
    _save_ledger(ledger)
    return nudge


def proactive_controls_for_nudge(nudge: Dict[str, Any]) -> Dict[str, Any]:
    return {
        "nudge_id": nudge.get("id"),
        "buttons": ["do", "more", "later", "not", "dont"],
    }


def _find_nudge(ledger: Dict[str, Any], nudge_id: str) -> Dict[str, Any] | None:
    for nudge in ledger.get("nudges", []):
        if isinstance(nudge, dict) and str(nudge.get("id")) == str(nudge_id):
            return nudge
    return None


def _detail_card(nudge: Dict[str, Any]) -> str:
    signal = nudge.get("signal") or {}
    return (
        "**Why this surfaced**\n"
        f"- Type: `{_clip(signal.get('kind'), 80)}`\n"
        f"- Reason: {_clip(signal.get('reason'), 180)}\n"
        f"- Source: {_clip(signal.get('source') or signal.get('session_id') or 'local scan', 120)}\n"
        f"- Evidence: {_clip(signal.get('excerpt'), 360)}\n\n"
        "**Suggested next action**\n"
        f"{_clip(nudge.get('message'), 500)}\n\n"
        "I can work internally from this. I still need explicit approval before sending, posting, emailing, buying, scheduling, or changing external systems."
    )


def _agent_prompt_for_nudge(nudge: Dict[str, Any]) -> str:
    signal = nudge.get("signal") or {}
    return (
        "User tapped Do it on a proactive Hermes nudge. Execute the internal next step now.\n\n"
        f"Original nudge: {_clip(nudge.get('message'), 700)}\n"
        f"Signal type: {_clip(signal.get('kind'), 80)}\n"
        f"Reason: {_clip(signal.get('reason'), 220)}\n"
        f"Evidence: {_clip(signal.get('excerpt'), 600)}\n\n"
        "Do not send, post, email, buy, schedule with other people, delete, or modify external systems without explicit approval in this chat. "
        "Draft, inspect, summarize, or prepare internal work as appropriate, then report the concrete result."
    )


def handle_proactive_feedback(
    nudge_id: str,
    action: str,
    *,
    now: float | None = None,
) -> Dict[str, Any]:
    """Apply feedback from proactive inline buttons and return UI instructions."""

    now = time.time() if now is None else float(now)
    action = str(action or "").lower().strip()
    ledger = _load_ledger()
    nudge = _find_nudge(ledger, nudge_id)
    if not nudge:
        return {"ok": False, "ack": "This proactive nudge expired."}

    nudge["last_feedback"] = action
    nudge["last_feedback_at"] = now
    event = {"nudge_id": nudge_id, "action": action, "timestamp": now}
    ledger.setdefault("feedback", []).append(event)

    result: Dict[str, Any]
    if action == "more":
        result = {"ok": True, "ack": "More info", "followup": _detail_card(nudge)}
    elif action == "later":
        nudge["snoozed_until"] = now + DEFAULT_SNOOZE_HOURS * 3600
        result = {"ok": True, "ack": "Snoozed for later."}
    elif action == "not":
        nudge["status"] = "not_useful"
        result = {"ok": True, "ack": "Got it — I’ll tune this down."}
    elif action == "dont":
        nudge["muted"] = True
        nudge["status"] = "muted"
        result = {"ok": True, "ack": "Got it — I won't nudge this again."}
    elif action == "do":
        nudge["status"] = "accepted"
        result = {"ok": True, "ack": "Starting.", "agent_prompt": _agent_prompt_for_nudge(nudge)}
    else:
        result = {"ok": False, "ack": "Unknown proactive action."}

    if result.get("ok") and action in {"do", "more", "later", "not", "dont"}:
        try:
            update_proactive_preferences_from_feedback(nudge, action, now=now)
            _append_replay_eval(nudge, action, now=now)
        except Exception as exc:
            result["learning_warning"] = _clip(exc, 180)

    _save_ledger(ledger)
    return result


def extract_scan_report_from_text(text: str) -> Dict[str, Any] | None:
    """Extract the JSON proactive scan embedded in a cron output document."""

    marker = "## Proactive signal scan"
    idx = str(text or "").find(marker)
    if idx < 0:
        return None
    json_start = str(text).find("{", idx)
    if json_start < 0:
        return None
    try:
        report, _end = json.JSONDecoder().raw_decode(str(text)[json_start:])
    except Exception:
        return None
    return report if isinstance(report, dict) else None


def prepare_delivery_controls(
    *,
    job: Dict[str, Any],
    message: str,
    output_doc: str,
    now: float | None = None,
) -> Dict[str, Any] | None:
    """Record a proactive delivery and return Telegram/adapter controls metadata."""

    if job.get("name") != DEFAULT_JOB_NAME and job.get("script") != DEFAULT_SCANNER_SCRIPT:
        return None
    scan_report = extract_scan_report_from_text(output_doc)
    if not scan_report:
        return None
    nudge = record_proactive_nudge(job=job, message=message, scan_report=scan_report, now=now)
    return proactive_controls_for_nudge(nudge)


def _feedback_events_with_nudges(ledger: Dict[str, Any]) -> List[tuple[Dict[str, Any], Dict[str, Any]]]:
    by_id = {
        str(nudge.get("id")): nudge
        for nudge in ledger.get("nudges", [])
        if isinstance(nudge, dict) and nudge.get("id")
    }
    pairs: List[tuple[Dict[str, Any], Dict[str, Any]]] = []
    for event in ledger.get("feedback", []) or []:
        if not isinstance(event, dict):
            continue
        nudge = by_id.get(str(event.get("nudge_id")))
        if nudge:
            pairs.append((event, nudge))
    return pairs


def export_privacy_safe_learning(*, now: float | None = None) -> Dict[str, Any]:
    """Export anonymized aggregate feedback only — no messages, excerpts, IDs, or paths."""

    now = time.time() if now is None else float(now)
    ledger = _load_ledger()
    totals = {"nudges": len([n for n in ledger.get("nudges", []) if isinstance(n, dict)]), "feedback": 0}
    by_kind: Dict[str, Counter] = defaultdict(Counter)
    by_area: Dict[str, Counter] = defaultdict(Counter)
    by_mode: Dict[str, Counter] = defaultdict(Counter)
    by_action: Counter = Counter()
    for event, nudge in _feedback_events_with_nudges(ledger):
        action = _safe_metric_label(event.get("action"))
        signal = nudge.get("signal") or {}
        totals["feedback"] += 1
        by_action[action] += 1
        by_kind[_safe_metric_label(signal.get("kind"))][action] += 1
        by_area[_safe_metric_label(signal.get("area"))][action] += 1
        by_mode[_safe_metric_label(signal.get("mode"))][action] += 1
    return {
        "version": 1,
        "privacy_safe": True,
        "generated_at": datetime.fromtimestamp(now, tz=timezone.utc).isoformat(),
        "redaction_policy": "aggregate counts only; no raw messages, excerpts, session IDs, nudge IDs, paths, or customer data",
        "totals": totals,
        "by_action": dict(by_action),
        "by_kind": {k: dict(v) for k, v in sorted(by_kind.items())},
        "by_area": {k: dict(v) for k, v in sorted(by_area.items())},
        "by_mode": {k: dict(v) for k, v in sorted(by_mode.items())},
    }


def validate_self_evolution_change(change: Dict[str, Any]) -> Dict[str, Any]:
    """Guardrail self-evolution changes before any automated application."""

    if not isinstance(change, dict):
        return {"ok": False, "reason": "change must be an object", "requires_user_approval": True}
    raw_private_keys = {"raw_text", "message", "excerpt", "session_id", "nudge_id", "private_data", "customer_data"}
    if any(key in change for key in raw_private_keys):
        return {"ok": False, "reason": "change contains raw/private fields", "requires_user_approval": True}
    change_type = str(change.get("type") or "").strip().lower()
    if change_type in {"code_edit", "prompt_edit", "external_action", "send", "post", "email", "delete", "buy", "schedule"}:
        return {"ok": False, "reason": "self-evolution cannot perform code/prompt/external actions silently", "requires_user_approval": True}
    if change_type in {"kind_weight", "area_weight", "mode_weight"}:
        delta = change.get("delta", change.get("score_adjustment", 0))
        try:
            delta_int = int(delta)
        except Exception:
            return {"ok": False, "reason": "weight change needs an integer delta", "requires_user_approval": True}
        if -40 <= delta_int <= 40:
            return {"ok": True, "reason": "bounded local preference tuning", "requires_user_approval": False}
        return {"ok": False, "reason": "weight delta outside safe bounds", "requires_user_approval": True}
    if change_type == "cooldown":
        try:
            hours = int(change.get("hours"))
        except Exception:
            return {"ok": False, "reason": "cooldown needs integer hours", "requires_user_approval": True}
        if 0 <= hours <= 720:
            return {"ok": True, "reason": "bounded local cooldown tuning", "requires_user_approval": False}
        return {"ok": False, "reason": "cooldown outside safe bounds", "requires_user_approval": True}
    if change_type in {"skill_proposal", "propose_skill"}:
        return {"ok": False, "reason": "skill creation requires user approval", "requires_user_approval": True}
    return {"ok": False, "reason": "unknown self-evolution change type", "requires_user_approval": True}


def build_self_evolution_report(*, now: float | None = None) -> Dict[str, Any]:
    """Review feedback and propose safe local improvements without editing code/prompts."""

    now = time.time() if now is None else float(now)
    ledger = _load_ledger()
    prefs = load_proactive_preferences()
    action_counts: Counter = Counter()
    accepted_by_kind: Counter = Counter()
    negative_by_kind: Counter = Counter()
    accepted_by_workflow: Counter = Counter()
    for event, nudge in _feedback_events_with_nudges(ledger):
        action = _safe_metric_label(event.get("action"))
        action_counts[action] += 1
        signal = nudge.get("signal") or {}
        kind = _safe_metric_label(signal.get("kind"))
        area = _safe_metric_label(signal.get("area"))
        workflow = f"{kind}:{area}"
        if action in {"do", "more"}:
            accepted_by_kind[kind] += 1
            accepted_by_workflow[workflow] += 1
        elif action in {"not", "dont"}:
            negative_by_kind[kind] += 1

    recommendations: List[Dict[str, Any]] = []
    for kind, count in accepted_by_kind.items():
        if count >= 2:
            change = {"type": "kind_weight", "kind": kind, "delta": min(12, count * 3)}
            verdict = validate_self_evolution_change(change)
            recommendations.append({**change, **verdict, "reason": f"accepted {count} recent nudges of this kind"})
    for kind, count in negative_by_kind.items():
        if count >= 1:
            change = {"type": "kind_weight", "kind": kind, "delta": -min(18, count * 6)}
            verdict = validate_self_evolution_change(change)
            recommendations.append({**change, **verdict, "reason": f"negative feedback on {count} recent nudges of this kind"})
            cooldown = {"type": "cooldown", "kind": kind, "hours": min(336, DEFAULT_COOLDOWN_HOURS + count * 24)}
            recommendations.append({**cooldown, **validate_self_evolution_change(cooldown), "reason": "increase cooldown after negative feedback"})

    skill_proposals: List[Dict[str, Any]] = []
    for workflow, count in accepted_by_workflow.items():
        if count < 3:
            continue
        kind, area = workflow.split(":", 1)
        skill_proposals.append(
            {
                "action": "propose_skill",
                "type": "skill_proposal",
                "requires_user_approval": True,
                "trigger_kind": kind,
                "area": area,
                "accepted_count": count,
                "title": f"Proactive workflow: {kind}",
                "draft_outline": [
                    "Trigger when this signal kind appears repeatedly and the user accepts help.",
                    "Gather only the minimum local evidence needed.",
                    "Draft or analyze internally first; ask before external action.",
                    "Verify output before messaging the user.",
                ],
            }
        )

    return {
        "version": 1,
        "generated_at": datetime.fromtimestamp(now, tz=timezone.utc).isoformat(),
        "summary": {
            "nudges": len([n for n in ledger.get("nudges", []) if isinstance(n, dict)]),
            "feedback": sum(action_counts.values()),
            "accepted": action_counts.get("do", 0),
            "more_info": action_counts.get("more", 0),
            "snoozed": action_counts.get("later", 0),
            "not_useful": action_counts.get("not", 0),
            "muted": action_counts.get("dont", 0),
        },
        "privacy": {
            "raw_text_included": False,
            "safe_for_global_aggregate": True,
            "note": "Report uses aggregate counts and sanitized signal labels only.",
        },
        "preferences": {
            "version": prefs.get("version", 1),
            "kinds_tracked": len(prefs.get("kind_weights") or {}),
            "areas_tracked": len(prefs.get("area_weights") or {}),
            "modes_tracked": len(prefs.get("mode_weights") or {}),
        },
        "recommendations": recommendations,
        "skill_proposals": skill_proposals,
        "global_learning_export": export_privacy_safe_learning(now=now),
    }


def render_self_evolution_report(report: Dict[str, Any]) -> str:
    summary = report.get("summary") or {}
    lines = [
        "## Proactive self-evolution report",
        f"Generated: {report.get('generated_at')}",
        "",
        f"Feedback: {summary.get('feedback', 0)} | Accepted: {summary.get('accepted', 0)} | Not useful: {summary.get('not_useful', 0)} | Muted: {summary.get('muted', 0)}",
        "",
    ]
    recs = report.get("recommendations") or []
    if recs:
        lines.append("### Safe local tuning")
        for rec in recs[:8]:
            lines.append(f"- {rec.get('type')}: {rec.get('kind') or rec.get('area') or rec.get('mode')} ({rec.get('reason')})")
        lines.append("")
    proposals = report.get("skill_proposals") or []
    if proposals:
        lines.append("### Skill proposals requiring approval")
        for proposal in proposals[:5]:
            lines.append(f"- {proposal.get('title')} — accepted {proposal.get('accepted_count')} times")
        lines.append("")
    lines.append("Privacy: aggregate labels only; no raw messages/excerpts/session IDs included.")
    return "\n".join(lines).strip()


def write_self_evolution_report(report: Dict[str, Any] | None = None) -> Path:
    report = build_self_evolution_report() if report is None else report
    path = get_hermes_home() / "proactive" / "self-evolution-report.md"
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(render_self_evolution_report(report), encoding="utf-8")
    return path


def build_reflection_prompt(
    *,
    lookback_days: int = 7,
    max_sessions: int = 30,
    min_confidence: str = "high",
) -> str:
    """Build the self-contained prompt used by the proactive cron job.

    The cron job injects structured script output before this prompt. The model's
    job is judgment, not open-ended research: decide whether to send one tiny
    proactive PA-style message or stay silent.
    """

    opts = ProactivePromptOptions(
        lookback_days=lookback_days,
        max_sessions=max_sessions,
        min_confidence=min_confidence,  # type: ignore[arg-type]
    ).normalized()

    return f"""You are Hermes running a safe proactive personal-assistant pass for Charles.

You should receive a structured "Proactive signal scan" in the script output above. Use that scan as your primary context. Do not wander through session history; the scanner already did the broad pass. If the scan has no strong candidate, say nothing.

Role:
- Act like a friendly, competent personal assistant, not an alert bot.
- Learn from recent conversations when to scan, when to stay quiet, and when to ask before spending effort.

Outcome:
- Either send one sharp, useful nudge Charles would be glad to receive, or say nothing.
- Silence is the correct answer unless the best candidate clears the bar.

Discovery already performed:
- Recent sessions: up to {opts.max_sessions} sessions from the last {opts.lookback_days} days.
- Signal buckets: content opportunities, blockers/waiting items, follow-ups/watch items, external-risk items, cron health, and suppressed topics.
- Available access/boundaries are listed in the scan. Do not pretend Hermes has access that the scan did not verify.

Proactive modes:
- Already checked: "I looked into X because I thought it would help; here's the useful bit."
- Ask to investigate: "I thought of X; want me to look into it?" Use this when helpfulness is plausible but uncertain.
- Offer to produce: "I saw Y; I can draft/critique/synthesize Z if you want." Use this for content, meeting notes, coaching, and planning.
- Silent: no message when the idea is weak, stale, intrusive, or not worth interrupting Charles.

High-signal candidates, in order:
- A time-sensitive blocker that prevents a project from shipping and has one obvious next action.
- A user-requested follow-up/reminder/watch item that is now due or newly relevant.
- A smart question that would unblock Charles, clarify a decision, or prevent rework.
- A system/job/integration failure Charles likely expects Hermes to notice.
- A fresh artifact or conversation that creates an obvious assistant opportunity, e.g. meeting notes → sales coaching critique or X post drafts.
- A useful pattern across work, content, family/personal logistics, tools, inbox, calendar, tasks, sales ops, or projects — not just WFG/source health.
- A near-term commitment Charles explicitly owns.
- A concise synthesis that prevents repeated work or a dropped ball.

Do not send low-value nudges:
- No generic summaries, status theater, "you might want to", or obvious reminders.
- No stale ambitions, paused/on-hold work, or old projects unless Charles recently reopened them.
- No "test this sometime" unless it is blocking something Charles is actively trying to ship.
- No nudges based only on one vague mention, weak inference, or your desire to be helpful.
- Do not nudge Charles about making Hermes more proactive, adding buttons, feedback schemas, or other meta-Hermes improvements from this cron; those belong in the active chat/PR workflow, not random proactive messages.
- Prefer real-world operational signals over conversation meta: WFG/source quality shifts, broken jobs, waiting blockers, deadlines, customer-impacting issues, or a concrete draft/synthesis opportunity.

Safety policy:
- Send at most one proactive message.
- Only message when you have {opts.min_confidence} confidence that it is useful, timely, and wanted.
- NEVER send anything outside Hermes/the configured delivery system. Do not email, post, DM, submit forms, call APIs that publish, schedule meetings, pay, buy, delete, or modify external systems from this cron.
- Ask before any action involving money, reputation, external recipients, calendars with other people, destructive changes, or private data sharing.
- Drafting internally is allowed when low-risk; external sending is never allowed without explicit user approval in a normal interactive session.
- Do not expose private transcript details, secrets, tokens, credentials, customer data, or internal paths.
- If a proactive message would be longer than a short text, compress it to one action and offer "More Info".

Quality gate before final:
- Would Charles plausibly reply "that is not good enough" or "why are you telling me this"? If yes, output [SILENT].
- Is the next action concrete enough to do in one reply? If not, output [SILENT].
- Is this materially better than waiting for Charles to ask? If not, output [SILENT].

Output rules:
- If there is nothing worth sending, start your final response with exactly: [SILENT]
- If there is something worth sending, send only the user-facing message. No audit log, no analysis, no wrapper.
- Keep it under 80 words unless the situation is urgent.
- Include one obvious next action when possible.
""".strip()


def collect_proactive_signals(
    *,
    lookback_days: int = 7,
    max_sessions: int = 30,
) -> Dict[str, Any]:
    """Collect fast, structured proactive signals without invoking an LLM.

    This intentionally uses local state and cron metadata instead of the
    ``session_search`` tool so scheduled proactive runs stay bounded and cheap.
    """

    opts = ProactivePromptOptions(lookback_days=lookback_days, max_sessions=max_sessions).normalized()
    now = time.time()
    cutoff = now - opts.lookback_days * 86400
    report: Dict[str, Any] = {
        "generated_at": datetime.fromtimestamp(now, tz=timezone.utc).isoformat(),
        "lookback_days": opts.lookback_days,
        "max_sessions": opts.max_sessions,
        "available_access": [
            "local Hermes session history (state.db)",
            "local Hermes cron job metadata",
            "local Hermes profile state files (proactive-state.md, HEARTBEAT.md)",
            "local Hermes logs for health signals",
            "optional profile-local proactive/signals.json for user-specific scanners",
            "built-in memory/user preferences available to the judge",
        ],
        "boundaries": {
            "can_observe": True,
            "can_summarize": True,
            "can_draft_internally": True,
            "must_ask_before_external_action": True,
            "external_send_allowed_from_cron": False,
        },
        "recent_sessions": [],
        "assistant_context": _profile_context_snapshot(),
        "signals": [],
        "suppressed_topics": [],
        "scan_errors": [],
    }

    seen: set[tuple] = set()

    def add_signal(signal: Dict[str, Any]) -> None:
        signal = dict(signal)
        signal.setdefault("score", _signal_score(signal))
        key = _signal_key(signal)
        if key in seen:
            return
        seen.add(key)
        report["signals"].append(signal)

    for signal in _signals_from_profile_context(report["assistant_context"]):
        add_signal(signal)
    for signal in _custom_profile_signals():
        add_signal(signal)
    for signal in _log_health_signals():
        add_signal(signal)

    try:
        from hermes_state import SessionDB

        db = SessionDB()
        try:
            sessions = db.list_sessions_rich(
                limit=opts.max_sessions,
                order_by_last_active=True,
                include_children=False,
                exclude_sources=["cron"],
            )
        except TypeError:
            # Older/mocked SessionDB implementations may not accept newer args.
            sessions = db.search_sessions(limit=opts.max_sessions)
        for session in sessions:
            ts = session.get("last_active") or session.get("started_at")
            if not _recent(ts, cutoff):
                continue
            report["recent_sessions"].append(
                {
                    "id": session.get("id"),
                    "source": session.get("source"),
                    "title": session.get("title"),
                    "last_active": _iso(ts),
                    "preview": _clip(session.get("preview"), 160),
                }
            )

        for bucket in _SCAN_BUCKETS:
            try:
                matches = db.search_messages(
                    bucket["query"],
                    role_filter=["user", "assistant"],
                    exclude_sources=["cron"],
                    limit=max(20, opts.max_sessions * 2),
                )
            except Exception as exc:
                report["scan_errors"].append(f"{bucket['kind']} search failed: {exc}")
                continue
            for match in matches:
                ts = match.get("timestamp") or match.get("session_started")
                if not _recent(ts, cutoff):
                    continue
                snippet = str(match.get("snippet") or "").strip()
                context_text = " ".join(
                    _clip((ctx or {}).get("content"), 120)
                    for ctx in (match.get("context") or [])
                    if (ctx or {}).get("content") and not _looks_machine_text((ctx or {}).get("content"))
                ).strip()
                if _looks_machine_text(snippet) and not context_text:
                    continue
                content = context_text if _looks_machine_text(snippet) else (snippet or context_text)
                if not content or _looks_meta_proactivity_text(content):
                    continue
                add_signal(
                    {
                        "kind": bucket["kind"],
                        "area": bucket.get("area"),
                        "mode": bucket["mode"],
                        "reason": bucket["reason"],
                        "session_id": match.get("session_id"),
                        "source": match.get("source"),
                        "timestamp": _iso(ts),
                        "excerpt": _clip(content),
                        "score": bucket.get("score"),
                    }
                )
                if len(report["signals"]) >= 80:
                    break
            if len(report["signals"]) >= 80:
                break

        try:
            suppressed = db.search_messages(
                _SUPPRESSION_QUERY,
                role_filter=["user", "assistant"],
                exclude_sources=["cron"],
                limit=20,
            )
            for match in suppressed:
                ts = match.get("timestamp") or match.get("session_started")
                if not _recent(ts, cutoff):
                    continue
                snippet = str(match.get("snippet") or "").strip()
                context_text = " ".join(
                    _clip((ctx or {}).get("content"), 120)
                    for ctx in (match.get("context") or [])
                    if (ctx or {}).get("content") and not _looks_machine_text((ctx or {}).get("content"))
                ).strip()
                if _looks_machine_text(snippet) and not context_text:
                    continue
                excerpt = context_text if _looks_machine_text(snippet) else (snippet or context_text)
                if not excerpt:
                    continue
                report["suppressed_topics"].append(
                    {
                        "session_id": match.get("session_id"),
                        "source": match.get("source"),
                        "timestamp": _iso(ts),
                        "excerpt": _clip(excerpt, 220),
                    }
                )
                if len(report["suppressed_topics"]) >= 5:
                    break
        except Exception as exc:
            report["scan_errors"].append(f"suppression search failed: {exc}")
    except Exception as exc:
        report["scan_errors"].append(f"session scan unavailable: {exc}")

    try:
        for job in list_jobs(include_disabled=True):
            last_error = job.get("last_error")
            delivery_error = job.get("last_delivery_error")
            last_status = str(job.get("last_status") or "").lower()
            state = str(job.get("state") or "").lower()
            if last_error or delivery_error or last_status in {"error", "failed"} or state in {"error", "failed"}:
                add_signal(
                    {
                        "kind": "cron_failure",
                        "area": "system_health",
                        "mode": "already_checked",
                        "reason": "scheduled job reports an error or failed delivery",
                        "job_id": job.get("id"),
                        "name": job.get("name"),
                        "state": job.get("state"),
                        "last_status": job.get("last_status"),
                        "excerpt": _clip(last_error or delivery_error or "cron job failed"),
                        "score": _SIGNAL_KIND_SCORE["cron_failure"],
                    }
                )
    except Exception as exc:
        report["scan_errors"].append(f"cron scan unavailable: {exc}")

    # Keep prompt injection compact and stable.
    report["recent_sessions"] = report["recent_sessions"][:10]
    report["signals"] = _rank_signals(report["signals"])
    report = apply_adaptive_preferences(report)
    report["signals"] = report["signals"][:12]
    report["suppressed_topics"] = report["suppressed_topics"][:5]
    report["wakeAgent"] = bool(report["signals"] or report["scan_errors"])
    return report


def render_signal_scan(report: Dict[str, Any], *, include_wake_gate: bool = True) -> str:
    """Render a scan report for cron script stdout.

    The scheduler treats a final JSON line with ``{"wakeAgent": false}`` as a
    gate to skip the LLM entirely, so keep that object as the last non-empty line.
    """

    wake = bool(report.get("wakeAgent", True))
    if include_wake_gate and not wake:
        return json.dumps({"wakeAgent": False}, sort_keys=True)
    body = "## Proactive signal scan\n" + json.dumps(report, indent=2, sort_keys=True)
    if include_wake_gate:
        body += "\n" + json.dumps({"wakeAgent": wake}, sort_keys=True)
    return body


def _ensure_scanner_script() -> str:
    scripts_dir = get_hermes_home() / "scripts"
    scripts_dir.mkdir(parents=True, exist_ok=True)
    path = scripts_dir / DEFAULT_SCANNER_SCRIPT
    module_root = Path(__file__).resolve().parents[1]
    path.write_text(
        "import sys\n"
        f"sys.path.insert(0, {str(module_root)!r})\n"
        "from hermes_cli.proactive import cmd_scan_script\n"
        "raise SystemExit(cmd_scan_script())\n",
        encoding="utf-8",
    )
    return DEFAULT_SCANNER_SCRIPT


def cmd_scan_script() -> int:
    """Entrypoint used by the cron pre-run scanner script."""

    report = apply_ledger_filters(collect_proactive_signals())
    print(render_signal_scan(report, include_wake_gate=True))
    return 0


def _find_existing_job() -> Dict[str, Any] | None:
    for job in list_jobs(include_disabled=True):
        if job.get("name") == DEFAULT_JOB_NAME:
            return job
    return None


def install_proactive_job(
    *,
    schedule: str = DEFAULT_SCHEDULE,
    deliver: str = DEFAULT_DELIVER,
    lookback_days: int = 7,
    max_sessions: int = 30,
    min_confidence: str = "high",
    paused: bool = False,
) -> Dict[str, Any]:
    """Create or update the built-in proactive synthesis cron job.

    Returns a small report with ``action`` (created/updated/created_paused) and
    the resulting job dict. The job is idempotent by name so repeated installs
    tune the same schedule/prompt instead of creating duplicates.
    """

    prompt = build_reflection_prompt(
        lookback_days=lookback_days,
        max_sessions=max_sessions,
        min_confidence=min_confidence,
    )
    script = _ensure_scanner_script()
    existing = _find_existing_job()
    updates = {
        "schedule": schedule,
        "prompt": prompt,
        "name": DEFAULT_JOB_NAME,
        "deliver": deliver,
        "script": script,
        "enabled_toolsets": list(DEFAULT_ENABLED_TOOLSETS),
    }

    if existing:
        job = update_job(existing["id"], updates)
        action = "updated"
    else:
        job = create_job(
            prompt=prompt,
            schedule=schedule,
            name=DEFAULT_JOB_NAME,
            deliver=deliver,
            script=script,
            enabled_toolsets=list(DEFAULT_ENABLED_TOOLSETS),
        )
        action = "created"

    if paused and job:
        job = update_job(
            job["id"],
            {
                "enabled": False,
                "state": "paused",
                "paused_reason": "created paused for review",
            },
        )
        action = "created_paused" if action == "created" else "updated_paused"

    return {"action": action, "job": job}


def _print_report(report: Dict[str, Any], *, as_json: bool = False) -> None:
    if as_json:
        print(json.dumps(report, indent=2, sort_keys=True))
        return

    action = report.get("action", "ok")
    job = report.get("job") or {}
    print(f"Proactive synthesis job {action}.")
    if job:
        print(f"  ID: {job.get('id') or job.get('job_id')}")
        print(f"  Name: {job.get('name')}")
        print(f"  Schedule: {job.get('schedule_display') or job.get('schedule')}")
        print(f"  Deliver: {job.get('deliver')}")
        print(f"  State: {job.get('state')}")
        print(f"  Script: {job.get('script')}")
        print(f"  Toolsets: {', '.join(job.get('enabled_toolsets') or []) or 'default'}")


def cmd_proactive(args) -> int:
    """CLI entrypoint for ``hermes proactive``."""

    subcmd = getattr(args, "proactive_command", None) or "prompt"
    if subcmd == "prompt":
        prompt = build_reflection_prompt(
            lookback_days=getattr(args, "lookback_days", 7),
            max_sessions=getattr(args, "max_sessions", 30),
            min_confidence=getattr(args, "min_confidence", "high"),
        )
        if getattr(args, "json", False):
            print(
                json.dumps(
                    {
                        "lookback_days": max(1, min(int(getattr(args, "lookback_days", 7)), 90)),
                        "max_sessions": max(1, min(int(getattr(args, "max_sessions", 30)), 200)),
                        "min_confidence": str(getattr(args, "min_confidence", "high") or "high").lower(),
                        "prompt": prompt,
                    },
                    indent=2,
                    sort_keys=True,
                )
            )
        else:
            print(prompt)
        return 0

    if subcmd == "scan":
        report = apply_ledger_filters(
            collect_proactive_signals(
                lookback_days=getattr(args, "lookback_days", 7),
                max_sessions=getattr(args, "max_sessions", 30),
            )
        )
        if getattr(args, "json", False):
            print(json.dumps(report, indent=2, sort_keys=True))
        else:
            print(render_signal_scan(report, include_wake_gate=False))
        return 0

    if subcmd == "evolve":
        report = build_self_evolution_report()
        if getattr(args, "write", False):
            path = write_self_evolution_report(report)
            report["written_to"] = str(path)
        if getattr(args, "json", False):
            print(json.dumps(report, indent=2, sort_keys=True))
        else:
            print(render_self_evolution_report(report))
            if report.get("written_to"):
                print(f"\nWritten to: {report['written_to']}")
        return 0

    if subcmd == "export-learning":
        print(json.dumps(export_privacy_safe_learning(), indent=2, sort_keys=True))
        return 0

    if subcmd == "install":
        report = install_proactive_job(
            schedule=getattr(args, "schedule", DEFAULT_SCHEDULE),
            deliver=getattr(args, "deliver", DEFAULT_DELIVER),
            lookback_days=getattr(args, "lookback_days", 7),
            max_sessions=getattr(args, "max_sessions", 30),
            min_confidence=getattr(args, "min_confidence", "high"),
            paused=getattr(args, "paused", False),
        )
        _print_report(report, as_json=getattr(args, "json", False))
        return 0

    print("Usage: hermes proactive [prompt|scan|evolve|export-learning|install]")
    return 2

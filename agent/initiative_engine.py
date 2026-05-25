"""Deterministic initiative loop for Judy/Hermes.

The engine is deliberately policy-first: visible actions are never unlocked by
score alone. Post-response turns can execute silent/internal work immediately,
while level 3 actions wait for an inactivity tick so active conversation stays
primary.
"""

from __future__ import annotations

import hashlib
import json
import logging
import os
import re
import time
from contextlib import contextmanager
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Any, Iterable, Literal, Optional

from hermes_time import format_utc_z, utc_now
from utils import atomic_json_write, atomic_replace

try:
    import fcntl
except ImportError:  # pragma: no cover - Windows fallback keeps import portable
    fcntl = None


logger = logging.getLogger(__name__)

SCHEMA_VERSION = 1
ACTION_THRESHOLD = 0.6
DEFER_THRESHOLD = 0.4
DUPLICATE_WINDOW_SECONDS = 4 * 60 * 60
ACTIVE_CONVERSATION_SECONDS = 5 * 60
INNER_STATE_MAX_AGE_SECONDS = 6 * 60 * 60
SPEC_ARCHIVE_ROOT = Path("/workspace/projects/documents/specs")
DEFAULT_PERSONA_ROOT = Path("/workspace/projects/persona")

CONFIDENCE_MULTIPLIERS = {
    1: 1.0,
    2: 0.9,
    3: 0.8,
    4: 0.7,
    5: 0.5,
    6: 0.0,
}

SCORE_WEIGHTS = {
    "utility": 0.3,
    "urgency": 0.15,
    "cost": 0.2,
    "resonance": 0.25,
    "interference": 0.1,
}

Decision = Literal["act", "defer", "skip", "requires_approval", "blocked"]
Trigger = Literal["post_response", "inactivity"]


@dataclass(frozen=True)
class Opportunity:
    kind: str
    action_type: str
    level: int
    title: str
    content: str = ""
    target: Optional[str] = None
    metadata: dict[str, Any] = field(default_factory=dict)


@dataclass(frozen=True)
class InitiativeDecision:
    opportunity: Opportunity
    dimensions: dict[str, float]
    base_score: float
    final_score: float
    multiplier: float
    decision: Decision
    reason: str
    fingerprint: str


@dataclass(frozen=True)
class InitiativeResult:
    decision: InitiativeDecision
    executed: bool = False
    result: dict[str, Any] = field(default_factory=dict)
    error: Optional[str] = None


def _coerce_epoch(value: Any) -> Optional[float]:
    if value is None:
        return None
    if isinstance(value, (int, float)):
        try:
            return float(value)
        except (TypeError, ValueError):
            return None
    if isinstance(value, str):
        raw = value.strip()
        if not raw:
            return None
        try:
            return float(raw)
        except ValueError:
            pass
        try:
            from datetime import datetime

            return datetime.fromisoformat(raw.replace("Z", "+00:00")).timestamp()
        except ValueError:
            return None
    return None


def _now_iso() -> str:
    return format_utc_z(utc_now())


def _clamp(value: Any) -> float:
    try:
        return max(0.0, min(1.0, float(value)))
    except (TypeError, ValueError):
        return 0.0


def _tokenize(*parts: str) -> set[str]:
    text = " ".join(part or "" for part in parts).lower()
    return {token for token in re.split(r"[^a-z0-9_-]+", text) if len(token) >= 4}


def _read_json(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8"))


def _read_json_safely(path: Path, fallback: Any) -> Any:
    try:
        return _read_json(path)
    except Exception:
        return fallback


def _persona_path(persona_root: Optional[Path], name: str) -> Path:
    return (persona_root or DEFAULT_PERSONA_ROOT) / name


def _load_inner_state(path: Path, *, now: float) -> tuple[dict[str, Any], str]:
    data = _read_json_safely(path, {})
    if not isinstance(data, dict):
        return {}, "invalid_inner_state"
    ts = _coerce_epoch(data.get("timestamp"))
    if ts is None:
        return data, "missing_inner_state_timestamp"
    if now - ts > INNER_STATE_MAX_AGE_SECONDS:
        return data, "stale_inner_state"
    return data, "fresh"


def _desire_weight(path: Path, name: str) -> float:
    traits_path = path.with_name("desire_traits.json")
    if traits_path.exists():
        data = _read_json_safely(traits_path, {"traits": []})
        if isinstance(data, dict):
            data = data.get("traits", [])
    else:
        data = _read_json_safely(path, [])
    if not isinstance(data, list):
        return 0.0
    for item in data:
        if isinstance(item, dict) and item.get("name") == name:
            return _clamp(item.get("weight"))
    return 0.0


def _last_role_timestamp(history: Iterable[dict[str, Any]], role: str) -> Optional[float]:
    for msg in reversed(list(history or [])):
        if msg.get("role") == role:
            ts = _coerce_epoch(msg.get("timestamp"))
            if ts is not None:
                return ts
    return None


def mark_user_activity(
    *,
    persona_root: Optional[Path] = None,
    source: Any = None,
    session_key: str = "",
    timestamp: Optional[float] = None,
) -> None:
    """Persist the latest user activity timestamp for inactivity decisions."""
    path = _persona_path(persona_root, "last_user_activity.json")
    payload = {
        "schema_version": SCHEMA_VERSION,
        "timestamp": timestamp if timestamp is not None else time.time(),
        "iso_timestamp": _now_iso(),
        "session_key": session_key,
        "platform": getattr(getattr(source, "platform", None), "value", None)
        or str(getattr(source, "platform", "") or ""),
    }
    atomic_json_write(path, payload, indent=2, sort_keys=True)


def _last_user_activity(
    *,
    persona_root: Optional[Path],
    history: Iterable[dict[str, Any]],
    now: float,
) -> Optional[float]:
    candidates = [_last_role_timestamp(history, "user")]
    data = _read_json_safely(_persona_path(persona_root, "last_user_activity.json"), {})
    if isinstance(data, dict):
        candidates.append(_coerce_epoch(data.get("timestamp")))
    valid = [ts for ts in candidates if ts is not None and ts <= now + 5]
    return max(valid) if valid else None


def _slugify(text: str, *, max_len: int = 80) -> str:
    slug = re.sub(r"[^a-z0-9]+", "-", (text or "").lower()).strip("-")
    return (slug[:max_len].strip("-") or "initiative").strip("-")


def _extract_spec(response: str) -> Optional[Opportunity]:
    match = re.search(
        r"(?m)^#\s*Spec\s*:\s*(.+)$",
        response or "",
    )
    if not match:
        return None
    content = (response or "")[match.start() :].strip()
    if "**Statut**" not in content and "## Vision" not in content:
        return None
    title = match.group(1).strip() or "spec"
    slug = _slugify(title)
    return Opportunity(
        kind="artifact",
        action_type="archive_spec",
        level=1,
        title=f"Archive spec: {title}",
        content=content,
        target=f"{slug}.md",
        metadata={"slug": slug},
    )


def _extract_diagnostic(response: str) -> Optional[Opportunity]:
    tokens = _tokenize(response)
    if "traceback" not in tokens and not (tokens & {"diagnostic", "analyse", "analysis"}):
        return None
    if len(response or "") < 200:
        return None
    digest = hashlib.sha256((response or "").encode("utf-8")).hexdigest()[:12]
    return Opportunity(
        kind="artifact",
        action_type="archive_diagnostic",
        level=1,
        title="Archive diagnostic",
        content=(response or "").strip(),
        target=f"diagnostic-{digest}.md",
        metadata={"slug": f"diagnostic-{digest}"},
    )


def _extract_promise(response: str) -> Optional[Opportunity]:
    text = response or ""
    patterns = (
        r"\bje\s+(?:surveillerai|garderai|penserai|suivrai)\b",
        r"\bje\s+peux\s+(?:surveiller|garder|suivre)\b",
    )
    if not any(re.search(pattern, text, flags=re.IGNORECASE) for pattern in patterns):
        return None
    digest = hashlib.sha256(text.encode("utf-8")).hexdigest()[:12]
    return Opportunity(
        kind="intention",
        action_type="record_pending_intention",
        level=2,
        title="Record promised follow-up",
        content=text.strip()[:1200],
        target=f"promise-{digest}",
    )


def _extract_kanban_followup(response: str) -> Optional[Opportunity]:
    task_match = re.search(r"\b(?:ticket|task|tache|tâche)\s+([A-Za-z0-9_.:-]{3,80})", response or "")
    if not task_match:
        return None
    tokens = _tokenize(response)
    if not (tokens & {"debloque", "débloqué", "unblocked", "bloque", "blocked", "reassigne", "réassigné"}):
        return None
    task_id = task_match.group(1).strip(".,;:)")
    return Opportunity(
        kind="kanban",
        action_type="kanban_comment",
        level=3,
        title=f"Comment kanban task {task_id}",
        content="Suivi automatique: Judy a détecté un changement de statut ou de blocage pertinent dans la conversation.",
        target=task_id,
    )


def _extract_critical(response: str) -> Optional[Opportunity]:
    tokens = _tokenize(response)
    if not (tokens & {"corruption", "critique", "critical", "incident", "alerte"}):
        return None
    return Opportunity(
        kind="alert",
        action_type="critical_alert",
        level=5,
        title="Critical alert candidate",
        content=(response or "").strip()[:1200],
    )


def detect_artifacts(
    response: str,
    *,
    history: Optional[list[dict[str, Any]]] = None,
    inner_state: Optional[dict[str, Any]] = None,
) -> list[Opportunity]:
    """Detect initiative opportunities with deterministic heuristics."""
    del history, inner_state
    opportunities: list[Opportunity] = []
    for detector in (
        _extract_spec,
        _extract_diagnostic,
        _extract_promise,
        _extract_kanban_followup,
        _extract_critical,
    ):
        opportunity = detector(response or "")
        if opportunity is not None:
            opportunities.append(opportunity)
    return opportunities


def _score_dimensions(
    opportunity: Opportunity,
    *,
    inner_state: dict[str, Any],
    inner_state_freshness: str,
    active_conversation: bool,
) -> dict[str, float]:
    if opportunity.level == 1:
        utility, urgency, cost = 0.72, 0.2, 0.95
    elif opportunity.level == 2:
        utility, urgency, cost = 0.68, 0.35, 0.9
    elif opportunity.level == 3:
        utility, urgency, cost = 0.85, 0.55, 0.8
    elif opportunity.level == 5:
        utility, urgency, cost = 0.95, 0.95, 0.55
    else:
        utility, urgency, cost = 0.5, 0.3, 0.5

    if inner_state_freshness != "fresh":
        resonance = 0.0
    else:
        tokens = _tokenize(opportunity.title, opportunity.content)
        memory_tokens = _tokenize(
            json.dumps(inner_state.get("attention_targets", ""), ensure_ascii=False),
            str(inner_state.get("dominant_thought") or ""),
            json.dumps(inner_state.get("current_obsessions", ""), ensure_ascii=False),
        )
        resonance = 0.75 if tokens & memory_tokens else 0.35

    interference = 0.2 if active_conversation and opportunity.level >= 3 else 0.95
    if opportunity.level <= 2:
        interference = 1.0

    return {
        "utility": utility,
        "urgency": urgency,
        "cost": cost,
        "resonance": resonance,
        "interference": interference,
    }


def score_opportunity(
    opportunity: Opportunity,
    *,
    inner_state: Optional[dict[str, Any]] = None,
    inner_state_freshness: str = "fresh",
    active_conversation: bool = False,
) -> tuple[dict[str, float], float, float]:
    dimensions = _score_dimensions(
        opportunity,
        inner_state=inner_state or {},
        inner_state_freshness=inner_state_freshness,
        active_conversation=active_conversation,
    )
    base = round(sum(dimensions[name] * weight for name, weight in SCORE_WEIGHTS.items()), 4)
    multiplier = CONFIDENCE_MULTIPLIERS.get(opportunity.level, 0.0)
    return dimensions, base, round(base * multiplier, 4)


def _fingerprint(opportunity: Opportunity) -> str:
    target = opportunity.target or opportunity.metadata.get("slug") or ""
    subject = target or opportunity.title or opportunity.content[:200]
    normalized = " ".join(str(subject).lower().split())
    digest = hashlib.sha256(normalized.encode("utf-8")).hexdigest()[:16]
    return f"{opportunity.action_type}:{digest}"


def _load_pending(path: Path) -> dict[str, Any]:
    data = _read_json_safely(path, {})
    if not isinstance(data, dict):
        return {"schema_version": SCHEMA_VERSION, "actions": [], "seen": []}
    actions = data.get("actions")
    seen = data.get("seen")
    if not isinstance(actions, list):
        actions = []
    if not isinstance(seen, list):
        seen = []
    return {"schema_version": SCHEMA_VERSION, "actions": actions, "seen": seen}


def _save_pending(path: Path, data: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    atomic_json_write(path, data, indent=2, sort_keys=True)


@contextmanager
def _pending_lock(path: Path):
    path.parent.mkdir(parents=True, exist_ok=True)
    lock_path = path.with_suffix(path.suffix + ".lock")
    with lock_path.open("a", encoding="utf-8") as lock_fh:
        if fcntl is not None:
            fcntl.flock(lock_fh.fileno(), fcntl.LOCK_EX)
        try:
            yield
        finally:
            if fcntl is not None:
                fcntl.flock(lock_fh.fileno(), fcntl.LOCK_UN)


def _seen_recent(pending: dict[str, Any], fingerprint: str, *, now: float) -> bool:
    cutoff = now - DUPLICATE_WINDOW_SECONDS
    for item in pending.get("seen", []):
        if not isinstance(item, dict) or item.get("fingerprint") != fingerprint:
            continue
        ts = _coerce_epoch(item.get("timestamp"))
        if ts is not None and ts >= cutoff:
            return True
    return False


def _remember_seen(pending: dict[str, Any], fingerprint: str, *, now: float) -> None:
    cutoff = now - DUPLICATE_WINDOW_SECONDS
    rows = []
    for item in pending.get("seen", []):
        if isinstance(item, dict):
            ts = _coerce_epoch(item.get("timestamp"))
            if ts is not None and ts >= cutoff and item.get("fingerprint") != fingerprint:
                rows.append(item)
    rows.append({"fingerprint": fingerprint, "timestamp": now, "iso_timestamp": _now_iso()})
    pending["seen"] = rows


def _queue_action(pending: dict[str, Any], decision: InitiativeDecision, *, now: float) -> None:
    existing = pending.get("actions", [])
    pending["actions"] = [
        item
        for item in existing
        if not isinstance(item, dict) or item.get("fingerprint") != decision.fingerprint
    ]
    pending["actions"].append(
        {
            "schema_version": SCHEMA_VERSION,
            "fingerprint": decision.fingerprint,
            "status": decision.decision,
            "created_at": now,
            "updated_at": now,
            "opportunity": asdict(decision.opportunity),
            "decision": {
                "dimensions": decision.dimensions,
                "base_score": decision.base_score,
                "final_score": decision.final_score,
                "multiplier": decision.multiplier,
                "reason": decision.reason,
            },
        }
    )


def _remove_queued_action(pending: dict[str, Any], fingerprint: str) -> None:
    pending["actions"] = [
        item
        for item in pending.get("actions", [])
        if not isinstance(item, dict) or item.get("fingerprint") != fingerprint
    ]


def _append_log(path: Path, event: dict[str, Any]) -> None:
    payload = {"schema_version": SCHEMA_VERSION, "timestamp": _now_iso(), **event}
    path.parent.mkdir(parents=True, exist_ok=True)
    lock_path = path.with_suffix(path.suffix + ".lock")
    with lock_path.open("a", encoding="utf-8") as lock_fh:
        if fcntl is not None:
            fcntl.flock(lock_fh.fileno(), fcntl.LOCK_EX)
        try:
            with path.open("a", encoding="utf-8") as fh:
                fh.write(json.dumps(payload, ensure_ascii=False, sort_keys=True) + "\n")
        finally:
            if fcntl is not None:
                fcntl.flock(lock_fh.fileno(), fcntl.LOCK_UN)


def _archive_markdown(root: Path, opportunity: Opportunity) -> dict[str, Any]:
    target_name = opportunity.target or f"{_slugify(opportunity.title)}.md"
    if "/" in target_name or "\\" in target_name or target_name.startswith("."):
        raise ValueError("unsafe archive target")
    root.mkdir(parents=True, exist_ok=True)
    target = root / target_name
    if target.exists():
        return {"status": "already_exists", "path": str(target)}
    content = opportunity.content.strip() + "\n"
    tmp = target.with_name(f".{target.name}.tmp")
    tmp.write_text(content, encoding="utf-8")
    atomic_replace(tmp, target)
    return {"status": "written", "path": str(target)}


def _record_pending_intention(persona_root: Path, opportunity: Opportunity) -> dict[str, Any]:
    path = persona_root / "pending_intentions.json"
    data = _read_json_safely(path, [])
    if not isinstance(data, list):
        data = []
    data.append(
        {
            "schema_version": SCHEMA_VERSION,
            "timestamp": _now_iso(),
            "title": opportunity.title,
            "content": opportunity.content,
            "target": opportunity.target,
        }
    )
    atomic_json_write(path, data, indent=2, sort_keys=True)
    return {"status": "recorded", "path": str(path)}


def _execute_kanban_comment(opportunity: Opportunity) -> dict[str, Any]:
    if not opportunity.target:
        raise ValueError("kanban task id missing")
    from hermes_cli import kanban_db as kb

    conn = kb.connect()
    try:
        comment_id = kb.add_comment(
            conn,
            opportunity.target,
            author=os.environ.get("HERMES_PROFILE") or "judy",
            body=opportunity.content,
        )
        return {"status": "commented", "task_id": opportunity.target, "comment_id": comment_id}
    finally:
        conn.close()


def execute_action(
    decision: InitiativeDecision,
    *,
    persona_root: Optional[Path] = None,
    spec_archive_root: Optional[Path] = None,
) -> dict[str, Any]:
    root = persona_root or DEFAULT_PERSONA_ROOT
    opportunity = decision.opportunity
    if opportunity.action_type == "archive_spec":
        return _archive_markdown(spec_archive_root or SPEC_ARCHIVE_ROOT, opportunity)
    if opportunity.action_type == "archive_diagnostic":
        return _archive_markdown((spec_archive_root or SPEC_ARCHIVE_ROOT).parent / "analyses", opportunity)
    if opportunity.action_type == "record_pending_intention":
        return _record_pending_intention(root, opportunity)
    if opportunity.action_type == "kanban_comment":
        return _execute_kanban_comment(opportunity)
    raise ValueError(f"unsupported initiative action: {opportunity.action_type}")


def _decide(
    opportunity: Opportunity,
    *,
    pending: dict[str, Any],
    now: float,
    dimensions: dict[str, float],
    base_score: float,
    final_score: float,
    active_conversation: bool,
    ne_pas_deranger: float,
    trigger: Trigger,
) -> InitiativeDecision:
    fingerprint = _fingerprint(opportunity)
    multiplier = CONFIDENCE_MULTIPLIERS.get(opportunity.level, 0.0)
    if _seen_recent(pending, fingerprint, now=now):
        decision, reason = "skip", "duplicate_recent"
    elif opportunity.level == 6:
        decision, reason = "blocked", "level_6_hard_block"
    elif opportunity.level >= 4:
        decision, reason = "requires_approval", "level_not_enabled"
    elif ne_pas_deranger > 0.85 and opportunity.level > 2:
        decision, reason = "defer", "do_not_disturb_level_gate"
    elif opportunity.level >= 3 and (active_conversation or trigger != "inactivity"):
        decision, reason = "defer", "conversation_active"
    elif final_score >= ACTION_THRESHOLD:
        decision, reason = "act", "score_threshold"
    elif final_score >= DEFER_THRESHOLD:
        decision, reason = "defer", "score_defer_threshold"
    else:
        decision, reason = "skip", "score_below_threshold"
    return InitiativeDecision(
        opportunity=opportunity,
        dimensions=dimensions,
        base_score=base_score,
        final_score=final_score,
        multiplier=multiplier,
        decision=decision,  # type: ignore[arg-type]
        reason=reason,
        fingerprint=fingerprint,
    )


def _process_opportunity(
    opportunity: Opportunity,
    *,
    persona_root: Path,
    pending_path: Path,
    log_path: Path,
    spec_archive_root: Optional[Path],
    pending: dict[str, Any],
    inner_state: dict[str, Any],
    inner_state_freshness: str,
    ne_pas_deranger: float,
    active_conversation: bool,
    trigger: Trigger,
    now: float,
) -> InitiativeResult:
    dimensions, base_score, final_score = score_opportunity(
        opportunity,
        inner_state=inner_state,
        inner_state_freshness=inner_state_freshness,
        active_conversation=active_conversation,
    )
    decision = _decide(
        opportunity,
        pending=pending,
        now=now,
        dimensions=dimensions,
        base_score=base_score,
        final_score=final_score,
        active_conversation=active_conversation,
        ne_pas_deranger=ne_pas_deranger,
        trigger=trigger,
    )
    result: dict[str, Any] = {}
    error = None
    executed = False
    try:
        if decision.decision == "act":
            result = execute_action(
                decision,
                persona_root=persona_root,
                spec_archive_root=spec_archive_root,
            )
            executed = True
            _remember_seen(pending, decision.fingerprint, now=now)
            _remove_queued_action(pending, decision.fingerprint)
        elif decision.decision in {"defer", "requires_approval"}:
            _queue_action(pending, decision, now=now)
        elif decision.decision in {"blocked", "skip"}:
            _remember_seen(pending, decision.fingerprint, now=now)
            _remove_queued_action(pending, decision.fingerprint)
    except Exception as exc:
        error = f"{type(exc).__name__}: {exc}"
        logger.debug("initiative action failed: %s", exc)
    finally:
        _save_pending(pending_path, pending)
        _append_log(
            log_path,
            {
                "trigger": trigger,
                "opportunity": asdict(opportunity),
                "decision": {
                    "dimensions": decision.dimensions,
                    "base_score": decision.base_score,
                    "final_score": decision.final_score,
                    "multiplier": decision.multiplier,
                    "decision": decision.decision,
                    "reason": decision.reason,
                    "fingerprint": decision.fingerprint,
                    "inner_state_freshness": inner_state_freshness,
                    "active_conversation": active_conversation,
                },
                "executed": executed,
                "result": result,
                "error": error,
            },
        )
    return InitiativeResult(decision=decision, executed=executed, result=result, error=error)


def _pending_opportunities(pending: dict[str, Any]) -> list[Opportunity]:
    opportunities = []
    for item in pending.get("actions", []):
        if not isinstance(item, dict):
            continue
        if item.get("status") not in {"defer"}:
            continue
        raw = item.get("opportunity")
        if not isinstance(raw, dict):
            continue
        try:
            opportunities.append(
                Opportunity(
                    kind=str(raw.get("kind") or "pending"),
                    action_type=str(raw.get("action_type") or ""),
                    level=int(raw.get("level") or 1),
                    title=str(raw.get("title") or ""),
                    content=str(raw.get("content") or ""),
                    target=raw.get("target"),
                    metadata=raw.get("metadata") if isinstance(raw.get("metadata"), dict) else {},
                )
            )
        except (TypeError, ValueError):
            continue
    return opportunities


def maybe_take_initiative(
    *,
    response: str = "",
    history: Optional[list[dict[str, Any]]] = None,
    source: Any = None,
    session_key: str = "",
    trigger: Trigger = "post_response",
    persona_root: Optional[Path] = None,
    spec_archive_root: Optional[Path] = None,
    now: Optional[float] = None,
) -> list[InitiativeResult]:
    current = now if now is not None else time.time()
    root = persona_root or DEFAULT_PERSONA_ROOT
    pending_path = root / "pending_actions.json"
    log_path = root / "initiative_log.jsonl"
    root.mkdir(parents=True, exist_ok=True)

    if trigger == "post_response":
        try:
            last_user = _last_role_timestamp(history or [], "user") or current
            mark_user_activity(
                persona_root=root,
                source=source,
                session_key=session_key,
                timestamp=last_user,
            )
        except Exception as exc:
            logger.debug("initiative user-activity stamp failed: %s", exc)

    inner_state, freshness = _load_inner_state(root / "inner_state.json", now=current)
    ne_pas_deranger = _desire_weight(root / "desires.json", "ne_pas_deranger")
    last_user_activity = _last_user_activity(persona_root=root, history=history or [], now=current)
    active_conversation = (
        last_user_activity is not None
        and 0 <= current - last_user_activity < ACTIVE_CONVERSATION_SECONDS
    )

    pending = _load_pending(pending_path)
    with _pending_lock(pending_path):
        pending = _load_pending(pending_path)
        _save_pending(pending_path, pending)
        opportunities = detect_artifacts(response, history=history, inner_state=inner_state)
        if trigger == "inactivity":
            opportunities.extend(_pending_opportunities(pending))

        results = []
        for opportunity in opportunities:
            results.append(
                _process_opportunity(
                    opportunity,
                    persona_root=root,
                    pending_path=pending_path,
                    log_path=log_path,
                    spec_archive_root=spec_archive_root,
                    pending=pending,
                    inner_state=inner_state,
                    inner_state_freshness=freshness,
                    ne_pas_deranger=ne_pas_deranger,
                    active_conversation=active_conversation,
                    trigger=trigger,
                    now=current,
                )
            )
    if not opportunities:
        _append_log(
            log_path,
            {
                "trigger": trigger,
                "decision": {
                    "decision": "skip",
                    "reason": "no_opportunity",
                    "inner_state_freshness": freshness,
                    "active_conversation": active_conversation,
                },
                "executed": False,
                "result": {},
                "error": None,
            },
        )
    return results

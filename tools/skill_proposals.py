"""Skill proposal / quarantine queue — persistence for agent-proposed skill changes.

Spike (Kanban t_328bc1ec) adapting the *pattern* — not the code — of OpenClaw's
Skill Workshop pending/quarantine queue to Hermes.

Why this exists
---------------
``skill_manage`` writes a skill to disk and then runs the security scanner
(``tools.skills_guard``) when ``skills.guard_agent_created`` is enabled. Today a
dangerous agent-created write simply **fails closed**: the content is rolled back
and the error is handed to the agent, leaving no durable record of what was
attempted. That is safe but opaque — a human reviewer can never see *what* the
agent tried to write, or deliberately promote a flagged-but-legitimate change.

This module adds a small, append-only **audit/review queue** for proposed skill
changes. It records the proposal, the scan verdict/findings, and any later
reviewer decision. It deliberately does **not** write skills itself — actual
active skill writes stay on the existing ``skill_manage`` path guards. Recording
a quarantine entry never changes the block/rollback decision; it only preserves
the evidence and intent for review.

Security decision (quarantine-record vs direct-block)
-----------------------------------------------------
We keep **fail-closed** as the activation behavior and add **record-for-review**
on top. A dangerous agent-created write is still rolled back and never silently
activates. The queue is an audit trail, not an auto-apply mechanism: promoting a
quarantined proposal back into an active skill must go through ``skill_manage``
again (and re-scan), which is intentionally left as a human-gated follow-up
rather than something this module can do on its own.

Persistence shape
-----------------
Sidecar JSON at ``~/.hermes/skills/.proposals.json`` (same directory and
atomic-write / cross-process-lock discipline as ``tools.skill_usage``). The file
maps ``proposal_id -> record``:

    {
      "id":                <hex12>,
      "skill_name":        str,
      "action":            "create" | "edit" | "patch" | "write_file" | ...,
      "status":            "pending" | "applied" | "rejected" | "quarantined",
      "verdict":           "safe" | "caution" | "dangerous" | None,
      "findings":          [ {pattern_id, severity, category, file, line, description}, ... ],
      "quarantine_reason": str | None,
      "content_hash":      str | None,
      "created_at":        iso8601,
      "reviewed_at":       iso8601 | None,
      "reviewer_action":   "apply" | "reject" | None,
      "reviewer_note":     str | None,
    }

All writes are best-effort: a broken or unwritable sidecar logs at DEBUG and
never breaks the underlying ``skill_manage`` call.
"""

from __future__ import annotations

import json
import logging
import os
import tempfile
import uuid
from contextlib import contextmanager
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional

from hermes_constants import get_hermes_home

logger = logging.getLogger(__name__)

# fcntl is Unix-only; on Windows use msvcrt for file locking. Mirrors
# tools/skill_usage.py so both sidecars share the same locking discipline.
msvcrt = None
try:
    import fcntl
except ImportError:  # pragma: no cover - platform-specific fallback
    fcntl = None
    try:
        import msvcrt
    except ImportError:
        pass


# Proposal lifecycle states.
STATUS_PENDING = "pending"          # proposed, awaiting review (not yet active)
STATUS_APPLIED = "applied"          # reviewer approved; activation happened via skill_manage
STATUS_REJECTED = "rejected"        # reviewer declined
STATUS_QUARANTINED = "quarantined"  # scanner flagged; failed closed, held for review
_VALID_STATUSES = {
    STATUS_PENDING,
    STATUS_APPLIED,
    STATUS_REJECTED,
    STATUS_QUARANTINED,
}

# Reviewer actions recorded against a proposal.
ACTION_APPLY = "apply"
ACTION_REJECT = "reject"
_VALID_REVIEWER_ACTIONS = {ACTION_APPLY, ACTION_REJECT}


def _skills_dir() -> Path:
    return get_hermes_home() / "skills"


def _proposals_file() -> Path:
    return _skills_dir() / ".proposals.json"


@contextmanager
def _proposals_file_lock():
    """Serialize .proposals.json read-modify-write cycles across processes."""
    lock_path = _proposals_file().with_suffix(".json.lock")
    lock_path.parent.mkdir(parents=True, exist_ok=True)

    if fcntl is None and msvcrt is None:
        yield
        return

    if msvcrt and (not lock_path.exists() or lock_path.stat().st_size == 0):
        lock_path.write_text(" ", encoding="utf-8")

    fd = open(lock_path, "r+" if msvcrt else "a+", encoding="utf-8")
    try:
        if fcntl:
            fcntl.flock(fd, fcntl.LOCK_EX)
        else:
            fd.seek(0)
            msvcrt.locking(fd.fileno(), msvcrt.LK_LOCK, 1)
        yield
    finally:
        if fcntl:
            try:
                fcntl.flock(fd, fcntl.LOCK_UN)
            except (OSError, IOError):
                pass
        elif msvcrt:
            try:
                fd.seek(0)
                msvcrt.locking(fd.fileno(), msvcrt.LK_UNLCK, 1)
            except (OSError, IOError):
                pass
        fd.close()


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def _new_id() -> str:
    return uuid.uuid4().hex[:12]


# ---------------------------------------------------------------------------
# Sidecar I/O
# ---------------------------------------------------------------------------

def load_proposals() -> Dict[str, Dict[str, Any]]:
    """Read the whole .proposals.json map. Returns {} on missing/corrupt."""
    path = _proposals_file()
    if not path.exists():
        return {}
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as e:
        logger.debug("Failed to read %s: %s", path, e)
        return {}
    if not isinstance(data, dict):
        return {}
    clean: Dict[str, Dict[str, Any]] = {}
    for k, v in data.items():
        if isinstance(v, dict):
            clean[str(k)] = v
    return clean


def save_proposals(data: Dict[str, Dict[str, Any]]) -> None:
    """Write the proposals map atomically. Best-effort — errors logged, not raised."""
    path = _proposals_file()
    try:
        path.parent.mkdir(parents=True, exist_ok=True)
        fd, tmp_path = tempfile.mkstemp(
            dir=str(path.parent), prefix=".proposals_", suffix=".tmp"
        )
        try:
            with os.fdopen(fd, "w", encoding="utf-8") as f:
                json.dump(data, f, indent=2, sort_keys=True, ensure_ascii=False)
                f.flush()
                os.fsync(f.fileno())
            os.replace(tmp_path, path)
        except BaseException:
            try:
                os.unlink(tmp_path)
            except OSError:
                pass
            raise
    except Exception as e:
        logger.debug("Failed to write %s: %s", path, e, exc_info=True)


def _normalize_findings(findings: Optional[List[Any]]) -> List[Dict[str, Any]]:
    """Coerce scanner Finding objects (or dicts) into plain JSON-safe dicts.

    Accepts ``tools.skills_guard.Finding`` dataclasses, mappings, or anything
    with the expected attributes. Unknown shapes are skipped rather than raising.
    """
    out: List[Dict[str, Any]] = []
    for f in findings or []:
        if isinstance(f, dict):
            src = f
            get = src.get
        else:
            src = f
            get = lambda k, _src=src: getattr(_src, k, None)  # noqa: E731
        rec = {
            "pattern_id": get("pattern_id"),
            "severity": get("severity"),
            "category": get("category"),
            "file": get("file"),
            "line": get("line"),
            "description": get("description"),
        }
        if any(v is not None for v in rec.values()):
            out.append(rec)
    return out


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

def record_proposal(
    skill_name: str,
    action: str,
    status: str = STATUS_PENDING,
    verdict: Optional[str] = None,
    findings: Optional[List[Any]] = None,
    quarantine_reason: Optional[str] = None,
    content_hash: Optional[str] = None,
) -> Optional[str]:
    """Append a proposal record to the queue. Returns its id, or None on failure.

    This never writes or activates a skill — it only records that a change was
    proposed (and, for quarantine entries, why it was held). Best-effort: a
    sidecar failure logs at DEBUG and returns None.
    """
    if status not in _VALID_STATUSES:
        logger.debug("record_proposal: invalid status %r", status)
        return None
    try:
        pid = _new_id()
        record = {
            "id": pid,
            "skill_name": skill_name or "",
            "action": action or "",
            "status": status,
            "verdict": verdict,
            "findings": _normalize_findings(findings),
            "quarantine_reason": quarantine_reason,
            "content_hash": content_hash,
            "created_at": _now_iso(),
            "reviewed_at": None,
            "reviewer_action": None,
            "reviewer_note": None,
        }
        with _proposals_file_lock():
            data = load_proposals()
            # Guard against the (astronomically unlikely) id collision.
            while pid in data:
                pid = _new_id()
                record["id"] = pid
            data[pid] = record
            save_proposals(data)
        return pid
    except Exception as e:
        logger.debug("record_proposal(%s) failed: %s", skill_name, e, exc_info=True)
        return None


def record_quarantine(
    skill_name: str,
    action: str,
    reason: str,
    verdict: Optional[str] = None,
    findings: Optional[List[Any]] = None,
    content_hash: Optional[str] = None,
) -> Optional[str]:
    """Convenience wrapper: record a ``quarantined`` proposal.

    Called from the ``skill_manage`` scan hook when an agent-created write is
    blocked, so the flagged content/intent is preserved for human review even
    though it was (correctly) rolled back and never activated.
    """
    return record_proposal(
        skill_name=skill_name,
        action=action,
        status=STATUS_QUARANTINED,
        verdict=verdict,
        findings=findings,
        quarantine_reason=reason,
        content_hash=content_hash,
    )


def get_proposal(proposal_id: str) -> Optional[Dict[str, Any]]:
    """Return a single proposal record, or None if not found."""
    if not proposal_id:
        return None
    return load_proposals().get(proposal_id)


def list_proposals(status: Optional[str] = None) -> List[Dict[str, Any]]:
    """Return proposals (optionally filtered by status), newest first."""
    rows = list(load_proposals().values())
    if status is not None:
        rows = [r for r in rows if r.get("status") == status]
    rows.sort(key=lambda r: str(r.get("created_at") or ""), reverse=True)
    return rows


def review_proposal(
    proposal_id: str,
    reviewer_action: str,
    note: Optional[str] = None,
) -> bool:
    """Record a reviewer decision against a proposal.

    Sets ``status`` to ``applied`` (for ``apply``) or ``rejected`` (for
    ``reject``) and stamps the reviewer action/note/time. This records the
    *decision only* — it does not write or re-activate the skill. Promoting a
    quarantined proposal into an active skill must go back through
    ``skill_manage`` (and re-scan); that path is intentionally human-gated.

    Returns True if the record was updated, False otherwise.
    """
    if reviewer_action not in _VALID_REVIEWER_ACTIONS:
        logger.debug("review_proposal: invalid reviewer_action %r", reviewer_action)
        return False
    try:
        with _proposals_file_lock():
            data = load_proposals()
            rec = data.get(proposal_id)
            if not isinstance(rec, dict):
                return False
            rec["reviewer_action"] = reviewer_action
            rec["reviewer_note"] = note
            rec["reviewed_at"] = _now_iso()
            rec["status"] = (
                STATUS_APPLIED if reviewer_action == ACTION_APPLY else STATUS_REJECTED
            )
            data[proposal_id] = rec
            save_proposals(data)
        return True
    except Exception as e:
        logger.debug("review_proposal(%s) failed: %s", proposal_id, e, exc_info=True)
        return False

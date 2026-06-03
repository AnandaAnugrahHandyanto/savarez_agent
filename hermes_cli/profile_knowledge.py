"""Per-specialist knowledge corpus — durable local evidence index.

Each Spearhead specialist (Gond, Helm, Waukeen, Mystra, Tymora, …) keeps
its own append-only evidence corpus under
``<profile_dir>/knowledge/``. Entries are derived from verified local
artifacts (audit JSON, planning notes, source spike reports, etc.), not
from prompts. Gated content (paywall/login-wall URLs) is stored in a
separate file as **limitation metadata only** — never as if it had been
read.

Layout under ``<profile_dir>/knowledge/``:

    corpus.jsonl   one JSON object per line. Append-only. Each entry has
                   a stable id (sha256 of normalized source identity),
                   provenance, confidence, status, tags, and an optional
                   short evidence excerpt.
    gates.jsonl    one JSON object per line. Records *that a gated URL
                   exists*, not its body. Confidence is fixed to
                   ``gated_unread``.
    index.json     rebuildable index — by_id, by_tag, by_source_type,
                   by_status, by_confidence. Always derivable from the
                   JSONL files; rewritten on each ingest/update.

Schema is intentionally small. The single source of truth is this
module: ``CORPUS_ENTRY_REQUIRED_KEYS`` and ``GATE_ENTRY_REQUIRED_KEYS``.

CLI:

    python -m hermes_cli.profile_knowledge ingest-file <profile> <path> \
        --tag domain:engineering --tag type:audit
    python -m hermes_cli.profile_knowledge ingest-audit <profile> <audit.json>
    python -m hermes_cli.profile_knowledge ingest-gate <profile> <url> \
        --gate-kind paywall --tag domain:finance
    python -m hermes_cli.profile_knowledge query <profile> [--tag X] [--json]
    python -m hermes_cli.profile_knowledge status <profile> <id> <new_status>
    python -m hermes_cli.profile_knowledge matrix [--json]

``matrix`` is the deterministic ``knowledge_corpus_ready`` emitter used
by the readiness matrix; it returns a row per specialist with the file
paths, counts, and whether the corpus has at least one verified entry.
"""

from __future__ import annotations

import argparse
import datetime as _dt
import hashlib
import json
import os
import sys
from pathlib import Path
from typing import Any, Iterable, Optional


CORPUS_DIRNAME = "knowledge"
CORPUS_FILENAME = "corpus.jsonl"
GATES_FILENAME = "gates.jsonl"
INDEX_FILENAME = "index.json"

# Confidence labels — narrow on purpose. ``verified`` means the source
# was read locally; ``self_reported`` means the entry came from a
# system that asserts its own correctness without an independent check
# (kept rare); ``gated_unread`` means we recorded metadata for a URL we
# could not load (paywall/login).
CONFIDENCE_VERIFIED = "verified"
CONFIDENCE_SELF_REPORTED = "self_reported"
CONFIDENCE_GATED_UNREAD = "gated_unread"
ALLOWED_CONFIDENCE = (
    CONFIDENCE_VERIFIED,
    CONFIDENCE_SELF_REPORTED,
    CONFIDENCE_GATED_UNREAD,
)

STATUS_ACTIVE = "active"
STATUS_SUPERSEDED = "superseded"
STATUS_INVALIDATED = "invalidated"
ALLOWED_STATUS = (STATUS_ACTIVE, STATUS_SUPERSEDED, STATUS_INVALIDATED)

ALLOWED_GATE_KINDS = (
    "paywall",
    "login_wall",
    "rate_limit",
    "api_limit",
    "geofence",
    "unknown",
)

# Required keys on each entry. Type matters — wrong types reject at
# ingest time so the corpus stays queryable.
CORPUS_ENTRY_REQUIRED_KEYS: dict[str, type] = {
    "id": str,
    "ingested_at": str,
    "specialist": str,
    "title": str,
    "source_type": str,
    "tags": list,
    "confidence": str,
    "status": str,
    "provenance": dict,
}

GATE_ENTRY_REQUIRED_KEYS: dict[str, type] = {
    "id": str,
    "ingested_at": str,
    "specialist": str,
    "url": str,
    "gate_kind": str,
    "tags": list,
    "confidence": str,
    "status": str,
    "provenance": dict,
}

# Specialists that should always have a corpus. Mirrors profile_contract.
KNOWN_SPECIALISTS: tuple[str, ...] = (
    "gond",
    "helm",
    "waukeen",
    "mystra",
    "tymora",
)

INGEST_VERSION = 1


# ---------------------------------------------------------------------------
# Path helpers
# ---------------------------------------------------------------------------


def _profiles_root() -> Path:
    return Path.home() / ".hermes" / "profiles"


def profile_dir_for(name: str) -> Path:
    return _profiles_root() / name


def corpus_dir(profile_dir: Path) -> Path:
    return profile_dir / CORPUS_DIRNAME


def corpus_path(profile_dir: Path) -> Path:
    return corpus_dir(profile_dir) / CORPUS_FILENAME


def gates_path(profile_dir: Path) -> Path:
    return corpus_dir(profile_dir) / GATES_FILENAME


def index_path(profile_dir: Path) -> Path:
    return corpus_dir(profile_dir) / INDEX_FILENAME


def _ensure_corpus_dir(profile_dir: Path) -> Path:
    cdir = corpus_dir(profile_dir)
    cdir.mkdir(parents=True, exist_ok=True)
    return cdir


# ---------------------------------------------------------------------------
# Identity / hashing
# ---------------------------------------------------------------------------


def _now_iso() -> str:
    return _dt.datetime.now(_dt.timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def _sha256_of_file(path: Path) -> Optional[str]:
    if not path.is_file():
        return None
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(65536), b""):
            h.update(chunk)
    return h.hexdigest()


def _sha256_of_text(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def _stable_entry_id(specialist: str, source_identity: str) -> str:
    """Deterministic id so the same source ingested twice yields the same id.

    ``source_identity`` is the unambiguous handle (absolute path + sha,
    or canonical URL). Hashing keeps ids fixed-length and filename-safe.
    """
    raw = f"{specialist}|{source_identity}"
    return _sha256_of_text(raw)[:32]


# ---------------------------------------------------------------------------
# Validation
# ---------------------------------------------------------------------------


def _check_required(entry: dict, spec: dict[str, type]) -> list[str]:
    errors: list[str] = []
    for key, expected_type in spec.items():
        if key not in entry:
            errors.append(f"{key}: missing")
            continue
        if expected_type is bool and not isinstance(entry[key], bool):
            errors.append(f"{key}: must be bool")
        elif not isinstance(entry[key], expected_type):
            errors.append(f"{key}: must be {expected_type.__name__}")
    return errors


def validate_corpus_entry(entry: dict) -> list[str]:
    errors = _check_required(entry, CORPUS_ENTRY_REQUIRED_KEYS)
    if isinstance(entry.get("confidence"), str) and entry["confidence"] not in ALLOWED_CONFIDENCE:
        errors.append(f"confidence: must be one of {ALLOWED_CONFIDENCE}")
    if isinstance(entry.get("status"), str) and entry["status"] not in ALLOWED_STATUS:
        errors.append(f"status: must be one of {ALLOWED_STATUS}")
    tags = entry.get("tags")
    if isinstance(tags, list) and not all(isinstance(t, str) and t.strip() for t in tags):
        errors.append("tags: must be a list of non-empty strings")
    # Gated-unread entries belong in gates.jsonl, not corpus.jsonl.
    if entry.get("confidence") == CONFIDENCE_GATED_UNREAD:
        errors.append("confidence: gated_unread is for gates.jsonl, not corpus.jsonl")
    return errors


def validate_gate_entry(entry: dict) -> list[str]:
    errors = _check_required(entry, GATE_ENTRY_REQUIRED_KEYS)
    if isinstance(entry.get("gate_kind"), str) and entry["gate_kind"] not in ALLOWED_GATE_KINDS:
        errors.append(f"gate_kind: must be one of {ALLOWED_GATE_KINDS}")
    if entry.get("confidence") != CONFIDENCE_GATED_UNREAD:
        errors.append("confidence: gate entries must use 'gated_unread'")
    if isinstance(entry.get("status"), str) and entry["status"] not in ALLOWED_STATUS:
        errors.append(f"status: must be one of {ALLOWED_STATUS}")
    tags = entry.get("tags")
    if isinstance(tags, list) and not all(isinstance(t, str) and t.strip() for t in tags):
        errors.append("tags: must be a list of non-empty strings")
    return errors


# ---------------------------------------------------------------------------
# IO — JSONL append + read
# ---------------------------------------------------------------------------


def _append_jsonl(path: Path, entry: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with open(path, "a", encoding="utf-8") as f:
        f.write(json.dumps(entry, sort_keys=True))
        f.write("\n")


def _read_jsonl(path: Path) -> list[dict]:
    if not path.is_file():
        return []
    out: list[dict] = []
    with open(path, "r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            try:
                obj = json.loads(line)
            except json.JSONDecodeError:
                continue
            if isinstance(obj, dict):
                out.append(obj)
    return out


def _rewrite_jsonl(path: Path, entries: Iterable[dict]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(path.suffix + ".tmp")
    with open(tmp, "w", encoding="utf-8") as f:
        for e in entries:
            f.write(json.dumps(e, sort_keys=True))
            f.write("\n")
    os.replace(tmp, path)


def read_entries(profile_dir: Path) -> list[dict]:
    return _read_jsonl(corpus_path(profile_dir))


def read_gates(profile_dir: Path) -> list[dict]:
    return _read_jsonl(gates_path(profile_dir))


# ---------------------------------------------------------------------------
# Ingest helpers
# ---------------------------------------------------------------------------


def _normalize_tags(tags: Optional[Iterable[str]]) -> list[str]:
    if not tags:
        return []
    seen: list[str] = []
    for t in tags:
        if not isinstance(t, str):
            continue
        t = t.strip()
        if t and t not in seen:
            seen.append(t)
    return seen


def _provenance(ingested_by: str, extra: Optional[dict] = None) -> dict:
    prov = {"ingested_by": ingested_by, "ingest_version": INGEST_VERSION}
    if extra:
        prov.update(extra)
    return prov


def find_existing_entry(profile_dir: Path, entry_id: str) -> Optional[dict]:
    for e in read_entries(profile_dir):
        if e.get("id") == entry_id:
            return e
    for e in read_gates(profile_dir):
        if e.get("id") == entry_id:
            return e
    return None


def ingest_local_artifact(
    profile_dir: Path,
    artifact_path: Path,
    *,
    specialist: Optional[str] = None,
    title: Optional[str] = None,
    summary: Optional[str] = None,
    source_type: str = "local_artifact",
    tags: Optional[Iterable[str]] = None,
    evidence_excerpt: Optional[str] = None,
    ingested_by: str = "profile_knowledge.ingest_local_artifact",
    confidence: str = CONFIDENCE_VERIFIED,
    extra_provenance: Optional[dict] = None,
) -> dict:
    """Ingest a single local file as a corpus entry.

    The file MUST exist locally — we hash and stat it. Calling this with
    a path we have not actually read is a programming error; the absent
    file raises ``FileNotFoundError`` so the orchestrator cannot
    silently record evidence it never saw.
    """
    if not artifact_path.is_file():
        raise FileNotFoundError(f"artifact not found: {artifact_path}")
    if confidence == CONFIDENCE_GATED_UNREAD:
        raise ValueError("use ingest_gated_source for gated_unread content")
    specialist_name = specialist or profile_dir.name
    sha = _sha256_of_file(artifact_path)
    abs_path = str(artifact_path.resolve())
    mtime = _dt.datetime.fromtimestamp(
        artifact_path.stat().st_mtime, tz=_dt.timezone.utc
    ).strftime("%Y-%m-%dT%H:%M:%SZ")
    entry_id = _stable_entry_id(specialist_name, f"file:{abs_path}@{sha}")
    entry: dict[str, Any] = {
        "id": entry_id,
        "ingested_at": _now_iso(),
        "specialist": specialist_name,
        "title": title or artifact_path.name,
        "summary": summary or "",
        "source_type": source_type,
        "source_path": abs_path,
        "source_url": None,
        "source_sha256": sha,
        "source_mtime_iso": mtime,
        "source_size_bytes": artifact_path.stat().st_size,
        "tags": _normalize_tags(tags),
        "confidence": confidence,
        "status": STATUS_ACTIVE,
        "evidence_excerpt": evidence_excerpt or "",
        "provenance": _provenance(ingested_by, extra_provenance),
    }
    errors = validate_corpus_entry(entry)
    if errors:
        raise ValueError(f"corpus entry invalid: {errors}")
    _ensure_corpus_dir(profile_dir)
    # Idempotent — skip if an active entry with the same id already exists.
    existing = find_existing_entry(profile_dir, entry_id)
    if existing is not None and existing.get("status") == STATUS_ACTIVE:
        return existing
    _append_jsonl(corpus_path(profile_dir), entry)
    write_index(profile_dir)
    return entry


def ingest_audit_log(
    profile_dir: Path,
    audit_path: Path,
    *,
    specialist: Optional[str] = None,
    tags: Optional[Iterable[str]] = None,
    ingested_by: str = "profile_knowledge.ingest_audit_log",
) -> dict:
    """Ingest a standalone-orchestrator audit JSON as a corpus entry.

    Reads the audit file, extracts the stamp / blocked summary as the
    evidence excerpt, and records provenance. Hashes the actual bytes
    on disk so a re-run of the orchestrator with the same audit content
    is idempotent.
    """
    if not audit_path.is_file():
        raise FileNotFoundError(f"audit log not found: {audit_path}")
    try:
        audit = json.loads(audit_path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        raise ValueError(f"audit log is not valid JSON: {audit_path}: {exc}") from exc
    if not isinstance(audit, dict):
        raise ValueError(f"audit log is not a JSON object: {audit_path}")
    stamp = audit.get("stamp") or ""
    blocked = audit.get("blocked_by_class") or {}
    blocked_total = sum(v for v in blocked.values() if isinstance(v, int))
    excerpt = (
        f"stamp={stamp} blocked_total={blocked_total} "
        f"snapshot_count={audit.get('snapshot_count')} "
        f"snapshot_stale={audit.get('snapshot_stale')}"
    )
    title = f"orchestrator audit {stamp or audit_path.name}"
    full_tags = list(tags or [])
    full_tags.append("type:orchestrator_audit")
    return ingest_local_artifact(
        profile_dir,
        audit_path,
        specialist=specialist,
        title=title,
        summary=excerpt,
        source_type="orchestrator_audit",
        tags=full_tags,
        evidence_excerpt=excerpt,
        ingested_by=ingested_by,
        extra_provenance={"audit_stamp": stamp},
    )


def ingest_notion_intake_artifact(
    profile_dir: Path,
    artifact_path: Path,
    *,
    notion_item: dict[str, Any],
    specialist: Optional[str] = None,
    artifact_kind: str = "verified_artifact",
    title: Optional[str] = None,
    summary: Optional[str] = None,
    tags: Optional[Iterable[str]] = None,
    evidence_excerpt: Optional[str] = None,
    ingested_by: str = "profile_knowledge.ingest_notion_intake_artifact",
) -> dict:
    """Ingest a verified local artifact surfaced by Notion intake.

    This is deliberately narrower than generic ``ingest_local_artifact``:
    the caller must provide the Notion item metadata that made the local
    artifact eligible. The artifact itself still must exist on disk and is
    hashed/stat'ed before any corpus entry is appended. URLs, login/paywall
    placeholders, and unseen source bodies never enter ``corpus.jsonl`` via
    this helper.
    """
    if not isinstance(notion_item, dict):
        raise ValueError("notion_item must be a dict")
    if not artifact_kind or not isinstance(artifact_kind, str):
        raise ValueError("artifact_kind must be a non-empty string")
    specialist_name = specialist or profile_dir.name
    nid = str(notion_item.get("id") or "")
    nurl = str(notion_item.get("url") or "")
    ntitle = str(notion_item.get("title") or "")
    full_tags = list(tags or [])
    for t in (
        "type:notion_intake_artifact",
        "source:notion_intake",
        f"specialist:{specialist_name}",
        f"artifact_kind:{artifact_kind}",
    ):
        full_tags.append(t)
    if nid:
        full_tags.append(f"notion_id:{nid}")
    entry_title = title or f"Notion intake artifact: {ntitle or artifact_path.name}"
    entry_summary = summary or f"Verified local artifact from Notion intake item {nid or '(no id)'}"
    provenance = {
        "notion_id": nid,
        "notion_url": nurl,
        "notion_title": ntitle,
        "notion_priority": notion_item.get("priority") or "",
        "notion_context": notion_item.get("context") or "",
        "notion_last_edited_time": notion_item.get("last_edited_time") or "",
        "artifact_kind": artifact_kind,
        "verified_local_artifact": True,
    }
    return ingest_local_artifact(
        profile_dir,
        artifact_path,
        specialist=specialist_name,
        title=entry_title,
        summary=entry_summary,
        source_type="notion_intake_artifact",
        tags=full_tags,
        evidence_excerpt=evidence_excerpt,
        ingested_by=ingested_by,
        confidence=CONFIDENCE_VERIFIED,
        extra_provenance=provenance,
    )


def ingest_gated_source(
    profile_dir: Path,
    url: str,
    *,
    gate_kind: str,
    specialist: Optional[str] = None,
    title: Optional[str] = None,
    tags: Optional[Iterable[str]] = None,
    notes: Optional[str] = None,
    ingested_by: str = "profile_knowledge.ingest_gated_source",
) -> dict:
    """Record metadata for a paywalled/login-walled source.

    The corpus deliberately stores only the URL, gate kind, and a short
    note about why content could not be read. The body is NEVER stored
    or claimed as evidence.
    """
    if gate_kind not in ALLOWED_GATE_KINDS:
        raise ValueError(f"gate_kind must be one of {ALLOWED_GATE_KINDS}")
    if not isinstance(url, str) or not url.strip():
        raise ValueError("url must be a non-empty string")
    specialist_name = specialist or profile_dir.name
    canonical = url.strip()
    entry_id = _stable_entry_id(specialist_name, f"gate:{canonical}")
    entry = {
        "id": entry_id,
        "ingested_at": _now_iso(),
        "specialist": specialist_name,
        "url": canonical,
        "title": title or canonical,
        "gate_kind": gate_kind,
        "tags": _normalize_tags(tags),
        "confidence": CONFIDENCE_GATED_UNREAD,
        "status": STATUS_ACTIVE,
        "notes": notes or "",
        "provenance": _provenance(ingested_by, {"observer": ingested_by}),
    }
    errors = validate_gate_entry(entry)
    if errors:
        raise ValueError(f"gate entry invalid: {errors}")
    _ensure_corpus_dir(profile_dir)
    existing = find_existing_entry(profile_dir, entry_id)
    if existing is not None and existing.get("status") == STATUS_ACTIVE:
        return existing
    _append_jsonl(gates_path(profile_dir), entry)
    write_index(profile_dir)
    return entry


# ---------------------------------------------------------------------------
# Query / update
# ---------------------------------------------------------------------------


def query(
    profile_dir: Path,
    *,
    tags: Optional[Iterable[str]] = None,
    source_type: Optional[str] = None,
    status: Optional[str] = None,
    confidence: Optional[str] = None,
    include_gates: bool = False,
    specialist: Optional[str] = None,
) -> list[dict]:
    """Filter corpus (and optionally gates) by simple AND of predicates.

    ``tags`` is treated as "all of these tags must be present".
    """
    rows: list[dict] = list(read_entries(profile_dir))
    if include_gates:
        rows.extend(read_gates(profile_dir))
    needed_tags = set(_normalize_tags(tags)) if tags else None

    def keep(e: dict) -> bool:
        if needed_tags and not needed_tags.issubset(set(e.get("tags") or [])):
            return False
        if source_type and e.get("source_type") != source_type:
            return False
        if status and e.get("status") != status:
            return False
        if confidence and e.get("confidence") != confidence:
            return False
        if specialist and e.get("specialist") != specialist:
            return False
        return True

    return [e for e in rows if keep(e)]


def update_status(profile_dir: Path, entry_id: str, new_status: str) -> dict:
    """Rewrite an entry's status in place. Returns the updated entry."""
    if new_status not in ALLOWED_STATUS:
        raise ValueError(f"status must be one of {ALLOWED_STATUS}")
    updated: Optional[dict] = None
    for filename in (CORPUS_FILENAME, GATES_FILENAME):
        path = corpus_dir(profile_dir) / filename
        entries = _read_jsonl(path)
        if not entries:
            continue
        changed = False
        for e in entries:
            if e.get("id") == entry_id:
                e["status"] = new_status
                e["status_updated_at"] = _now_iso()
                updated = e
                changed = True
        if changed:
            _rewrite_jsonl(path, entries)
    if updated is None:
        raise KeyError(f"entry not found: {entry_id}")
    write_index(profile_dir)
    return updated


# ---------------------------------------------------------------------------
# Index
# ---------------------------------------------------------------------------


def build_index(profile_dir: Path) -> dict:
    entries = read_entries(profile_dir)
    gates = read_gates(profile_dir)
    by_id: dict[str, dict] = {}
    by_tag: dict[str, list[str]] = {}
    by_source_type: dict[str, int] = {}
    by_status: dict[str, int] = {}
    by_confidence: dict[str, int] = {}
    for source in (entries, gates):
        for e in source:
            eid = e.get("id")
            if not isinstance(eid, str):
                continue
            by_id[eid] = {
                "specialist": e.get("specialist"),
                "title": e.get("title"),
                "source_type": e.get("source_type") or ("gate" if "url" in e else "unknown"),
                "status": e.get("status"),
                "confidence": e.get("confidence"),
            }
            for t in e.get("tags") or []:
                if isinstance(t, str) and t:
                    by_tag.setdefault(t, []).append(eid)
            st = e.get("source_type") or ("gate" if "url" in e else "unknown")
            by_source_type[st] = by_source_type.get(st, 0) + 1
            status = e.get("status")
            if isinstance(status, str):
                by_status[status] = by_status.get(status, 0) + 1
            conf = e.get("confidence")
            if isinstance(conf, str):
                by_confidence[conf] = by_confidence.get(conf, 0) + 1
    return {
        "generated_at": _now_iso(),
        "specialist": profile_dir.name,
        "counts": {
            "entries": len(entries),
            "gates": len(gates),
        },
        "by_source_type": by_source_type,
        "by_status": by_status,
        "by_confidence": by_confidence,
        "by_tag": {k: sorted(set(v)) for k, v in by_tag.items()},
        "by_id": by_id,
    }


def write_index(profile_dir: Path) -> Path:
    _ensure_corpus_dir(profile_dir)
    idx = build_index(profile_dir)
    p = index_path(profile_dir)
    tmp = p.with_suffix(p.suffix + ".tmp")
    tmp.write_text(json.dumps(idx, indent=2, sort_keys=True), encoding="utf-8")
    os.replace(tmp, p)
    return p


# ---------------------------------------------------------------------------
# Orchestrator wiring — convenience that never raises
# ---------------------------------------------------------------------------


def update_corpus_from_audit(
    profile_name: str,
    audit_path: Path,
    *,
    tags: Optional[Iterable[str]] = None,
    ingested_by: str = "orchestrator.update_corpus_from_audit",
) -> Optional[dict]:
    """Best-effort: ingest a freshly written audit log into the corpus.

    The orchestrator tick calls this *after* writing the audit JSON it
    just produced — so the source is by definition a verified local
    artifact. Returns the entry on success, ``None`` on any failure;
    never raises. The orchestrator must keep ticking even if the corpus
    has a transient problem (full disk, race, etc.).
    """
    try:
        pdir = profile_dir_for(profile_name)
        if not pdir.is_dir():
            return None
        if not audit_path.is_file():
            return None
        return ingest_audit_log(
            pdir,
            audit_path,
            tags=tags,
            ingested_by=ingested_by,
        )
    except Exception:
        return None


# ---------------------------------------------------------------------------
# Readiness — knowledge_corpus_ready per specialist
# ---------------------------------------------------------------------------


def corpus_ready(profile_dir: Path) -> dict:
    """Return {ok, has_corpus_dir, entries, gates, verified_entries, ...}.

    Ready means: corpus dir exists AND ``corpus.jsonl`` has at least one
    verified entry. ``gates.jsonl`` is optional. An empty or missing
    corpus is reported as not ready, never blocked.
    """
    cdir = corpus_dir(profile_dir)
    cpath = corpus_path(profile_dir)
    gpath = gates_path(profile_dir)
    has_dir = cdir.is_dir()
    entries = read_entries(profile_dir) if has_dir else []
    gates = read_gates(profile_dir) if has_dir else []
    verified = [e for e in entries if e.get("confidence") == CONFIDENCE_VERIFIED]
    invalid: list[str] = []
    for e in entries:
        errors = validate_corpus_entry(e)
        if errors:
            invalid.append(f"corpus:{e.get('id')}:{errors}")
    for e in gates:
        errors = validate_gate_entry(e)
        if errors:
            invalid.append(f"gate:{e.get('id')}:{errors}")
    ok = has_dir and len(verified) > 0 and not invalid
    return {
        "name": profile_dir.name,
        "ok": ok,
        "has_corpus_dir": has_dir,
        "corpus_path": str(cpath),
        "gates_path": str(gpath),
        "entries": len(entries),
        "gates": len(gates),
        "verified_entries": len(verified),
        "invalid_entries": invalid,
    }


def knowledge_corpus_matrix(
    names: Optional[Iterable[str]] = None,
    *,
    profiles_root: Optional[Path] = None,
) -> dict:
    root = profiles_root if profiles_root is not None else _profiles_root()
    targets = list(names) if names is not None else list(KNOWN_SPECIALISTS)
    rows = [corpus_ready(root / n) for n in targets]
    return {
        "profiles_root": str(root),
        "generated_for": targets,
        "rows": rows,
        "all_ok": all(r["ok"] for r in rows) if rows else True,
    }


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------


def _format_matrix_text(matrix: dict) -> str:
    lines = ["KNOWLEDGE_CORPUS_READY matrix", f"profiles_root: {matrix['profiles_root']}", ""]
    width = max((len(r["name"]) for r in matrix["rows"]), default=4)
    for r in matrix["rows"]:
        mark = "OK  " if r["ok"] else "FAIL"
        lines.append(
            f"  {mark}  {r['name']:<{width}}  entries={r['entries']} "
            f"verified={r['verified_entries']} gates={r['gates']}"
        )
        for inv in r["invalid_entries"]:
            lines.append(f"          - invalid: {inv}")
        if not r["has_corpus_dir"]:
            lines.append("          - corpus dir missing")
    lines.append("")
    lines.append("all_ok: " + ("yes" if matrix["all_ok"] else "no"))
    return "\n".join(lines)


def _cmd_ingest_file(args: argparse.Namespace) -> int:
    pdir = profile_dir_for(args.profile)
    if not pdir.is_dir():
        print(f"profile dir not found: {pdir}", file=sys.stderr)
        return 2
    try:
        entry = ingest_local_artifact(
            pdir,
            Path(args.path).resolve(),
            title=args.title,
            summary=args.summary,
            source_type=args.source_type,
            tags=args.tag,
            evidence_excerpt=args.excerpt,
            ingested_by=args.ingested_by or "cli.ingest-file",
        )
    except (FileNotFoundError, ValueError) as exc:
        print(str(exc), file=sys.stderr)
        return 3
    print(json.dumps({"id": entry["id"], "path": entry["source_path"]}))
    return 0


def _cmd_ingest_audit(args: argparse.Namespace) -> int:
    pdir = profile_dir_for(args.profile)
    if not pdir.is_dir():
        print(f"profile dir not found: {pdir}", file=sys.stderr)
        return 2
    try:
        entry = ingest_audit_log(
            pdir,
            Path(args.path).resolve(),
            tags=args.tag,
            ingested_by=args.ingested_by or "cli.ingest-audit",
        )
    except (FileNotFoundError, ValueError) as exc:
        print(str(exc), file=sys.stderr)
        return 3
    print(json.dumps({"id": entry["id"], "path": entry["source_path"]}))
    return 0


def _cmd_ingest_gate(args: argparse.Namespace) -> int:
    pdir = profile_dir_for(args.profile)
    if not pdir.is_dir():
        print(f"profile dir not found: {pdir}", file=sys.stderr)
        return 2
    try:
        entry = ingest_gated_source(
            pdir,
            args.url,
            gate_kind=args.gate_kind,
            title=args.title,
            tags=args.tag,
            notes=args.notes,
            ingested_by=args.ingested_by or "cli.ingest-gate",
        )
    except ValueError as exc:
        print(str(exc), file=sys.stderr)
        return 3
    print(json.dumps({"id": entry["id"], "url": entry["url"]}))
    return 0


def _cmd_query(args: argparse.Namespace) -> int:
    pdir = profile_dir_for(args.profile)
    if not pdir.is_dir():
        print(f"profile dir not found: {pdir}", file=sys.stderr)
        return 2
    rows = query(
        pdir,
        tags=args.tag,
        source_type=args.source_type,
        status=args.status,
        confidence=args.confidence,
        include_gates=args.include_gates,
    )
    if args.json:
        print(json.dumps(rows, indent=2, sort_keys=True))
    else:
        for e in rows:
            print(
                f"{e.get('id')}  {e.get('confidence'):<14}  "
                f"{e.get('status'):<12}  {e.get('title') or e.get('url')}"
            )
    return 0


def _cmd_status(args: argparse.Namespace) -> int:
    pdir = profile_dir_for(args.profile)
    if not pdir.is_dir():
        print(f"profile dir not found: {pdir}", file=sys.stderr)
        return 2
    try:
        entry = update_status(pdir, args.entry_id, args.new_status)
    except (KeyError, ValueError) as exc:
        print(str(exc), file=sys.stderr)
        return 3
    print(json.dumps({"id": entry["id"], "status": entry["status"]}))
    return 0


def _cmd_matrix(args: argparse.Namespace) -> int:
    matrix = knowledge_corpus_matrix()
    if args.json:
        print(json.dumps(matrix, indent=2, sort_keys=True))
    else:
        print(_format_matrix_text(matrix))
    if args.strict and not matrix["all_ok"]:
        return 1
    return 0


def _cmd_rebuild_index(args: argparse.Namespace) -> int:
    pdir = profile_dir_for(args.profile)
    if not pdir.is_dir():
        print(f"profile dir not found: {pdir}", file=sys.stderr)
        return 2
    path = write_index(pdir)
    print(str(path))
    return 0


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="python -m hermes_cli.profile_knowledge",
        description="Per-specialist knowledge corpus — durable evidence index.",
    )
    sub = parser.add_subparsers(dest="cmd", required=True)

    p_if = sub.add_parser("ingest-file", help="ingest a single verified local file")
    p_if.add_argument("profile")
    p_if.add_argument("path", help="absolute or relative path to the file")
    p_if.add_argument("--title")
    p_if.add_argument("--summary", default="")
    p_if.add_argument("--source-type", default="local_artifact")
    p_if.add_argument("--tag", action="append", default=[])
    p_if.add_argument("--excerpt", default="")
    p_if.add_argument("--ingested-by")
    p_if.set_defaults(func=_cmd_ingest_file)

    p_ia = sub.add_parser("ingest-audit", help="ingest a standalone-orchestrator audit JSON")
    p_ia.add_argument("profile")
    p_ia.add_argument("path")
    p_ia.add_argument("--tag", action="append", default=[])
    p_ia.add_argument("--ingested-by")
    p_ia.set_defaults(func=_cmd_ingest_audit)

    p_ig = sub.add_parser("ingest-gate", help="record metadata for a gated (paywall/login) URL")
    p_ig.add_argument("profile")
    p_ig.add_argument("url")
    p_ig.add_argument("--gate-kind", required=True, choices=list(ALLOWED_GATE_KINDS))
    p_ig.add_argument("--title")
    p_ig.add_argument("--tag", action="append", default=[])
    p_ig.add_argument("--notes", default="")
    p_ig.add_argument("--ingested-by")
    p_ig.set_defaults(func=_cmd_ingest_gate)

    p_q = sub.add_parser("query", help="query the corpus (AND of predicates)")
    p_q.add_argument("profile")
    p_q.add_argument("--tag", action="append", default=[])
    p_q.add_argument("--source-type")
    p_q.add_argument("--status", choices=list(ALLOWED_STATUS))
    p_q.add_argument("--confidence", choices=list(ALLOWED_CONFIDENCE))
    p_q.add_argument("--include-gates", action="store_true")
    p_q.add_argument("--json", action="store_true")
    p_q.set_defaults(func=_cmd_query)

    p_s = sub.add_parser("status", help="update an entry's status (active/superseded/invalidated)")
    p_s.add_argument("profile")
    p_s.add_argument("entry_id")
    p_s.add_argument("new_status", choices=list(ALLOWED_STATUS))
    p_s.set_defaults(func=_cmd_status)

    p_m = sub.add_parser("matrix", help="knowledge_corpus_ready matrix for known specialists")
    p_m.add_argument("--json", action="store_true")
    p_m.add_argument(
        "--strict",
        action="store_true",
        help="exit non-zero if any specialist corpus is not ready (default: always 0)",
    )
    p_m.set_defaults(func=_cmd_matrix)

    p_ri = sub.add_parser("rebuild-index", help="rebuild index.json from corpus.jsonl + gates.jsonl")
    p_ri.add_argument("profile")
    p_ri.set_defaults(func=_cmd_rebuild_index)

    return parser


def main(argv: Optional[list[str]] = None) -> int:
    parser = _build_parser()
    args = parser.parse_args(argv)
    return args.func(args)


if __name__ == "__main__":
    sys.exit(main())

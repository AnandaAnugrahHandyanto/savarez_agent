import copy
import datetime as _datetime
import hashlib
import json
import os
import re
import uuid
from pathlib import Path
from typing import Any

from agent import codex_workflow_provenance as provenance


SCHEMA_VERSION = 1


class LedgerSchemaUnsupported(ValueError):
    pass


def repo_id(repo: Path) -> str:
    return provenance.repo_id(repo)


def _hermes_home() -> Path:
    configured = os.environ.get("HERMES_HOME")
    if configured:
        return Path(configured)
    return Path.home() / ".hermes"


def _safe_segment(value: str | None, fallback: str) -> str:
    raw = str(value or fallback).strip()
    safe = re.sub(r"[^A-Za-z0-9._-]+", "-", raw).strip("-._")
    return safe[:96] or fallback


def ledger_path(*, repo: Path, branch: str | None, stage_id: str, root: Path | None = None) -> Path:
    base = root or (_hermes_home() / "runtime" / "codex_workflows")
    return base / repo_id(repo) / _safe_segment(branch, "detached") / f"{_safe_segment(stage_id, 'stage')}.json"


def _redact_text(value: str, *, extra_paths: tuple[str, ...] = ()) -> str:
    redacted = value
    home = os.environ.get("HOME")
    hermes_home = os.environ.get("HERMES_HOME")
    if hermes_home:
        redacted = redacted.replace(hermes_home, "<HERMES_HOME>")
    if home:
        redacted = redacted.replace(home, "<HOME>")
    for path in sorted((p for p in extra_paths if p), key=len, reverse=True):
        redacted = redacted.replace(path, "<PATH>")
    redacted = re.sub(r"\bsk-[A-Za-z0-9_.-]{8,}\b", "<REDACTED>", redacted)
    redacted = re.sub(
        r"(?i)\b([A-Z0-9_]*(?:API[_-]?KEY|TOKEN|SECRET)[A-Z0-9_]*)\s*[:=]\s*[^,\s\"']+",
        r"\1=<REDACTED>",
        redacted,
    )
    redacted = re.sub(
        r"(?<![A-Za-z0-9_<:>])/(?:[A-Za-z0-9._-]+/)+[A-Za-z0-9._-]*",
        "<PATH>",
        redacted,
    )
    if redacted.startswith("/"):
        redacted = "<PATH>"
    return redacted


def redact(value: Any, *, extra_paths: tuple[str, ...] = ()) -> Any:
    if isinstance(value, str):
        return _redact_text(value, extra_paths=extra_paths)
    if isinstance(value, list):
        return [redact(item, extra_paths=extra_paths) for item in value]
    if isinstance(value, dict):
        return {str(key): redact(item, extra_paths=extra_paths) for key, item in value.items()}
    return value


def _fsync_dir(path: Path) -> None:
    try:
        fd = os.open(str(path), os.O_RDONLY)
    except OSError:
        return
    try:
        os.fsync(fd)
    except OSError:
        pass
    finally:
        os.close(fd)


def write_ledger(payload: dict[str, Any], *, root: Path | None = None) -> Path:
    if payload.get("schema_version") != SCHEMA_VERSION:
        raise LedgerSchemaUnsupported("ledger_schema_unsupported")
    repo_info = payload.get("repo") if isinstance(payload.get("repo"), dict) else {}
    repo_path = Path(str(repo_info.get("path") or repo_info.get("path_redacted") or "."))
    branch = repo_info.get("branch")
    stage_id = str(payload.get("stage_id") or "stage")
    path = ledger_path(repo=repo_path, branch=branch if isinstance(branch, str) else None, stage_id=stage_id, root=root)
    path.parent.mkdir(parents=True, exist_ok=True)
    extra_paths = (str(repo_path.resolve(strict=False)), str(repo_path))
    redacted = redact(copy.deepcopy(payload), extra_paths=extra_paths)
    tmp = path.with_name(path.name + ".tmp")
    with tmp.open("w", encoding="utf-8") as handle:
        json.dump(redacted, handle, ensure_ascii=False, sort_keys=True, indent=2)
        handle.write("\n")
        handle.flush()
        os.fsync(handle.fileno())
    os.replace(tmp, path)
    _fsync_dir(path.parent)
    return path


def read_ledger(path: Path) -> dict[str, Any]:
    with path.open("r", encoding="utf-8") as handle:
        payload = json.load(handle)
    if not isinstance(payload, dict) or payload.get("schema_version") != SCHEMA_VERSION:
        raise LedgerSchemaUnsupported("ledger_schema_unsupported")
    return payload


def new_ledger(
    *,
    repo: Path,
    stage_id: str,
    branch: str | None,
    head_sha: str | None,
    authorization: dict[str, Any] | None = None,
    scope: dict[str, Any] | None = None,
    dirty_baseline: dict[str, Any] | None = None,
) -> dict[str, Any]:
    auth = {
        "standing_authorization": False,
        "may_write_files": False,
        "may_run_codex_impl": False,
        "may_run_codex_review": True,
        "may_commit": False,
        "may_push": False,
        "may_deploy_or_restart": False,
    }
    if authorization:
        auth.update(authorization)
    scope_payload = {
        "allowed_files": [],
        "allowed_globs": [],
        "excluded_dirty_paths": [],
        "risk_classes": [],
    }
    if scope:
        scope_payload.update(scope)
    dirty_payload = {
        "dirty_state_id": None,
        "paths": [],
        "classes": [],
        "blocking_reasons": [],
        "resume_strategy": "clean_current",
    }
    if dirty_baseline:
        dirty_payload.update(dirty_baseline)
    now = _datetime.datetime.now(_datetime.UTC).isoformat().replace("+00:00", "Z")
    ledger_id = hashlib.sha256(
        json.dumps([repo_id(repo), branch, head_sha, stage_id, now], sort_keys=True).encode("utf-8")
    ).hexdigest()[:24]
    return {
        "schema_version": SCHEMA_VERSION,
        "ledger_id": ledger_id,
        "stage_id": stage_id,
        "status": "running",
        "active_pid": os.getpid(),
        "repo": {
            "path": str(repo.resolve(strict=False)),
            "path_redacted": str(repo.resolve(strict=False)),
            "head_sha": head_sha,
            "branch": branch,
            "upstream": None,
        },
        "authorization": auth,
        "scope": scope_payload,
        "dirty_baseline": dirty_payload,
        "events": [],
        "review": {"verdict": "not_run", "must_fix_count": 0},
        "verification": {"matrix_id": None, "commands": [], "results": [], "skipped": []},
        "next_stage": {"recommendation": None, "authorization_required": True},
    }


def _pid_alive(pid: Any) -> bool:
    if not isinstance(pid, int) or pid <= 0:
        return False
    try:
        os.kill(pid, 0)
    except ProcessLookupError:
        return False
    except PermissionError:
        return True
    except OSError:
        return False
    except RuntimeError:
        # Test/runtime guards may block probing unrelated live-system PIDs.
        # Treat unprobeable external PIDs as not alive for resume recovery.
        return False
    return True


def _lock_path(*, repo: Path, branch: str | None, stage_id: str, root: Path | None = None) -> Path:
    return ledger_path(repo=repo, branch=branch, stage_id=stage_id, root=root).with_suffix(".lock")


def acquire_lock(*, repo: Path, branch: str | None, stage_id: str, pid: int | None = None, root: Path | None = None) -> dict[str, Any]:
    path = _lock_path(repo=repo, branch=branch, stage_id=stage_id, root=root)
    path.parent.mkdir(parents=True, exist_ok=True)
    lock_pid = pid or os.getpid()
    lock_token = uuid.uuid4().hex
    payload = {
        "pid": lock_pid,
        "repo_id": repo_id(repo),
        "branch": branch,
        "stage_id": stage_id,
        "token": lock_token,
    }
    try:
        fd = os.open(str(path), os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
    except FileExistsError:
        try:
            existing = json.loads(path.read_text(encoding="utf-8"))
        except Exception:
            existing = {}
        existing_pid = existing.get("pid")
        if _pid_alive(existing_pid):
            return {"acquired": False, "reason": "active_elsewhere", "path": str(path), "pid": existing_pid}
        try:
            path.unlink()
        except OSError:
            return {"acquired": False, "reason": "lock_unavailable", "path": str(path)}
        return acquire_lock(repo=repo, branch=branch, stage_id=stage_id, pid=lock_pid, root=root)
    with os.fdopen(fd, "w", encoding="utf-8") as handle:
        json.dump(payload, handle, sort_keys=True)
        handle.write("\n")
        handle.flush()
        os.fsync(handle.fileno())
    _fsync_dir(path.parent)
    return {"acquired": True, "path": str(path), "pid": lock_pid, "token": lock_token, "repo_id": repo_id(repo), "branch": branch, "stage_id": stage_id}


def release_lock(lock: dict[str, Any]) -> None:
    path = lock.get("path") if isinstance(lock, dict) else None
    if not isinstance(path, str):
        return
    lock_path = Path(path)
    try:
        current = json.loads(lock_path.read_text(encoding="utf-8"))
    except FileNotFoundError:
        return
    except Exception:
        return
    if not isinstance(current, dict):
        return
    for key in ("pid", "repo_id", "branch", "stage_id", "token"):
        if current.get(key) != lock.get(key):
            return
    try:
        lock_path.unlink()
    except FileNotFoundError:
        return


def resume_status(
    *,
    repo: Path,
    branch: str | None,
    stage_id: str,
    current_head_sha: str | None,
    current_dirty_paths: list[str],
    root: Path | None = None,
) -> dict[str, Any]:
    lock_path = _lock_path(repo=repo, branch=branch, stage_id=stage_id, root=root)
    if lock_path.exists():
        try:
            lock_payload = json.loads(lock_path.read_text(encoding="utf-8"))
        except Exception:
            lock_payload = {}
        if _pid_alive(lock_payload.get("pid")):
            return {"resume_status": "active_elsewhere", "reason": "active_elsewhere", "pid": lock_payload.get("pid")}

    path = ledger_path(repo=repo, branch=branch, stage_id=stage_id, root=root)
    if not path.exists():
        return {"resume_status": "not_found", "reason": "ledger_not_found"}
    try:
        payload = read_ledger(path)
    except LedgerSchemaUnsupported:
        return {"resume_status": "blocked", "reason": "ledger_schema_unsupported"}

    repo_info = payload.get("repo") if isinstance(payload.get("repo"), dict) else {}
    previous_head = repo_info.get("head_sha")
    baseline = payload.get("dirty_baseline") if isinstance(payload.get("dirty_baseline"), dict) else {}
    previous_dirty = set(path for path in baseline.get("paths", []) if isinstance(path, str))
    current_dirty = set(path for path in current_dirty_paths if isinstance(path, str))
    if previous_head != current_head_sha:
        overlap = sorted(previous_dirty & current_dirty)
        if overlap:
            return {
                "resume_status": "blocked",
                "reason": "head_changed_with_overlapping_dirty",
                "overlapping_dirty_paths": overlap,
            }
        return {"resume_status": "needs_replan", "reason": "head_changed_without_dirty_overlap"}

    if payload.get("status") == "running" and not _pid_alive(payload.get("active_pid")):
        return {"resume_status": "interrupted_recoverable", "dry_run_only": True}

    return {"resume_status": "ready", "reason": "ledger_ready"}

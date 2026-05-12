"""Persistent runtime for Perplexity Computer-style workflows in Hermes.

Implements the three feature ports requested in the clone plan:

1. **Persistent Computer runtime** — a goal becomes a tracked run record with
   a plan, an event log, an artifact directory, lifecycle status, and a
   structured place for background execution metadata.
2. **Parallel research / browser / workflow orchestration** — the Computer
   prompt (see :func:`build_computer_prompt`) explicitly steers Hermes to use
   ``delegate_task`` in parallel and to lean on browser/web/file/MCP tools
   instead of re-inventing an agent framework.
3. **Continuous monitoring / scheduled runs** — :func:`build_scheduled_computer_prompt`
   produces a fully self-contained prompt that a cron job can fire in a fresh
   session, with traceability back to a stored run.

Storage layout (under ``base_dir``, default ``~/.hermes/computer``)::

    base_dir/
        index.json                # ordered list of run ids (newest first)
        runs/<run_id>/run.json    # persisted run record
        runs/<run_id>/events.jsonl
        runs/<run_id>/artifacts/  # per-run artifact dir written by the agent

All storage operations are best-effort durable: each write goes through a
temp-file + ``os.replace`` to avoid leaving torn files on crash.
"""

from __future__ import annotations

import json
import logging
import os
import secrets
import tempfile
import threading
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional

logger = logging.getLogger(__name__)


# ── Lifecycle statuses ────────────────────────────────────────────────────────
#
# Computer runs follow a small, explicit state machine:
#
#     queued    — created, not yet started (foreground or background)
#     running   — background execution underway
#     scheduled — backed by a cron job firing on a schedule
#     completed — background execution finished successfully
#     failed    — background execution exited non-zero / raised
#     cancelled — user cancelled via the tool

VALID_STATUSES = frozenset({
    "queued", "running", "scheduled", "completed", "failed", "cancelled",
})

_DEFAULT_FEATURES = (
    "runtime",
    "parallel_research",
    "continuous_monitoring",
)


def _utcnow_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def _atomic_write(path: Path, data: str) -> None:
    """Write ``data`` to ``path`` atomically (temp file + ``os.replace``)."""
    path.parent.mkdir(parents=True, exist_ok=True)
    fd, tmp_path = tempfile.mkstemp(
        dir=str(path.parent), prefix=f".{path.name}.", suffix=".tmp"
    )
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as fh:
            fh.write(data)
            fh.flush()
            os.fsync(fh.fileno())
        os.replace(tmp_path, path)
    except BaseException:
        try:
            os.unlink(tmp_path)
        except OSError:
            pass
        raise


def _resolve_base_dir(base_dir: Optional[Path]) -> Path:
    if base_dir is not None:
        return Path(base_dir)
    # Lazy import so the module is importable in tests without HERMES_HOME.
    from hermes_constants import get_hermes_home

    return get_hermes_home() / "computer"


class ComputerStore:
    """JSON-backed store for Computer runs and their event logs.

    The store is process-safe (uses an in-process lock + atomic file
    replacement) and is intentionally simple — no database, no migrations,
    so tests can spin up an isolated store with ``base_dir=tmp_path``.
    """

    def __init__(self, base_dir: Optional[Path] = None):
        self.base_dir = _resolve_base_dir(base_dir)
        self.runs_dir = self.base_dir / "runs"
        self.index_path = self.base_dir / "index.json"
        # Serialize index reads/writes so concurrent create_run / update_run
        # calls don't clobber each other.
        self._lock = threading.RLock()
        self._ensure_dirs()

    # ── filesystem helpers ────────────────────────────────────────────────

    def _ensure_dirs(self) -> None:
        self.base_dir.mkdir(parents=True, exist_ok=True)
        self.runs_dir.mkdir(parents=True, exist_ok=True)

    def _run_dir(self, run_id: str) -> Path:
        return self.runs_dir / run_id

    def _run_path(self, run_id: str) -> Path:
        return self._run_dir(run_id) / "run.json"

    def _events_path(self, run_id: str) -> Path:
        return self._run_dir(run_id) / "events.jsonl"

    def _artifact_dir(self, run_id: str) -> Path:
        # The artifact dir IS the run dir — keeping them merged makes
        # ``Path(run["artifact_dir"]).name == run["id"]`` true and means
        # ``run.json`` / ``events.jsonl`` / agent-written artifacts all live
        # in one tidy location named after the run id.
        return self._run_dir(run_id)

    # ── index ────────────────────────────────────────────────────────────

    def _load_index(self) -> List[str]:
        if not self.index_path.exists():
            return []
        try:
            with self.index_path.open("r", encoding="utf-8") as fh:
                data = json.load(fh)
            if isinstance(data, list):
                return [str(x) for x in data]
            if isinstance(data, dict) and isinstance(data.get("runs"), list):
                return [str(x) for x in data["runs"]]
        except (OSError, json.JSONDecodeError) as exc:
            logger.warning("ComputerStore index unreadable, resetting: %s", exc)
        return []

    def _save_index(self, run_ids: List[str]) -> None:
        _atomic_write(self.index_path, json.dumps({"runs": run_ids}, indent=2))

    def _add_to_index(self, run_id: str) -> None:
        with self._lock:
            ids = self._load_index()
            if run_id in ids:
                return
            ids.insert(0, run_id)  # newest first
            self._save_index(ids)

    # ── public API ───────────────────────────────────────────────────────

    def create_run(
        self,
        goal: str,
        features: Optional[List[str]] = None,
        source: Optional[str] = None,
        plan: Optional[Dict[str, Any]] = None,
        deliver: Optional[str] = None,
        metadata: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        """Create and persist a new Computer run.

        Returns the freshly created run dict.  An initial
        ``computer.run.created`` event is appended so reloading the events
        log always shows the lifecycle from the very first moment.
        """
        if not goal or not str(goal).strip():
            raise ValueError("goal must be a non-empty string")

        feature_list = list(features) if features else list(_DEFAULT_FEATURES)
        # Use a short hex suffix — readable in logs and CLI but collision-safe.
        run_id = f"computer_{secrets.token_hex(6)}"
        artifact_dir = self._artifact_dir(run_id)
        artifact_dir.mkdir(parents=True, exist_ok=True)

        now = _utcnow_iso()
        run = {
            "id": run_id,
            "goal": str(goal).strip(),
            "features": feature_list,
            "status": "queued",
            "source": source,
            "deliver": deliver,
            "plan": plan,
            "metadata": metadata or {},
            "artifact_dir": str(artifact_dir),
            "created_at": now,
            "updated_at": now,
            "started_at": None,
            "completed_at": None,
            "schedule": None,
            "schedule_job_id": None,
            "background": None,
            "error": None,
            "output": None,
        }

        with self._lock:
            _atomic_write(self._run_path(run_id), json.dumps(run, indent=2))
            self._add_to_index(run_id)
            self._append_event_unlocked(
                run_id,
                "computer.run.created",
                {"goal": run["goal"], "features": feature_list},
                at=now,
            )

        return dict(run)

    def update_run(self, run_id: str, **fields: Any) -> Dict[str, Any]:
        """Update fields on a run and log a ``computer.run.updated`` event.

        Unknown fields are stored as-is so callers can stash extra metadata
        (background pid, exit code, scheduled job id, etc.) without a schema
        migration.  Status values outside :data:`VALID_STATUSES` raise.
        """
        with self._lock:
            run = self._load_run_unlocked(run_id)
            if run is None:
                raise KeyError(f"unknown computer run: {run_id}")

            status = fields.get("status")
            if status is not None and status not in VALID_STATUSES:
                raise ValueError(
                    f"invalid computer run status: {status!r} "
                    f"(expected one of {sorted(VALID_STATUSES)})"
                )

            now = _utcnow_iso()
            for key, value in fields.items():
                run[key] = value
            run["updated_at"] = now
            if status == "running" and not run.get("started_at"):
                run["started_at"] = now
            if status in {"completed", "failed", "cancelled"} and not run.get("completed_at"):
                run["completed_at"] = now

            _atomic_write(self._run_path(run_id), json.dumps(run, indent=2))
            self._append_event_unlocked(
                run_id,
                "computer.run.updated",
                {"changes": {k: fields[k] for k in fields}},
                at=now,
            )
            return dict(run)

    def get_run(self, run_id: str) -> Optional[Dict[str, Any]]:
        with self._lock:
            return self._load_run_unlocked(run_id)

    def list_runs(self) -> List[Dict[str, Any]]:
        """Return all runs newest-first.

        Runs whose ``run.json`` is missing are silently skipped — they can
        happen if an artifact dir was nuked manually.
        """
        with self._lock:
            ids = self._load_index()
        runs: List[Dict[str, Any]] = []
        for rid in ids:
            run = self.get_run(rid)
            if run:
                runs.append(run)
        return runs

    def append_event(self, run_id: str, event_type: str, payload: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        with self._lock:
            return self._append_event_unlocked(run_id, event_type, payload or {})

    def list_events(self, run_id: str) -> List[Dict[str, Any]]:
        events_path = self._events_path(run_id)
        if not events_path.exists():
            return []
        out: List[Dict[str, Any]] = []
        try:
            with events_path.open("r", encoding="utf-8") as fh:
                for line in fh:
                    line = line.strip()
                    if not line:
                        continue
                    try:
                        out.append(json.loads(line))
                    except json.JSONDecodeError:
                        logger.warning(
                            "skipping malformed event line in %s", events_path
                        )
        except OSError as exc:
            logger.warning("could not read events for %s: %s", run_id, exc)
        return out

    # ── internal helpers ─────────────────────────────────────────────────

    def _load_run_unlocked(self, run_id: str) -> Optional[Dict[str, Any]]:
        path = self._run_path(run_id)
        if not path.exists():
            return None
        try:
            with path.open("r", encoding="utf-8") as fh:
                data = json.load(fh)
            if not isinstance(data, dict):
                return None
            return data
        except (OSError, json.JSONDecodeError) as exc:
            logger.warning("could not load run %s: %s", run_id, exc)
            return None

    def _append_event_unlocked(
        self,
        run_id: str,
        event_type: str,
        payload: Dict[str, Any],
        *,
        at: Optional[str] = None,
    ) -> Dict[str, Any]:
        run_dir = self._run_dir(run_id)
        run_dir.mkdir(parents=True, exist_ok=True)
        event = {
            "type": str(event_type),
            "at": at or _utcnow_iso(),
            "payload": payload,
        }
        events_path = self._events_path(run_id)
        # JSONL append — durable enough for an event log; we don't fsync per
        # line because event-log loss on crash is acceptable (run.json is
        # the source of truth for resumability).
        with events_path.open("a", encoding="utf-8") as fh:
            fh.write(json.dumps(event, ensure_ascii=False) + "\n")
        return event


# ── Prompt construction ───────────────────────────────────────────────────────


_FEATURE_LABELS = {
    "runtime": (
        "First-class persistent Computer runtime — write the plan, intermediate "
        "notes, and final deliverables into the run artifact directory."
    ),
    "parallel_research": (
        "Parallel research / browser / workflow orchestration — fan out using "
        "delegate_task in parallel for independent research threads and only "
        "then synthesize."
    ),
    "continuous_monitoring": (
        "Continuous monitoring — when the goal implies recurring work, schedule "
        "a cron job via the cronjob tool. Otherwise, treat this run as one-shot."
    ),
}


def _format_feature_block(features: List[str]) -> str:
    lines = []
    for feat in features:
        label = _FEATURE_LABELS.get(feat, f"Feature: {feat}")
        lines.append(f"- [{feat}] {label}")
    return "\n".join(lines) if lines else "- (no specific feature ports requested)"


def build_computer_prompt(run: Dict[str, Any]) -> str:
    """Build the system/user prompt that drives a Computer run.

    The prompt explicitly instructs Hermes to act as a Perplexity
    Computer-style workflow orchestrator and to use existing Hermes
    primitives (delegate_task, browser, web, files, MCP).  Tests assert on
    several specific phrases; treat those phrases as part of the contract.
    """
    features = list(run.get("features") or [])
    artifact_dir = run.get("artifact_dir") or ""
    deliver = run.get("deliver") or "the originating conversation"

    return f"""You are operating as a Perplexity Computer-style workflow orchestrator inside Hermes.
This is a persistent Computer run; everything you produce is tied to a tracked run record.

Run id: {run.get("id", "<unknown>")}
Goal: {run.get("goal", "<no goal>")}
Artifact directory (write deliverables here): {artifact_dir}
Delivery target: {deliver}

Active feature ports:
{_format_feature_block(features)}

Operating rules:
1. Treat this as a Perplexity Computer-style task: plan first, then execute,
   then synthesize a clear deliverable. Maintain a short written plan inside
   the artifact directory ("{artifact_dir}/plan.md") and update it as you go.
2. Use Hermes primitives — do not invent a second agent framework. Prefer:
     - delegate_task for parallel research sub-tasks (run independent
       branches in parallel, then synthesize in the parent).
     - browser_* tools for live web navigation when search/extract is not
       enough.
     - web_search / web_extract for fast research.
     - read_file / write_file / patch / search_files for local-file work.
     - cronjob for continuous monitoring when the goal is recurring.
     - MCP / connector tools when available for first-party integrations.
3. Write every deliverable (briefings, summaries, csv/json/markdown
   artifacts) into the run artifact directory above so the user can find
   them later. Reference artifact paths in your final reply.
4. Respect approvals and user-control boundaries. Do not bypass the normal
   approval flow, do not silently send messages outside configured
   delivery, and do not exfiltrate secrets.
5. If the goal includes continuous monitoring, schedule it via the cronjob
   tool with a self-contained prompt rather than looping forever in this
   run. The cron run will spawn a fresh Computer run on each tick.
6. End with a short, structured summary: what you did, key findings, and
   the absolute paths of the artifacts you wrote.
"""


def build_scheduled_computer_prompt(run: Dict[str, Any]) -> str:
    """Build a self-contained prompt for a *scheduled* Computer run.

    This is what the cron scheduler stores as the job ``prompt``.  Each
    tick fires it in a fresh session, so the prompt must carry all the
    context the agent needs and must explicitly forbid recursive cron
    creation.
    """
    base = build_computer_prompt(run)
    deliver = run.get("deliver") or "the originating conversation"

    return f"""This is a scheduled Perplexity Computer-style run firing in a fresh session.

Originating Computer run id: {run.get("id", "<unknown>")}
Continuous monitoring tick goal: {run.get("goal", "<no goal>")}
Deliver the resulting briefing to: {deliver}

Do not recursively create cron jobs. Run the goal once for this tick, write
artifacts into the originating run's artifact directory below, and rely on
the existing cron schedule for future ticks.

--- Computer operating instructions (same as the parent run) ---
{base}
"""


# ── Background execution helper ───────────────────────────────────────────────


def start_computer_run(
    run_id: str,
    *,
    store: Optional[ComputerStore] = None,
    hermes_executable: Optional[str] = None,
) -> bool:
    """Launch a background Hermes session that executes a Computer run.

    Best-effort: returns True if a background process was launched and
    metadata recorded, False otherwise.  Tests monkey-patch this so the
    real launch never runs in CI — keep the signature stable.

    The implementation deliberately uses ``subprocess.Popen`` to fire off
    ``hermes chat -q <self-contained prompt>`` instead of re-inventing a
    second agent framework. The subprocess inherits the user's normal
    approval/delivery configuration, so security boundaries are preserved.
    """
    import shutil
    import subprocess

    target_store = store if store is not None else ComputerStore()
    run = target_store.get_run(run_id)
    if run is None:
        logger.warning("start_computer_run: unknown run %s", run_id)
        return False

    if run.get("status") in {"running", "completed", "cancelled"}:
        # Already in a terminal/active state — refuse to relaunch.
        return False

    prompt = build_computer_prompt(run)
    binary = hermes_executable or shutil.which("hermes")
    if not binary:
        target_store.update_run(
            run_id,
            status="failed",
            error="hermes executable not on PATH; cannot launch background run",
        )
        return False

    artifact_dir = Path(run.get("artifact_dir") or target_store._artifact_dir(run_id))
    artifact_dir.mkdir(parents=True, exist_ok=True)
    stdout_path = artifact_dir / "background.stdout.log"
    stderr_path = artifact_dir / "background.stderr.log"

    try:
        # Open the log files now and hand them to the child. We do NOT call
        # ``shell=True`` — the prompt is passed as a single argv element so
        # quoting/escaping cannot collapse into shell metacharacters.
        stdout_fh = open(stdout_path, "ab", buffering=0)
        stderr_fh = open(stderr_path, "ab", buffering=0)
        proc = subprocess.Popen(  # noqa: S603 — explicit argv, no shell
            [binary, "chat", "-q", prompt],
            stdout=stdout_fh,
            stderr=stderr_fh,
            stdin=subprocess.DEVNULL,
            start_new_session=True,
        )
    except Exception as exc:  # pragma: no cover — defensive
        target_store.update_run(
            run_id,
            status="failed",
            error=f"failed to launch background run: {exc!r}",
        )
        return False

    target_store.update_run(
        run_id,
        status="running",
        background={
            "pid": proc.pid,
            "binary": binary,
            "stdout_log": str(stdout_path),
            "stderr_log": str(stderr_path),
        },
    )
    target_store.append_event(
        run_id,
        "computer.background.launched",
        {"pid": proc.pid, "binary": binary},
    )
    return True


__all__ = [
    "VALID_STATUSES",
    "ComputerStore",
    "build_computer_prompt",
    "build_scheduled_computer_prompt",
    "start_computer_run",
]

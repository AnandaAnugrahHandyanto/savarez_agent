"""Sentry Issue Alert webhook receiver — Vedere ecosystem standardization.

Receives Sentry Issue Alert webhook payloads, deduplicates by fingerprint
against a SQLite cache, maps environment to a target GitHub repository, and
creates a GitHub issue via ``gh issue create`` with a hybrid Markdown +
JSON-payload body matching ``Vhailors/vedere-shared@main:golden/payload-schema.ts``.

Free-tier Sentry does NOT sign webhook payloads. Authentication is via the
``SENTRY_WEBHOOK_TOKEN`` env var presented as a ``?token=`` query parameter
and compared with :func:`secrets.compare_digest`.

The same :class:`FingerprintCache` is shared between the FastAPI handler
thread and the 6h backfill cron (G5 unification) — ``check_same_thread=False``
on the underlying sqlite3 connection so concurrent calls are safe under the
short critical sections used here.
"""

from __future__ import annotations

import json
import logging
import os
import secrets
import sqlite3
import subprocess
import threading
import time
from pathlib import Path
from typing import Any, Dict, List, Optional

from fastapi import APIRouter, FastAPI, HTTPException, Query, Request
from pydantic import BaseModel, Field, ValidationError

_log = logging.getLogger(__name__)

router = APIRouter(prefix="/api/sentry", tags=["sentry"])


# ---------------------------------------------------------------------------
# Environment → target repo mapping. Static rather than configurable —
# adding a new Vedere project should be an explicit code change reviewed
# in PR rather than a runtime env-var surprise.
# ---------------------------------------------------------------------------
ENV_REPO_MAP: Dict[str, str] = {
    "lms-prod": "manlaughed/VedereLMS",
    "lms-staging": "manlaughed/VedereLMS",
    "lms-dev": "manlaughed/VedereLMS",
    "aireader-prod": "Vhailors/AIReader",
    "aireader-staging": "Vhailors/AIReader",
    "aireader-dev": "Vhailors/AIReader",
    "university-prod": "Vhailors/VedereUniversity",
    "university-staging": "Vhailors/VedereUniversity",
    "university-dev": "Vhailors/VedereUniversity",
}


# Recurrence-vs-regression thresholds (seconds).
_RECURRENCE_HORIZON_S = 30 * 24 * 60 * 60   # 30 days — within = "recurring"
_REGRESSION_HORIZON_S = 7 * 24 * 60 * 60    # 7 days — older AND closed = regression


# ---------------------------------------------------------------------------
# Pydantic payload model — matches the Sentry Issue Alert webhook shape
# documented at https://docs.sentry.io/product/integrations/integration-platform/webhooks/issue-alerts/
# We only require the fields we actually consume; unknown fields pass through.
# ---------------------------------------------------------------------------
class SentryEventException(BaseModel):
    values: Optional[List[Dict[str, Any]]] = None


class SentryEvent(BaseModel):
    fingerprint: List[str] = Field(..., min_length=1)
    level: Optional[str] = "error"
    environment: str
    exception: Optional[SentryEventException] = None
    message: Optional[str] = None
    title: Optional[str] = None
    web_url: Optional[str] = None
    project_slug: Optional[str] = None


class SentryIssueAlertData(BaseModel):
    event: SentryEvent
    issue_url: Optional[str] = None
    triggered_rule: Optional[str] = None


class SentryIssueAlertPayload(BaseModel):
    action: str
    data: SentryIssueAlertData
    installation: Optional[Dict[str, Any]] = None
    actor: Optional[Dict[str, Any]] = None


# ---------------------------------------------------------------------------
# SQLite-backed fingerprint cache. Shared by the FastAPI handler thread and
# the backfill cron via the SAME on-disk file. We open with
# ``check_same_thread=False`` and serialize writes through a process-local
# lock — sqlite3 itself handles cross-process locking via the file.
# ---------------------------------------------------------------------------
class FingerprintCache:
    """Tracks fingerprint→issue-state mappings for dedup + regression detection.

    Schema::
        CREATE TABLE fingerprints (
            fingerprint        TEXT,
            environment        TEXT,
            last_seen          INTEGER,
            github_issue_url   TEXT,
            github_issue_state TEXT,
            PRIMARY KEY(fingerprint, environment)
        )

    All methods are safe to call from any thread.
    """

    DEFAULT_PATH = Path.home() / ".hermes" / "sentry-fingerprints.db"

    def __init__(self, db_path: Optional[Path] = None) -> None:
        path = Path(db_path) if db_path is not None else self.DEFAULT_PATH
        path.parent.mkdir(parents=True, exist_ok=True)
        self._path = path
        self._lock = threading.Lock()
        # check_same_thread=False so the cache instance is shareable across
        # the FastAPI worker thread and any background-loop tasks (G5).
        self._conn = sqlite3.connect(
            str(path),
            check_same_thread=False,
            isolation_level=None,  # autocommit; we wrap atomic ops in `BEGIN` ourselves
            timeout=5.0,
        )
        self._conn.execute("PRAGMA journal_mode=WAL")
        self._conn.execute(
            """
            CREATE TABLE IF NOT EXISTS fingerprints (
                fingerprint        TEXT NOT NULL,
                environment        TEXT NOT NULL,
                last_seen          INTEGER NOT NULL,
                github_issue_url   TEXT,
                github_issue_state TEXT,
                PRIMARY KEY (fingerprint, environment)
            )
            """
        )

    @property
    def path(self) -> Path:
        return self._path

    def _row(self, fingerprint: str, env: str) -> Optional[sqlite3.Row]:
        cur = self._conn.execute(
            "SELECT fingerprint, environment, last_seen, github_issue_url, github_issue_state "
            "FROM fingerprints WHERE fingerprint = ? AND environment = ?",
            (fingerprint, env),
        )
        return cur.fetchone()

    def is_new(self, fingerprint: str, env: str, *, now: Optional[int] = None) -> bool:
        """True when no row exists OR the cached row is older than 30 days."""
        with self._lock:
            row = self._row(fingerprint, env)
        if row is None:
            return True
        now_s = int(now if now is not None else time.time())
        return (now_s - int(row[2])) >= _RECURRENCE_HORIZON_S

    def is_regression(self, fingerprint: str, env: str, *, now: Optional[int] = None) -> bool:
        """True when last_seen is older than 7 days AND state was 'closed'."""
        with self._lock:
            row = self._row(fingerprint, env)
        if row is None:
            return False
        now_s = int(now if now is not None else time.time())
        age = now_s - int(row[2])
        state = (row[4] or "").lower()
        return age >= _REGRESSION_HORIZON_S and state == "closed"

    def record(
        self,
        fingerprint: str,
        env: str,
        issue_url: Optional[str],
        issue_state: Optional[str],
        *,
        now: Optional[int] = None,
    ) -> None:
        """Insert or replace the row for ``(fingerprint, env)`` with current time."""
        now_s = int(now if now is not None else time.time())
        with self._lock:
            self._conn.execute(
                """
                INSERT INTO fingerprints
                    (fingerprint, environment, last_seen, github_issue_url, github_issue_state)
                VALUES (?, ?, ?, ?, ?)
                ON CONFLICT(fingerprint, environment) DO UPDATE SET
                    last_seen = excluded.last_seen,
                    github_issue_url = excluded.github_issue_url,
                    github_issue_state = excluded.github_issue_state
                """,
                (fingerprint, env, now_s, issue_url, issue_state),
            )

    def close(self) -> None:
        with self._lock:
            try:
                self._conn.close()
            except Exception:  # pragma: no cover — defensive
                pass


# Module-level singleton — handler and backfill share this. Tests override
# via :func:`set_cache`.
_cache_singleton: Optional[FingerprintCache] = None
_cache_singleton_lock = threading.Lock()


def get_cache() -> FingerprintCache:
    global _cache_singleton
    with _cache_singleton_lock:
        if _cache_singleton is None:
            _cache_singleton = FingerprintCache()
        return _cache_singleton


def set_cache(cache: FingerprintCache) -> None:
    """Test hook — swap the module-level cache for an isolated instance."""
    global _cache_singleton
    with _cache_singleton_lock:
        _cache_singleton = cache


# ---------------------------------------------------------------------------
# Issue-body builder — hybrid Markdown + machine-readable JSON block.
# Schema lives in Vhailors/vedere-shared@main:golden/payload-schema.ts; the
# JSON block here MUST stay byte-aligned with that golden file.
# ---------------------------------------------------------------------------
def _short_fingerprint(fp: str) -> str:
    fp = fp.strip()
    if len(fp) <= 12:
        return fp
    return fp[:12]


def _summarize_exception(event: SentryEvent) -> str:
    if event.title:
        return event.title
    if event.message:
        return event.message
    if event.exception and event.exception.values:
        first = event.exception.values[0]
        type_ = first.get("type") or "Exception"
        value = first.get("value") or ""
        return f"{type_}: {value}".strip(": ")
    return "Sentry event"


def build_issue_body(payload: SentryIssueAlertPayload, *, regression: bool) -> str:
    event = payload.data.event
    fingerprint = event.fingerprint[0]
    machine_payload = {
        "schema": "vedere-shared/payload-schema@1",
        "source": "sentry-webhook",
        "fingerprint": fingerprint,
        "environment": event.environment,
        "level": event.level,
        "title": _summarize_exception(event),
        "sentry_issue_url": payload.data.issue_url,
        "sentry_event_url": event.web_url,
        "project_slug": event.project_slug,
        "regression": regression,
        "received_at": int(time.time()),
    }
    md_lines = [
        f"## Sentry alert ({'regression' if regression else 'new'})",
        "",
        f"- **Fingerprint:** `{fingerprint}`",
        f"- **Environment:** `{event.environment}`",
        f"- **Level:** `{event.level or 'error'}`",
        f"- **Title:** {_summarize_exception(event)}",
    ]
    if payload.data.issue_url:
        md_lines.append(f"- **Sentry issue:** {payload.data.issue_url}")
    if event.web_url:
        md_lines.append(f"- **Event URL:** {event.web_url}")
    if regression:
        md_lines.append("")
        md_lines.append(
            "> Regression detected — this fingerprint was previously closed "
            "more than 7 days ago."
        )
    md_lines.append("")
    md_lines.append("<!-- hermes-payload -->")
    md_lines.append("```json")
    md_lines.append(json.dumps(machine_payload, indent=2, sort_keys=True))
    md_lines.append("```")
    return "\n".join(md_lines)


# ---------------------------------------------------------------------------
# GitHub issue creation via `gh` CLI. Subprocess-based so we inherit the
# operator's existing gh auth — no token plumbing needed.
# ---------------------------------------------------------------------------
class GhCliError(RuntimeError):
    pass


def _run_gh_issue_create(repo: str, title: str, body: str, labels: List[str]) -> str:
    """Invoke ``gh issue create`` and return the resulting issue URL.

    Raises :class:`GhCliError` if the CLI exits non-zero or returns no URL.
    """
    cmd = [
        "gh", "issue", "create",
        "--repo", repo,
        "--title", title,
        "--body", body,
    ]
    for label in labels:
        cmd.extend(["--label", label])
    try:
        result = subprocess.run(
            cmd,
            check=False,
            capture_output=True,
            text=True,
            timeout=30,
        )
    except FileNotFoundError as exc:  # pragma: no cover — host without gh
        raise GhCliError("gh CLI not installed") from exc
    except subprocess.TimeoutExpired as exc:
        raise GhCliError("gh issue create timed out") from exc
    if result.returncode != 0:
        raise GhCliError(
            f"gh issue create failed (rc={result.returncode}): {result.stderr.strip() or result.stdout.strip()}"
        )
    # gh prints the issue URL as the last non-empty line on success.
    out_lines = [ln.strip() for ln in (result.stdout or "").splitlines() if ln.strip()]
    if not out_lines:
        raise GhCliError("gh issue create produced no output")
    url = out_lines[-1]
    if not url.startswith("http"):
        raise GhCliError(f"gh issue create did not return a URL: {url!r}")
    return url


# ---------------------------------------------------------------------------
# FastAPI endpoint
# ---------------------------------------------------------------------------
def _verify_token(token: Optional[str]) -> None:
    expected = os.environ.get("SENTRY_WEBHOOK_TOKEN", "")
    presented = token or ""
    # compare_digest requires equal-length strings to be safe; both inputs
    # are str here, so it short-circuits length-mismatch in constant time.
    if not expected or not secrets.compare_digest(presented, expected):
        raise HTTPException(status_code=401, detail="Unauthorized")


@router.post("/webhook")
async def sentry_webhook(
    request: Request,
    token: Optional[str] = Query(default=None),
) -> Dict[str, Any]:
    """Receive a Sentry Issue Alert payload and create/skip a GitHub issue."""
    _verify_token(token)

    raw_body = await request.body()
    try:
        body_json = json.loads(raw_body or b"{}")
    except json.JSONDecodeError as exc:
        raise HTTPException(status_code=400, detail=f"invalid JSON: {exc}")

    try:
        payload = SentryIssueAlertPayload.model_validate(body_json)
    except ValidationError as exc:
        # Pydantic returns 422-shaped detail by default; we surface the message.
        raise HTTPException(status_code=422, detail=exc.errors())

    event = payload.data.event
    env = event.environment
    fingerprint = event.fingerprint[0]

    repo = ENV_REPO_MAP.get(env)
    if repo is None:
        raise HTTPException(
            status_code=400,
            detail=f"unknown environment: {env!r} — add to ENV_REPO_MAP if it is a Vedere project",
        )

    cache = get_cache()
    is_new = cache.is_new(fingerprint, env)
    is_regression = cache.is_regression(fingerprint, env)

    if not is_new and not is_regression:
        _log.info("sentry-webhook: skipping recurring fingerprint=%s env=%s", fingerprint, env)
        return {
            "action": "skipped",
            "reason": "recurring",
            "fingerprint": fingerprint,
            "environment": env,
        }

    title = f"[Sentry] {_summarize_exception(event)} ({_short_fingerprint(fingerprint)})"
    body = build_issue_body(payload, regression=is_regression)
    labels = ["sentry-bug", "hermes-pending"]
    if is_regression:
        labels.append("regression")

    issue_url = _run_gh_issue_create(repo=repo, title=title, body=body, labels=labels)

    cache.record(fingerprint, env, issue_url=issue_url, issue_state="open")

    return {
        "action": "created",
        "github_issue_url": issue_url,
        "fingerprint": fingerprint,
        "environment": env,
        "repo": repo,
        "regression": is_regression,
    }


def register_sentry_webhook(app: FastAPI) -> None:
    """Mount the Sentry webhook router on the given FastAPI app.

    The dashboard's ``auth_middleware`` gates all ``/api/*`` paths behind
    the ephemeral session token. The Sentry webhook has its own
    secret-token query-param auth (``?token=...`` checked with
    :func:`secrets.compare_digest` against ``SENTRY_WEBHOOK_TOKEN``), so
    we extend the dashboard's public-paths frozenset to let our router
    handle authentication itself.
    """
    app.include_router(router)
    try:
        from . import web_server  # local import to avoid cycle at module-load time
    except Exception:  # pragma: no cover — register_sentry_webhook can be called against alternate apps
        return
    public = getattr(web_server, "_PUBLIC_API_PATHS", None)
    if isinstance(public, frozenset):
        web_server._PUBLIC_API_PATHS = frozenset(public | {"/api/sentry/webhook"})

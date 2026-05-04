"""Sentry 6h backfill cron — Vedere ecosystem standardization.

Queries the Sentry events API for the last 6h+1h margin (level >= error)
and replays each unique fingerprint through the Hermes Sentry webhook
endpoint. Re-using the live HTTP path means the SAME
:class:`hermes_cli.sentry_webhook.FingerprintCache` is consulted (G5
unification) — no parallel dedup logic to drift out of sync.

Crontab line (deploy via ``crontab -e``)::

    0 */6 * * * /usr/bin/env -i HOME=$HOME bash -lc 'source .venv/bin/activate && python -m cron.sentry_backfill >> ~/.hermes/logs/backfill.log 2>&1'

Env vars consumed:

* ``SENTRY_AUTH_TOKEN`` — Sentry API auth token (required).
* ``SENTRY_ORG_SLUG``   — Sentry organization slug (default: ``vedere``).
* ``SENTRY_PROJECTS``   — comma-separated project slugs to scan (required).
* ``SENTRY_WEBHOOK_TOKEN`` — same secret the receiver verifies (required).
* ``HERMES_WEBHOOK_URL`` — webhook receiver URL
  (default: ``http://localhost:9119/api/sentry/webhook``).
* ``SENTRY_BASE_URL``   — Sentry API base (default: ``https://sentry.io/api/0``).

Exit codes:

* 0 — success (zero or more fingerprints replayed)
* 2 — missing required env vars
* 3 — Sentry API error
"""

from __future__ import annotations

import logging
import os
import sys
import time
from typing import Any, Dict, Iterable, List, Optional, Set, Tuple

import httpx

from hermes_cli.sentry_webhook import FingerprintCache, get_cache

_log = logging.getLogger("cron.sentry_backfill")


_BACKFILL_WINDOW_S = 6 * 60 * 60      # nominal window
_BACKFILL_MARGIN_S = 1 * 60 * 60      # +1h overlap so we don't lose events at the edges
_HTTP_TIMEOUT_S = 30.0


def _require_env(name: str) -> str:
    value = os.environ.get(name)
    if not value:
        _log.error("missing required env var %s", name)
        raise SystemExit(2)
    return value


def _list_projects() -> List[str]:
    raw = _require_env("SENTRY_PROJECTS")
    return [p.strip() for p in raw.split(",") if p.strip()]


def _fetch_recent_events(
    *,
    org: str,
    project: str,
    auth_token: str,
    since_ts: int,
    base_url: str,
    client: httpx.Client,
) -> List[Dict[str, Any]]:
    """Pull recent events for one project. Returns a list of event dicts.

    Uses the public Sentry events endpoint with a ``query=level:error
    age:-7h`` filter. We over-fetch slightly because Sentry's age filter
    is project-time-zone sensitive and we'd rather replay one event twice
    (the receiver dedups) than miss one.
    """
    url = f"{base_url}/projects/{org}/{project}/events/"
    headers = {"Authorization": f"Bearer {auth_token}"}
    params = {
        "query": "level:error",
        "statsPeriod": "7h",  # 6h + 1h margin
        "full": "true",
    }
    response = client.get(url, headers=headers, params=params, timeout=_HTTP_TIMEOUT_S)
    if response.status_code != 200:
        _log.error(
            "Sentry events API returned %d for project=%s body=%s",
            response.status_code,
            project,
            response.text[:300],
        )
        raise SystemExit(3)
    data = response.json()
    if not isinstance(data, list):
        _log.error("Sentry events API returned non-list payload: %r", type(data))
        raise SystemExit(3)
    return [evt for evt in data if isinstance(evt, dict)]


def _event_fingerprint(event: Dict[str, Any]) -> Optional[str]:
    fp = event.get("fingerprint") or event.get("groupID") or event.get("eventID")
    if isinstance(fp, list) and fp:
        return str(fp[0])
    if isinstance(fp, str) and fp:
        return fp
    return None


def _event_environment(event: Dict[str, Any], default: Optional[str] = None) -> Optional[str]:
    env = event.get("environment")
    if isinstance(env, str) and env:
        return env
    return default


def _build_synthetic_payload(event: Dict[str, Any], project: str) -> Dict[str, Any]:
    fp = _event_fingerprint(event) or event.get("eventID") or "unknown"
    env = _event_environment(event) or f"{project}-prod"
    return {
        "action": "triggered",
        "data": {
            "event": {
                "fingerprint": [fp],
                "level": event.get("level") or "error",
                "environment": env,
                "exception": event.get("entries", [{}])[0].get("data") if event.get("entries") else None,
                "message": event.get("message") or event.get("title"),
                "title": event.get("title"),
                "web_url": event.get("permalink") or event.get("eventID"),
                "project_slug": project,
            },
            "issue_url": event.get("groupURL"),
            "triggered_rule": "hermes-backfill-cron",
        },
    }


def _replay_one(
    *,
    payload: Dict[str, Any],
    webhook_url: str,
    webhook_token: str,
    client: httpx.Client,
) -> Tuple[int, str]:
    response = client.post(
        webhook_url,
        params={"token": webhook_token},
        json=payload,
        timeout=_HTTP_TIMEOUT_S,
    )
    return response.status_code, (response.text or "")[:300]


def _configure_logging() -> None:
    level = os.environ.get("SENTRY_BACKFILL_LOG_LEVEL", "INFO").upper()
    logging.basicConfig(
        level=getattr(logging, level, logging.INFO),
        format="%(asctime)s %(levelname)s %(name)s :: %(message)s",
    )


def main(argv: Optional[List[str]] = None) -> int:
    _configure_logging()

    auth_token = _require_env("SENTRY_AUTH_TOKEN")
    webhook_token = _require_env("SENTRY_WEBHOOK_TOKEN")
    projects = _list_projects()

    org = os.environ.get("SENTRY_ORG_SLUG", "vedere")
    base_url = os.environ.get("SENTRY_BASE_URL", "https://sentry.io/api/0").rstrip("/")
    webhook_url = os.environ.get(
        "HERMES_WEBHOOK_URL",
        "http://localhost:9119/api/sentry/webhook",
    )

    since_ts = int(time.time()) - (_BACKFILL_WINDOW_S + _BACKFILL_MARGIN_S)

    # Touch the singleton so the cache file exists on disk before the
    # webhook receiver process is asked to consult it. This is purely a
    # warm-start nicety; the receiver opens its own connection.
    cache: FingerprintCache = get_cache()
    _log.info("sentry-backfill: cache path=%s projects=%s", cache.path, projects)

    new_count = 0
    skipped_count = 0
    error_count = 0

    seen: Set[Tuple[str, str]] = set()

    with httpx.Client() as client:
        for project in projects:
            try:
                events = _fetch_recent_events(
                    org=org,
                    project=project,
                    auth_token=auth_token,
                    since_ts=since_ts,
                    base_url=base_url,
                    client=client,
                )
            except SystemExit:
                raise
            except httpx.HTTPError as exc:
                _log.warning("network error fetching project=%s: %s", project, exc)
                error_count += 1
                continue
            for event in events:
                fp = _event_fingerprint(event)
                env = _event_environment(event, default=f"{project}-prod")
                if not fp or not env:
                    continue
                key = (fp, env)
                if key in seen:
                    continue
                seen.add(key)
                if not cache.is_new(fp, env) and not cache.is_regression(fp, env):
                    skipped_count += 1
                    continue
                payload = _build_synthetic_payload(event, project)
                try:
                    status, text = _replay_one(
                        payload=payload,
                        webhook_url=webhook_url,
                        webhook_token=webhook_token,
                        client=client,
                    )
                except httpx.HTTPError as exc:
                    _log.warning("network error replaying fp=%s env=%s: %s", fp, env, exc)
                    error_count += 1
                    continue
                if status >= 400:
                    _log.warning(
                        "webhook replay returned %d fp=%s env=%s body=%s",
                        status, fp, env, text,
                    )
                    error_count += 1
                else:
                    new_count += 1
                    _log.info("replayed fp=%s env=%s status=%d", fp, env, status)

    _log.info(
        "sentry-backfill: done new=%d skipped=%d errors=%d unique=%d",
        new_count, skipped_count, error_count, len(seen),
    )
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))

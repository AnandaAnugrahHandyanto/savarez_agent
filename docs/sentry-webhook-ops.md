# Sentry Webhook Receiver — Ops Runbook

Vedere ecosystem standardization (Phase 2 Lane A3). The receiver lives at
`POST /api/sentry/webhook` on the existing Hermes FastAPI server
(`hermes_cli/web_server.py`). It deduplicates Sentry Issue Alert webhooks by
fingerprint via a SQLite cache and creates GitHub issues in the appropriate
Vedere repository via the `gh` CLI.

## Environment variables

| Var                     | Required | Purpose                                                                                  |
| ----------------------- | :------: | ---------------------------------------------------------------------------------------- |
| `SENTRY_WEBHOOK_TOKEN`  |   yes    | Shared secret. Sentry presents it as `?token=...`. Compared with `secrets.compare_digest`. |
| `SENTRY_AUTH_TOKEN`     |   yes\*  | Sentry API token used by the 6h backfill cron only.                                      |
| `SENTRY_PROJECTS`       |   yes\*  | Comma-separated project slugs the backfill cron should scan.                             |
| `SENTRY_ORG_SLUG`       |    no    | Defaults to `vedere`.                                                                    |
| `SENTRY_BASE_URL`       |    no    | Defaults to `https://sentry.io/api/0`.                                                   |
| `HERMES_WEBHOOK_URL`    |    no    | Backfill posts here. Defaults to `http://localhost:9119/api/sentry/webhook`.             |

\* Required only on the host that runs the backfill cron, not on every Hermes node.

## Auth model

* **Free-tier Sentry does not sign webhook payloads.** Auth is a shared secret-token
  query parameter: `POST /api/sentry/webhook?token=<SENTRY_WEBHOOK_TOKEN>`.
* The receiver compares with `secrets.compare_digest` (constant-time).
* The dashboard `auth_middleware` is bypassed for `/api/sentry/webhook` because the
  endpoint owns its own auth — `register_sentry_webhook` extends
  `_PUBLIC_API_PATHS`.

## Dedup, regression, and the shared cache (G5)

* SQLite at `~/.hermes/sentry-fingerprints.db`, schema
  `(fingerprint, environment, last_seen, github_issue_url, github_issue_state)`,
  PK `(fingerprint, environment)`.
* `is_new` → True when no row exists or `last_seen` is older than 30 days.
* `is_regression` → True when `last_seen` is older than 7 days **and** the recorded
  state is `closed`. Regressions create a fresh issue with the `regression` label.
* Connection opened with `check_same_thread=False` so the FastAPI handler thread
  and the backfill cron share the SAME `FingerprintCache` instance (G5).

## Issue creation

* `gh issue create --repo <mapped-repo> --title "[Sentry] <summary> (<fp[:12]>)" --body <hybrid> --label sentry-bug --label hermes-pending [--label regression]`
* Body is hybrid Markdown + a `<!-- hermes-payload -->` JSON block matching
  `Vhailors/vedere-shared@main:golden/payload-schema.ts`.
* `hermes-pending` is applied at creation time so the Hermes triage loop can scan
  the label even if Hermes was offline when the issue was created (downtime
  fallback).

## Environment → repo mapping (compile-time)

```
lms-{prod,staging,dev}        → manlaughed/VedereLMS
aireader-{prod,staging,dev}   → Vhailors/AIReader
university-{prod,staging,dev} → Vhailors/VedereUniversity
```

Unknown environments yield `400 unknown environment`. Adding a new project is an
explicit code edit reviewed in PR.

## Deploy: BLUE-GREEN MANDATORY (G2 lock-in)

The webhook receiver is on the request path of every Sentry alert. We require
zero-downtime deploys with **RTO < 60s** during deploy windows.

Two systemd units run side-by-side; nginx fronts them:

```
# /etc/systemd/system/hermes@blue.service
[Service]
Environment=HERMES_PORT=9119
ExecStart=/opt/hermes/.venv/bin/hermes dashboard --no-browser --host 127.0.0.1 --port ${HERMES_PORT}
Restart=on-failure
EnvironmentFile=/etc/hermes/sentry.env

# /etc/systemd/system/hermes@green.service  (port 9120, same EnvironmentFile)
```

```
# /etc/nginx/conf.d/hermes-upstream.conf
upstream hermes_active {
    server 127.0.0.1:9119;   # blue (currently active)
    # server 127.0.0.1:9120; # green (commented out except during swap window)
}
server {
    listen 443 ssl;
    server_name hermes.vedere.io;
    location /api/sentry/webhook {
        proxy_pass http://hermes_active;
        proxy_read_timeout 30s;
    }
}
```

### Swap procedure (RTO target: <60s)

```bash
# 1. Deploy new code to the inactive color (green).
sudo systemctl restart hermes@green
# 2. Smoke-test green directly.
curl -fsS -X POST "http://127.0.0.1:9120/api/sentry/webhook?token=$SENTRY_WEBHOOK_TOKEN" \
     -H 'content-type: application/json' \
     -d '{"action":"triggered","data":{"event":{"fingerprint":["smoke"],"environment":"lms-prod"}}}'
# 3. Edit upstream conf to point at green; reload nginx gracefully.
sudo sed -i 's|server 127.0.0.1:9119;|# server 127.0.0.1:9119;|; s|# server 127.0.0.1:9120;|server 127.0.0.1:9120;|' \
     /etc/nginx/conf.d/hermes-upstream.conf
sudo nginx -t && sudo nginx -s reload
# 4. After verification window, stop the now-idle blue.
sudo systemctl stop hermes@blue
```

`nginx -s reload` is graceful — in-flight requests drain on the old upstream. The
flip itself is sub-second.

## 6h backfill cron (G5 unified dedup)

`cron/sentry_backfill.py` re-queries the Sentry events API for the last 6h+1h
margin and POSTs each unseen event to the live webhook URL. Because the synthetic
POST goes through the SAME endpoint, it consults the SAME `FingerprintCache` —
no parallel logic to drift out of sync.

Crontab entry (deploy via `crontab -e`, or systemd timer if preferred):

```
0 */6 * * * /usr/bin/env -i HOME=$HOME bash -lc 'source .venv/bin/activate && python -m cron.sentry_backfill >> ~/.hermes/logs/backfill.log 2>&1'
```

Required env in the cron environment: `SENTRY_AUTH_TOKEN`,
`SENTRY_WEBHOOK_TOKEN`, `SENTRY_PROJECTS`. If running over a systemd timer,
encode them in `EnvironmentFile=` rather than the unit body.

## Operational checks

* Verify cache is healthy: `sqlite3 ~/.hermes/sentry-fingerprints.db 'SELECT COUNT(*) FROM fingerprints;'`
* Tail receiver logs: `journalctl -u hermes@blue -f | grep sentry-webhook`
* Tail backfill: `tail -f ~/.hermes/logs/backfill.log`
* Force-replay one fingerprint (after deleting its row):
  `sqlite3 ~/.hermes/sentry-fingerprints.db "DELETE FROM fingerprints WHERE fingerprint='<fp>'"`

---
name: sap-admin-audit
description: Observe, verify, audit and actively control the external HTTP traffic hitting the CrewAI control-plane (apps/api-railway). End users call the control-plane directly over HTTP; this skill lets the admin (Telegram/CLI) see those requests, inspect a specific one, view stats, and take control actions — block/unblock a user, throttle, revoke a token, cancel an in-flight request. Trigger on: "who is using the API", "show recent requests", "audit", "what did user X ask", "block user", "throttle", "revoke token", "cancel request", "API stats", "is the backend being abused".
version: 1.0.0
author: Hermes Agent (Nous Research)
license: MIT
metadata:
  hermes:
    tags: [SAP, Admin, Audit, Observability, Control, MCP]
    related_skills: [sap-crew-delegate]
---

# SAP Admin / Audit

End users hit the CrewAI control-plane (`apps/api-railway`) **directly over HTTP**
(`/v1/copilot/chat` etc.) — they do not pass through Hermes. The control-plane audits
every external `/v1/*` request and exposes an admin plane. Hermes (admin, via Telegram/CLI)
uses these `admin_*` MCP tools (from the `sap_crew` server) to watch and control it.

## Observe / verify / audit (read)

- `admin_audit_list(limit, user_id?, path?, status?, days?)` — recent external requests,
  newest first. Each row: request_id, path, method, user_id, status, latency_ms, client.
  Copilot rows also carry message, reply_snippet, plan, model, improvements (quality gate).
- `admin_audit_get(request_id)` — full entries for one request.
- `admin_audit_stats(days?)` — totals, by status/user/path, latency p50/p95/p99.
- `admin_control_state()` — blocked users, throttles, revoked tokens, in-flight requests.

## Control (write — irreversible-ish, confirm with the operator first)

- `admin_block_user(user_id)` / `admin_unblock_user(user_id)` — block returns 403 for all
  that user's external traffic.
- `admin_throttle(user_id, rpm)` — per-user requests/minute cap; `rpm<=0` clears it.
- `admin_revoke_token(token_fp)` — reject a bearer by its fingerprint (read it from an
  audit row). The machinery/admin secret itself cannot be revoked.
- `admin_cancel_request(request_id)` — cooperative cancel of an in-flight request
  (best-effort: long crew runs check the flag at stage boundaries).

## Guidance

- For read questions ("who/what/how many"), call the read tools and summarize.
- For control actions, state exactly what will happen and confirm before calling, then
  report the new control state.
- Identify offenders from `admin_audit_stats` (top_users) or repeated 4xx/5xx in
  `admin_audit_list`, then act with block/throttle/revoke.

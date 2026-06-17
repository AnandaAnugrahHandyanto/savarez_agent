# SAP Crew Integration — Hermes as admin console, CrewAI as SAP orchestrator

Two distinct entry paths — Hermes is **admin-facing only**:

- **Admin** → Telegram + CLI → **Hermes** (master orchestrator). Single admin identity,
  one bearer token. Hermes delegates SAP work to the crew and runs ops/monitoring.
- **End user** → HTTP from app/site → **api-railway directly** (`/v1/copilot/chat`). End
  users do NOT go through Hermes. That path already exists and is complete (Firebase /
  channel-session auth + per-user quota + crew + quality gate).

The CrewAI control-plane (`apps/api-railway`) is the **SAP skills/agents orchestrator**
(7 agents, 4-task pipeline, abaplint quality gate). Hermes connects to it over MCP
(control-plane = MCP server, Hermes = MCP client).

## Architecture

```
ADMIN (Telegram / CLI)                       END USER (app / site)
   → HERMES (master, single admin token)        → HTTP POST /v1/copilot/chat
       1. coarse triage: is this SAP?               → api-railway: auth + quota + crew
            ├ no  → Hermes' own tools                  │  (direct, no Hermes)
            └ yes → sap_copilot_delegate(...)          │
                      → /v1/copilot/chat               ▼
                      → crew 4-task + quality gate  AuditMiddleware logs every /v1/*
       2. deliver reply on Telegram/CLI            + enforces block / throttle / revoke
                                                       │
   ◄── observe + control ──────────────────────────────┘
       admin_* MCP tools → /v1/admin/{audit,control}
```

Hermes is also the **audit/admin plane** over the end-user traffic: it observes, verifies,
audits, and actively controls the external requests it never routes.

Admin uses the machinery/admin bearer → treated as a paid (unlimited) plan, so admin
delegation never consumes end-user quota. Auth and quota stay **authoritative in the
control-plane**; the `/v1/auth/introspect` endpoint is available for the site/app to do
read-only pre-flight (login + quota UX) before calling `/v1/copilot/chat`.

## 1. Register the control-plane MCP server in Hermes

Add to `~/.hermes/config.yaml`:

```yaml
mcp_servers:
  sap_crew:
    url: "https://<api-railway-host>/mcp"
    headers:
      Authorization: "Bearer ${API_RAILWAY_TOKEN}"
    timeout: 180          # full crew pipeline is high-latency
    connect_timeout: 60
```

`tools/mcp_tool.py` (`register_mcp_servers`) discovers and registers the remote tools into
the Hermes registry. They appear as native tools:
- `sap_copilot_delegate` — full crew pipeline (use for end-to-end SAP tasks)
- granular: `abap_lint`, `sap_adt_cli`, `sap_odata_query`, `sap_bapi_call`,
  `sap_hana_query`, `sap_docs_search`, `cpi_lint`, ...

## 2. Secrets

Admin is a single identity → one bearer in `~/.hermes/.env` (never in versioned YAML).
Use the control-plane `MACHINERY_API_TOKEN` (server secret → unlimited plan):

```
API_RAILWAY_TOKEN=<machinery-api-token>
API_RAILWAY_URL=https://<api-railway-host>
```

## 3. Enable the routing skill

The `sap` optional-skill (`optional-skills/sap/sap-crew-delegate`) tells Hermes when to
delegate. Install it into `~/.hermes/skills/` (or your skills dir) so it loads.

## 4. Channels (admin only)

Enable Telegram + CLI in `~/.hermes/config.yaml`. No per-channel identity mapping is
needed — Hermes serves a single admin, so the one `API_RAILWAY_TOKEN` is used for every
delegation. (No `channel_identity_link` table — that was only relevant if end users came
through Hermes, which they do not: they hit api-railway over HTTP directly.)

## Audit / admin plane (Hermes observes + controls external traffic)

End users hit the control-plane directly, but the admin must be able to see and govern
that traffic. The control-plane provides:

- **Capture:** `AuditMiddleware` (`app/middleware/audit.py`) records every external
  `/v1/*` request (method, path, status, latency, request-id, subject, client) to a
  file-based audit log (`audit_service`, JSONL under `ARTIFACT_BASE_DIR/audit`). The
  copilot route adds a rich record (message, reply, plan, model, quality-gate
  improvements, quota).
- **Control:** the same middleware enforces blocked users (403) and throttles (429);
  `require_machinery_bearer` rejects revoked tokens. Admin (machinery token) is always
  exempt from enforcement.
- **Admin API** (`/v1/admin/*`, guarded by `require_machinery_bearer`):
  `GET /audit`, `GET /audit/{request_id}`, `GET /audit/stats`, `GET /audit/stream` (SSE),
  `GET /control`, `POST /control/{block,unblock,throttle,revoke,cancel}`.

Hermes drives this through the `admin_*` MCP tools (see the `sap-admin-audit` skill).

## Control-plane endpoints used

- `POST /v1/auth/introspect` (`app/api/routes/auth.py`) — read-only validate + quota
  snapshot. Reuses `require_machinery_bearer` and `daily_quota.get_usage` (no increment).
- `sap_copilot_delegate` MCP tool (`app/api/routes/mcp_sse.py`) — POSTs to
  `/v1/copilot/chat`, which re-validates and consumes quota once, then runs the crew.
- `admin_*` MCP tools → `/v1/admin/{audit,control}` — observe + control external traffic.

## Verify

1. Start the control-plane; confirm `/v1/auth/introspect` and `/mcp` respond.
2. In Hermes, check the `register_mcp_servers` log line lists `sap_crew.*` tools (or run
   `/tools`).
3. Pre-flight: `curl -X POST $API_RAILWAY_URL/v1/auth/introspect -H "Authorization: Bearer
   $API_RAILWAY_TOKEN" -d '{"plan":"PRO"}'` → `{valid:true, ...}`.
4. Delegation: ask Hermes a SAP task; confirm it calls `sap_copilot_delegate` and the
   reply carries crew/quality-gate output (`agent.log`).
```

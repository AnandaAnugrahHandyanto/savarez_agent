# Hermes AI Office — Stage 5 Test Plan

Last updated: 2026-05-08 12:17 KST
Status: Stage 5 technical architecture design. Documentation-only; no implementation approved.

## Purpose

This document defines the tests required before and during a future Stage 6 read-only implementation. It focuses on redaction, unknown provenance, source failure behavior, API auth, and read-only guarantees.

## Test command policy

Use the repository wrapper, not direct pytest:

```bash
scripts/run_tests.sh tests/hermes_cli/test_office_state.py -q
scripts/run_tests.sh tests/hermes_cli/test_office_api.py -q
scripts/run_tests.sh tests/web/test_office_page.py -q
```

For frontend tests, use the existing web test command if Stage 6 adds React tests:

```bash
export PATH="$HOME/.local/node-v24.11.1-linux-x64/bin:$PATH"
(cd web && npm test -- --run)
```

If npm is needed in WSL, use Linux Node from `~/.local/node-v24.11.1-linux-x64/bin` to avoid Windows npm path issues.

## Proposed test files

Backend:

```text
tests/hermes_cli/test_office_redaction.py
tests/hermes_cli/test_office_state_adapters.py
tests/hermes_cli/test_office_api.py
```

Frontend:

```text
web/src/pages/__tests__/OfficePage.test.tsx
web/src/components/office/__tests__/*.test.tsx
```

Exact frontend test placement can follow existing project conventions discovered during Stage 6.

## Fixture strategy

Use temporary `HERMES_HOME` fixtures. Do not read the user's live `~/.hermes` state in tests.

Backend fixture categories:

1. Minimal empty Hermes home.
2. Kanban board with safe task fields plus dangerous body/result/log fields.
3. Cron jobs file with prompt/script/context/output-like fields and explicit Telegram delivery.
4. Session DB with source metadata plus dangerous messages/tool calls/reasoning.
5. Topic registry with known label, unknown label, and conflict/redaction cases.
6. Source read failure fixtures.

## Redaction serializer tests

### R001 — Secret-like strings are removed from display fields

Input examples:

- `sk-...`,
- `Bearer abc123`,
- Telegram bot token shape `123456789:AA...`,
- `.env` path reference,
- `auth.json` reference,
- home/cache/log/script absolute paths.

Expected:

- returned safe string does not contain the secret/path,
- redaction report increments count or warning,
- omitted section names are categories, not sensitive content.

### R002 — Sensitive source sections are absent from OfficeState

Fixture contains:

```yaml
kanban_task:
  body: "private prompt"
  result: "private result"
  latest_summary: "private summary"
cron_job:
  prompt: "private cron prompt"
  script: "hermes_daily_health_digest.py"
  context_from: ["other-job"]
session_message:
  content: "private message"
  tool_calls: "raw tool json"
  reasoning: "hidden reasoning"
```

Expected OfficeState JSON does not contain keys or values:

- `body`,
- `result`,
- `latest_summary`,
- `prompt`,
- `script` content/path except redacted error summary category,
- `context_from`,
- `messages`,
- `tool_calls`,
- `reasoning`,
- private string values.

### R003 — Redaction report is present and stable

Expected:

```yaml
redactions:
  policy_version: 1
  redacted_field_count: >= 0
  omitted_sections:
    - session_messages
    - cron_prompt
    - task_logs
```

The exact count should be asserted only when fixtures are stable. Avoid brittle snapshot tests over entire DTOs.

## Unknown provenance tests

### P001 — Legacy Kanban task does not invent source

Given a Kanban task with no first-class source fields:

Expected:

```yaml
provenance.confidence: unknown
provenance.missing_reason: legacy_task|schema_missing_field
work_item.flags includes unknown_provenance
source_topic_ref: null
```

Must not infer from task title/body.

### P002 — Telegram session platform does not invent topic

Given session row:

```yaml
source: telegram
user_id: some internal id
```

and no chat/thread/message columns:

Expected:

- `source_platform=telegram`,
- topic/message fields are unknown/null,
- `missing_reason=schema_missing_field`,
- no topic label inferred from title/preview/message text.

### P003 — Cron explicit delivery creates destination, not origin

Given cron job:

```yaml
deliver: telegram:-1003775710032:11
origin: null
```

Expected:

- delivery target platform `telegram`, thread display per localhost policy,
- relation `delivered_to`,
- `origin` remains unknown or absent,
- no `created_from` Telegram topic is fabricated.

### P004 — Topic id without registry label remains unknown

Given delivery target with chat/thread and no registry entry:

Expected:

- topic exists only as unknown/id-safe fallback or delivery target,
- `confidence=derived|unknown`,
- warning `registry_missing` or `unknown_topic_label`.

### P005 — Notify subscription is delivery/subscription only

Given `kanban_notify_subs` with platform/chat/thread:

Expected:

- relation `subscribed_to` or `delivered_to`,
- no origin/source relation created.

## Data-source failure tests

### F001 — Missing Kanban source does not blank Cron/Sessions

Given missing Kanban board directory but valid cron fixture:

Expected:

- `data_sources.kanban.status=missing`,
- cron automations still render,
- summary does not treat missing Kanban as zero blocked work without source warning.

### F002 — Malformed cron jobs file returns source error

Given invalid `jobs.json`:

Expected:

- `data_sources.cron.status=error`,
- redacted error summary exists,
- other sources still render,
- HTTP response is 200 if OfficeState can be built.

### F003 — Registry malformed does not hide explicit delivery ids

Given malformed topic registry and valid cron explicit delivery:

Expected:

- `topics` source `error`,
- delivery target still appears with unknown/id-safe fallback,
- no label fabricated.

### F004 — Session DB locked/unreadable becomes source error

Expected:

- `sessions` status `error`,
- no fallback to raw session JSON/messages,
- other source panels survive.

## API auth/read-only tests

### A001 — Office API requires dashboard session token

Using `starlette.testclient.TestClient` against `hermes_cli.web_server.app`:

- Without `X-Hermes-Session-Token`: `GET /api/office/state` returns 401.
- With valid token: returns 200 and valid DTO.

### A002 — Office routes are not public or plugin routes

Expected:

- `/api/office/state` is not in `_PUBLIC_API_PATHS`,
- path does not start with `/api/plugins/`,
- auth middleware protects it.

### A003 — No mutation routes exist

Test the common mutation methods:

```text
POST /api/office/state
PUT /api/office/state
PATCH /api/office/state
DELETE /api/office/state
```

Expected:

- 405 or 404,
- no side effects,
- no data writes.

### A004 — Capabilities declare read-only

Expected:

```yaml
capabilities.read_only: true
capabilities.mutations_enabled: false
```

## Frontend tests

### UI001 — `/office` renders read-only badge and source strip

Fixture OfficeState has mixed source statuses.

Expected visible text:

- `Read-only`,
- Kanban/Cron/Sessions/Topics source statuses,
- generated timestamp.

### UI002 — Source errors are displayed, not converted to zero

Given `cron.status=error`, expected:

- Cron source card says error/unavailable,
- automations panel does not say healthy zero failures unless source is ok and empty.

### UI003 — No mutation controls

Query DOM for labels/buttons:

- `Create`,
- `Edit`,
- `Dispatch`,
- `Pause`,
- `Resume`,
- `Trigger`,
- `Delete`,
- `Restart`.

Expected: absent from Office MVP components, except harmless text inside documentation/error examples should not be part of actionable buttons.

### UI004 — Sensitive fixture strings are not rendered

Render fixture containing sentinel strings:

```text
SECRET_TASK_BODY_SENTINEL
SECRET_CRON_PROMPT_SENTINEL
SECRET_SESSION_MESSAGE_SENTINEL
SECRET_TOOL_OUTPUT_SENTINEL
```

Expected: none appear in DOM.

### UI005 — Existing `/chat` route remains separate

Existing App routing should still keep `/chat` as the persistent `ChatPage` route/sink when embedded chat is enabled. The Office page must not import or render the chat composer/transcript.

## Regression tests to avoid

Do not write change-detector tests that assert exact counts from the user's live WSL data, e.g. exact number of Kanban boards, cron jobs, sessions, or topic ids. Use fixtures and invariants.

Good invariant examples:

- every returned data source has a status,
- unknown provenance has a missing reason,
- no sensitive field names appear in serialized DTO,
- failed source does not erase unrelated sources,
- API auth protects `/api/office/state`.

Bad examples:

- assert live board `hermes-runtime` has exactly two blocked tasks,
- assert cron job id `70378c4d2890` exists,
- assert Telegram chat id appears in all environments.

## Stage 6 minimum verification before user-visible rollout

Backend focused slice:

```bash
scripts/run_tests.sh tests/hermes_cli/test_office_redaction.py tests/hermes_cli/test_office_state_adapters.py tests/hermes_cli/test_office_api.py -q
```

Existing dashboard regression slice:

```bash
scripts/run_tests.sh tests/hermes_cli/test_web_server.py tests/hermes_cli/test_web_server_host_header.py -q
```

Frontend build/test slice:

```bash
export PATH="$HOME/.local/node-v24.11.1-linux-x64/bin:$PATH"
(cd web && npm run type-check && npm test -- --run)
```

Final pre-merge/full verification when practical:

```bash
scripts/run_tests.sh
```

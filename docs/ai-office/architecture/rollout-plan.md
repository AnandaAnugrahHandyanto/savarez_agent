# Hermes AI Office — Stage 5 Rollout and Stage 6 Implementation Plan

Last updated: 2026-05-08 12:17 KST
Status: Stage 5 technical architecture design. Documentation-only; no implementation approved.

## Purpose

This document converts the Stage 5 architecture into a staged implementation plan for a future Stage 6 read-only MVP. It is not approval to implement Stage 6.

## Approval boundary

Before Stage 6 starts, the user must explicitly approve a specific implementation slice.

Stage 5 has not approved:

- code changes,
- dependency installation,
- dashboard build changes,
- service restart,
- Kanban/cron mutation,
- config/systemd/gateway changes,
- public dashboard exposure,
- NAS/Obsidian writes.

## Stage 5 architecture decisions

Stage 5 recommends:

1. Backend API: protected built-in `/api/office/...` routes, not unauthenticated plugin HTTP routes.
2. Storage posture: Stage 6 computes OfficeState in memory and may read an optional profile-local topic seed registry if it already exists; no writes.
3. Provenance posture: Stage 6 computes unknown/derived/observed projections only; persisted provenance capture/backfill is Stage 7.
4. Redaction posture: server-side redaction serializer is mandatory before browser DTO output.
5. Frontend posture: `/office` non-pixel read-only operational map first; pixel renderer deferred.
6. Failure posture: per-source `data_sources[]` statuses; one source failure does not erase the full page.

## Proposed Stage 6 slices

### Slice 6.1 — Backend DTO and redaction skeleton

Goal:

- Add typed DTO structures and redaction utility with tests.

Candidate files:

```text
hermes_cli/office_state.py
hermes_cli/office_redaction.py
tests/hermes_cli/test_office_redaction.py
```

Verification:

```bash
scripts/run_tests.sh tests/hermes_cli/test_office_redaction.py -q
```

Acceptance:

- Redaction policy version exists.
- Sensitive sentinel strings are removed/omitted.
- DTO can serialize an empty valid OfficeState.

### Slice 6.2 — Protected empty `/api/office/state` endpoint

Goal:

- Add route returning empty-but-valid OfficeState with source statuses.

Candidate files:

```text
hermes_cli/web_server.py
hermes_cli/office_state.py
tests/hermes_cli/test_office_api.py
```

Verification:

```bash
scripts/run_tests.sh tests/hermes_cli/test_office_api.py tests/hermes_cli/test_web_server.py -q
```

Acceptance:

- Endpoint requires `X-Hermes-Session-Token`.
- Endpoint is not in `_PUBLIC_API_PATHS`.
- No mutation routes exist.
- `capabilities.mutations_enabled=false`.

### Slice 6.3 — Kanban read-only adapter

Goal:

- Map Kanban boards/tasks/diagnostics to rooms/work items/events with redaction.

Candidate files:

```text
hermes_cli/office_adapters.py
hermes_cli/office_state.py
tests/hermes_cli/test_office_state_adapters.py
```

Verification:

```bash
scripts/run_tests.sh tests/hermes_cli/test_office_state_adapters.py -q
```

Acceptance:

- Board rooms and task cards use safe fields.
- `body`, `result`, `comments`, `logs`, raw event payloads are absent.
- Legacy tasks get unknown provenance.
- Source failure becomes source status, not whole API failure.

### Slice 6.4 — Cron read-only adapter

Goal:

- Map cron jobs to automations and delivery targets.

Candidate files:

```text
hermes_cli/office_adapters.py
hermes_cli/office_delivery.py  # optional if delivery parsing helper is separated
tests/hermes_cli/test_office_state_adapters.py
```

Verification:

```bash
scripts/run_tests.sh tests/hermes_cli/test_office_state_adapters.py -q
```

Acceptance:

- Job name/schedule/state/last status render.
- `prompt`, `script`, `context_from`, raw output are absent.
- Explicit Telegram delivery parses as destination relation only.
- Malformed jobs file yields cron source error while other sources survive.

### Slice 6.5 — Session metadata adapter

Goal:

- Project session metadata and source platform without transcripts.

Candidate files:

```text
hermes_cli/office_adapters.py
tests/hermes_cli/test_office_state_adapters.py
```

Verification:

```bash
scripts/run_tests.sh tests/hermes_cli/test_office_state_adapters.py -q
```

Acceptance:

- Source platform/timestamps/counts are safe.
- Raw messages, tool calls, reasoning, system prompt are absent.
- Telegram source without thread field remains unknown topic.
- Session title remains off unless redaction tests explicitly enable it.

### Slice 6.6 — Topic registry and provenance projection

Goal:

- Normalize topic labels/fallbacks and provenance relations in memory.

Candidate files:

```text
hermes_cli/office_topics.py
hermes_cli/office_provenance.py
hermes_cli/office_state.py
tests/hermes_cli/test_office_state_adapters.py
```

Verification:

```bash
scripts/run_tests.sh tests/hermes_cli/test_office_state_adapters.py -q
```

Acceptance:

- Unknown topic labels are honest fallback, not fabricated.
- Optional registry read is read-only.
- Origin and delivery relations are separate.
- Confidence and missing reason are present.

### Slice 6.7 — Frontend `/office` route and read-only page

Goal:

- Add non-pixel Office page that consumes `/api/office/state`.

Candidate files:

```text
web/src/App.tsx
web/src/lib/api.ts
web/src/types/office.ts
web/src/pages/OfficePage.tsx
web/src/components/office/*
```

Verification:

```bash
export PATH="$HOME/.local/node-v24.11.1-linux-x64/bin:$PATH"
(cd web && npm run type-check && npm test -- --run)
```

Acceptance:

- `/office` route renders read-only badge, source health, summary, rooms, work items, automations, topics, redaction report/inspector.
- No mutation controls appear.
- Sensitive fixture strings are not rendered.
- Existing `/chat` route remains the embedded TUI.

### Slice 6.8 — Integrated verification and docs update

Goal:

- Run focused backend/frontend checks and update project handoff docs.

Verification:

```bash
scripts/run_tests.sh tests/hermes_cli/test_office_redaction.py tests/hermes_cli/test_office_state_adapters.py tests/hermes_cli/test_office_api.py tests/hermes_cli/test_web_server.py -q
export PATH="$HOME/.local/node-v24.11.1-linux-x64/bin:$PATH"
(cd web && npm run type-check)
```

If practical before merge:

```bash
scripts/run_tests.sh
```

Acceptance:

- Stage 6 status and next steps recorded.
- No service restart is performed unless separately approved.
- Gateway/dashboard runtime is not assumed to have loaded new code until explicitly restarted later.

## Stage 7 and later boundaries

### Stage 7 — Provenance capture/storage

Requires separate approval.

Potential work:

- Persist topic registry aliases.
- Add provenance side tables/files.
- Capture Telegram runtime source into sessions/tasks where appropriate.
- Backfill reviewed structural metadata.

Not part of Stage 6.

### Stage 8 — Pixel renderer design/implementation

Requires separate approval.

Potential work:

- Add pixel renderer adapter consuming `OfficeState`.
- Choose CSS/SVG/PixiJS/Canvas after asset/license review.
- Add sprites/animations only after data layer is reliable.

Not part of Stage 6.

### Later mutation/control stages

Requires separate design and approval.

Potential work:

- Kanban task controls.
- Cron controls.
- Gateway/service controls.
- Audit logging, confirmations, rollback/failure behavior.

Not part of read-only MVP.

## Approval checklist for Stage 6 start

Before implementation, confirm:

1. User approves Stage 6 implementation scope.
2. User agrees to protected built-in `/api/office/...` API placement.
3. User agrees Stage 6 remains read-only and localhost-first.
4. User agrees pixel visualization remains deferred.
5. User agrees whether Stage 6 may read an existing `~/.hermes/office/topics.json` seed registry if present.
6. User agrees session titles remain off by default unless tests prove redaction behavior.
7. User agrees no gateway/dashboard service restart is performed without separate approval.

## Risk controls

| Risk | Control |
|---|---|
| Plugin route auth gap | Use protected built-in `/api/office/...`. |
| Sensitive transcript/tool leakage | Server-side redaction serializer and tests. |
| Fabricated provenance | Unknown/missing-reason tests; no content inference. |
| Source failure hidden as zero | Per-source statuses and failure tests. |
| Dashboard chat fork | `/office` sidecar only; `/chat` remains TUI. |
| WSL npm path breakage | Use Linux Node path for web builds. |
| Accidental runtime mutation | No mutation endpoints/buttons; tests query common control labels. |

## Recommended next `/goal` if Stage 6 is approved later

```text
/goal Hermes AI Office Stage 6 read-only MVP implementation을 승인된 범위 안에서 진행한다. 보호된 /api/office/state API, redaction-first OfficeState serializers, Kanban/cron/session/topic/provenance read-only adapters, non-pixel /office page를 작은 테스트 주도 slice로 구현하고, mutation endpoint/UI·서비스 재시작·설정 변경·Kanban/cron mutation·Pixel renderer는 하지 않는다. 각 slice 후 scripts/run_tests.sh 및 web type-check로 검증하고 STATUS/NEXT handoff를 갱신한다.
```

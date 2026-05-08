# Hermes AI Office — Stage 3 User Stories

Last updated: 2026-05-08 11:54 KST
Status: Stage 3 product requirements. Documentation-only; no implementation approved.

## Stage 3 `/goal`

```text
/goal Hermes AI Office Stage 3을 구현 없이 진행한다. Stage 2 audit 문서 6개를 근거로 read-only MVP user stories, OfficeState 객체/필드, 개인정보·비밀정보 redaction 경계, information architecture, non-goals/mutation boundary를 문서화하고 STATUS/NEXT handoff를 갱신한다.
```

This goal is a session guardrail only. It does not approve code changes, dependency installs, service restarts, gateway/cron/config mutations, Kanban mutations, NAS/Obsidian writes, or public dashboard exposure.

## Source basis

These stories are derived from the Stage 2 read-only audit outputs:

- `docs/ai-office/audit/dashboard-architecture.md`
- `docs/ai-office/audit/kanban-data-model.md`
- `docs/ai-office/audit/cron-data-model.md`
- `docs/ai-office/audit/telegram-topic-routing.md`
- `docs/ai-office/audit/session-provenance.md`
- `docs/ai-office/audit/current-wsl-state-snapshot.md`

## Primary personas

### P1 — Owner/operator

The user wants one place to answer: what is Hermes doing, what needs attention, what broke, and where did the work come from?

Key needs:

- fast status scan,
- blocked/error-first prioritization,
- clear Telegram topic routing,
- safe metadata rather than raw private transcripts,
- confidence that the dashboard did not mutate anything.

### P2 — Future implementation agent

A future coding agent needs a concrete product contract before writing Stage 6 code.

Key needs:

- explicit read-only API scope,
- field-level privacy/redaction rules,
- honest missing-data behavior,
- clear mutation boundaries,
- testable acceptance criteria.

### P3 — Remote or cross-device reviewer, later only

A future MacBook/VPS/Telegram reviewer may need a read-only view of the same state.

Key needs:

- no dependency on NAS/Obsidian sync for startup,
- no secret/config exposure,
- explicit localhost-first posture before any remote access discussion,
- shared handoff docs as optional context, not runtime source of truth.

## MVP user stories

### US001 — See the current operational summary

As the owner/operator, I want an overview strip that shows running, blocked, ready/todo, done, and failed automation counts, so I can know where to look first.

Acceptance notes:

- Pull counts from normalized `OfficeState`, not directly from UI-specific Kanban internals.
- Show source health: Kanban, cron, sessions, topics.
- If a source is unavailable, show `unavailable` or `unknown`, not zero.
- No mutation controls are present in this strip.

### US002 — See Kanban boards as office rooms

As the owner/operator, I want each Kanban board represented as a room or workstream, so I can see which domain contains blocked or active work.

Acceptance notes:

- Board names/ids and status counts are safe by default.
- Known WSL boards from audit (`hermes-runtime`, `koreandeer-content`, `obsidian-ledger`) should be renderable later without hardcoding them.
- Board room cards prioritize `blocked`, `running`, and `ready` over `done`.
- Archived tasks are excluded by default unless a later design explicitly includes them.

### US003 — See active and blocked work items first

As the owner/operator, I want tasks needing attention to appear before completed history, so I do not miss blocked work.

Acceptance notes:

- Statuses map from Kanban columns: `triage`, `todo`, `ready`, `running`, `blocked`, `done`, plus `archived` behind an optional filter.
- Task title/status/board/assignee/timestamps are visible when safe.
- Task body/result/logs are not shown by default.
- If diagnostics exist, show compact badges such as `stuck`, `crashed`, `needs_user`, or `spawn_failed`.

### US004 — Understand automation health

As the owner/operator, I want cron jobs to appear as scheduled automation actors, so I can see whether they are healthy and where they deliver output.

Acceptance notes:

- Display job name, enabled/state, schedule, next run, last run, last status, and redacted error summary.
- Display delivery target as a normalized topic/room label where possible.
- The current audited job `daily-hermes-health-digest` with `last_status=error` and timeout should appear as a warning, not as healthy.
- Job prompt, script contents, context inputs, and raw output files are hidden by default.
- No create/pause/resume/trigger/delete controls in MVP.

### US005 — Understand Telegram topic routing

As the owner/operator, I want Telegram topics to appear as rooms or destination labels, so I can understand which workstream a task or automation belongs to.

Acceptance notes:

- Known local labels can be displayed from a designed registry/source, but product code must not hardcode memory facts.
- Display topic name/purpose when known, e.g. operations vs automation.
- Unknown topics show raw-safe fallback such as `telegram topic 11` or `unknown topic`, not invented labels.
- Bot tokens, environment values, and raw messages are never shown.

### US006 — Trace safe provenance without exposing transcripts

As the owner/operator, I want to know whether an item came from CLI, Telegram, cron, or Kanban worker, so I can reconstruct context without opening raw prompts by default.

Acceptance notes:

- Default provenance shows platform/source, safe topic label, session id reference if safe, and timestamps.
- Raw session messages, tool args, tool outputs, system prompts, and reasoning fields remain hidden.
- Missing task/session provenance is displayed as `unknown`, because current audits show first-class source columns are incomplete.

### US007 — Inspect a task safely

As the owner/operator, I want a task inspector drawer with safe metadata, so I can decide whether to open the full Kanban/session detail elsewhere.

Acceptance notes:

- Safe fields: id, title, board, status, assignee, priority, timestamps, dependency counts, diagnostic badges, linked safe provenance ids.
- Potentially sensitive fields such as body, result, logs, comments, tool output, and raw event payloads are redacted or summarized.
- The inspector may include links/references to existing Kanban/session pages later, but should not embed raw transcript by default.

### US008 — Trust read-only mode

As the owner/operator, I want the MVP to visibly avoid control actions, so I can use it without fear of changing runtime state.

Acceptance notes:

- No buttons for task create/edit/reassign/reclaim/dispatch.
- No cron create/pause/resume/trigger/delete buttons.
- No gateway restart/service controls.
- No config editors.
- No NAS/Obsidian writes.

### US009 — Degrade gracefully

As the owner/operator, I want the page to remain useful even when one data source fails, so dashboard failure does not hide all state.

Acceptance notes:

- Each source has explicit status: `ok`, `unavailable`, `error`, `missing`, or `partial`.
- One failing source does not prevent other panels from rendering.
- Error summaries are compact and redacted.

### US010 — Preserve the embedded Hermes TUI boundary

As the owner/operator, I want the existing `/chat` dashboard route to remain the embedded real Hermes TUI, so AI Office does not fork chat behavior.

Acceptance notes:

- AI Office is an observability/sidecar surface.
- It does not reimplement transcript, composer, slash command handling, or PTY-backed chat.
- Any future chat-related improvements belong in Ink/TUI, not a duplicate React chat.

## Deferred user stories

These are valuable but out of MVP scope:

- Pixel office/game renderer with sprites and animation.
- LLM-generated speech bubbles or summaries.
- Browser-side control actions.
- Remote dashboard exposure.
- Automatic incident task creation from cron failures.
- Cross-device NAS/Obsidian dashboard panels.
- Full raw transcript browser inside AI Office.

# Rolly/Kanban Card Workspace v0 Acceptance Spec

## Scope

v0 is a focused card workspace layered on the existing Kanban dashboard/plugin API. It keeps the existing SQLite Kanban kernel and dashboard plugin shape, but adds first-class acceptance criteria, a human approval gate, and one server-side Claude Code/tmux terminal per card. Avoid workflow/template rewrites or multi-agent orchestration changes in v0.

## Board model

- Visible columns are exactly: `todo`, `ready`, `doing`, `review`, `done`.
- Existing internal statuses may continue to exist, but dashboard serialization must map cards into these five columns without hiding `review`.
- New cards default to `todo` until acceptance is explicitly approved.

## Acceptance criteria model

Each card has an ordered acceptance criteria checklist:

```json
{
  "id": "stable item id",
  "text": "observable requirement",
  "verifier": "Rolly | User",
  "passed": false,
  "evidence": "optional evidence text/url/path"
}
```

Card-level derived fields:

- `acceptance_approved: boolean`
- `acceptance_approved_at?: unix seconds`
- `acceptance_approved_by?: string`

Acceptance rules:

- Approval toggle is disabled unless at least one criterion exists.
- Approving criteria sets `acceptance_approved=true` and card status to `ready`.
- Editing criterion `text` or `verifier` resets `acceptance_approved=false` and status to `todo`.
- Editing card body/title/notes does **not** reset approval.
- Changing `verifier` also sets that item `passed=false` but preserves existing `evidence`.
- Rolly may mark passed only items where `verifier=Rolly`, and only when non-empty evidence is supplied.
- User may mark any item passed/unpassed and may add/edit evidence.
- If all Rolly-verifier items pass and any User-verifier items remain unpassed, status becomes `review`.
- If all criteria pass, status becomes `done`.
- If criteria exist but not approved, status remains/returns `todo` unless manually archived/deleted.

## Human acceptance gate

- Start CC is disabled until both are true:
  - `acceptance_approved=true`
  - card has a valid concrete workdir.
- Before approval, Rolly card chat may research, clarify, and help draft/spec acceptance criteria only; it must not start implementation.
- Missing workdir does not block card creation, chat, acceptance drafting, or approval UI visibility; it only blocks Start CC and should cause Rolly chat to ask for/confirm the repo path.

## Workdir and execution mode

- Workdir is inferred and persisted when high-confidence; otherwise remains empty and Start CC displays a blocking reason.
- Workdir validity is checked server-side: path exists and is a directory.
- Execution mode is inferred and displayed in the CC section, with a local override there only.
- Do not add a top-level execution-mode field to the card form.
- Persist effective execution settings needed to rebuild the launch context.

## Claude Code/tmux terminal

- Start CC launches immediately from the card workspace.
- There is exactly one server-side tmux terminal/session per card.
- Tmux session id/name is persisted on the card; browser reload only reads server state and reconnects/loads metadata.
- Terminal logs are ephemeral; durable artifacts are summaries and evidence saved back to the card/runs/criteria.
- Launch context is expandable after start, but the launch does not wait on a confirmation modal.
- CC prompt includes only:
  - card title/body
  - acceptance criteria
  - workdir
  - execution mode/overrides
  - global Rolly/MIX constraints
- CC prompt must not include the Rolly/card chat transcript.

## Rolly card chat

- Chat operates against one card and can update title/body/workdir/criteria when useful.
- It should use current card state, criteria, workdir, and persisted summaries/evidence; avoid injecting full chat transcript into CC launch context.
- It must explain blockers clearly: missing approval, missing/invalid workdir, unclear criteria, or criteria requiring User verification.

## API/backend acceptance

Minimum endpoint behavior:

- `GET /api/plugins/kanban/board` returns five visible columns and enough card summary fields for approval/workdir/CC disabled states.
- `GET /api/plugins/kanban/tasks/{id}` returns full card data including criteria, acceptance approval fields, workdir validity, execution mode, tmux/CC session state, comments/events/runs as currently available.
- `POST /api/plugins/kanban/tasks` accepts initial body/workdir and optional initial criteria.
- `PATCH /api/plugins/kanban/tasks/{id}` can edit title/body/workdir and must not reset approval for body-only edits.
- Criteria writes should be explicit, either via dedicated endpoints or a nested patch, and must enforce reset semantics transactionally.
- Approval endpoint must reject empty criteria and must atomically set approval + `ready`.
- Pass/fail endpoint must enforce verifier permissions, evidence requirements, and status roll-up (`review`/`done`).
- Start CC endpoint must reject unapproved cards or invalid workdirs and persist tmux session state before returning.
- CC state endpoint returns existing persisted session state after reload.

## Likely backend files/endpoints needing changes

- `hermes_cli/kanban_db.py`
  - Add durable storage for acceptance criteria and approval fields. Prefer an additive table such as `task_acceptance_criteria` plus additive task columns for approval/workdir/execution/tmux state, or a small metadata table if preserving `tasks` width is preferred.
  - Add transactional helpers for criteria CRUD, approval reset/approve, pass/fail roll-up, workdir validation, and tmux session state persistence.
- `plugins/kanban/dashboard/plugin_api.py`
  - Change `BOARD_COLUMNS` and `STATUS_TO_BOARD_COLUMN` to include `review` as its own visible column.
  - Extend `CreateTaskBody`, `UpdateTaskBody`, `_task_dict`, `GET /board`, `GET /tasks/{id}`.
  - Add/replace endpoints for acceptance criteria approval and pass/fail.
  - Add Start CC + CC state endpoints; current `/tasks/{id}/claude-context` only builds context and validates workspace.
- `hermes_cli/kanban_ready_review.py`
  - Current heuristic/event-based ready-review is insufficient. Replace or bypass with checklist-backed acceptance approval while preserving explicit human gate semantics.
- `hermes_cli/kanban_card_chat.py`
  - Update system prompt and output schema so chat can draft/edit structured criteria and workdir, and respects pre-approval research/spec-only behavior.
- `hermes_cli/kanban_card_context.py`
  - Build CC prompt from card body + structured criteria + workdir/execution + global constraints only; remove comments/events/runs/chat transcript from launch prompt, except durable summaries/evidence if explicitly part of card state.
  - Gate context/build launch on approval + valid workdir.
- Tests likely affected/needed:
  - `tests/plugins/test_kanban_dashboard_plugin.py`
  - `tests/hermes_cli/test_kanban_card_chat.py`
  - `tests/hermes_cli/test_kanban_mix_ready_guard.py`
  - new tests for acceptance criteria CRUD/reset/approve/pass roll-up and CC launch gating.

## Non-goals for v0

- No new general workflow engine.
- No multi-terminal-per-card support.
- No durable full terminal log storage.
- No top-level execution-mode field.
- No automatic implementation before human approval.

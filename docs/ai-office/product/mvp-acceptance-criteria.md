# Hermes AI Office — Stage 3 MVP Acceptance Criteria

Last updated: 2026-05-08 11:54 KST
Status: Stage 3 product acceptance criteria. Documentation-only; no implementation approved.

## Purpose

This document converts Stage 3 requirements into testable acceptance criteria for the future Stage 6 read-only MVP. It is not approval to implement Stage 6.

## Product acceptance criteria

### A001 — Read-only mode is visible and real

The MVP shows an explicit read-only badge and provides no UI controls that mutate Hermes state.

Pass conditions:

- No Kanban create/edit/reassign/reclaim/dispatch controls.
- No cron create/edit/pause/resume/trigger/delete controls.
- No gateway restart/start/stop controls.
- No config, `.env`, toolset, model, MCP, skill, memory, or credential editors.
- No NAS/Obsidian write actions.

### A002 — First viewport answers operational status

The first viewport lets the user answer:

- what is blocked,
- what is running,
- what is ready/todo,
- what automation failed,
- which data source is missing or degraded.

Pass conditions:

- Summary counts are sourced from `OfficeState`.
- Missing/unavailable source is not rendered as zero.
- Blocked and failed states have higher visual priority than done/history.

### A003 — Kanban boards render as rooms/workstreams

The MVP displays Kanban board rooms with status counts and safe task summaries.

Pass conditions:

- Board id/name and counts are visible.
- Task cards show safe fields only: id/title/status/board/assignee/priority/timestamps/diagnostic badges.
- Task body/result/comments/logs/raw event payloads are hidden by default.
- Archived tasks are excluded by default.

### A004 — Cron jobs render as automation health

The MVP displays cron jobs as automations with schedule and health.

Pass conditions:

- Job name, enabled/state, schedule, last run, next run, last status, and redacted last error are visible.
- Delivery target is normalized to a safe topic/room label when possible.
- The audited timeout state for `daily-hermes-health-digest` would appear as a warning.
- Prompt/script/output/context content is hidden by default.
- There is no trigger/pause/resume/delete UI.

### A005 — Telegram topics render as routing metadata

The MVP displays known topic labels and unknown topic fallbacks.

Pass conditions:

- Topic names/purposes are shown only when available through a designed source/registry.
- Unknown thread ids are clearly marked unknown or internal.
- Raw Telegram messages are never displayed by default.
- Bot tokens and environment values are never read or displayed.

### A006 — Session provenance is metadata-first

The MVP uses session metadata for provenance, not raw transcripts.

Pass conditions:

- Default display may include source platform, session id, title/preview only after redaction, model/provider, started/last active timestamps, active/ended status, counts, and usage/cost summaries.
- Default display excludes full prompts, system prompts, tool args, tool outputs, reasoning fields, and raw messages.
- Missing source chat/thread/message provenance is shown honestly as missing/unknown.

### A007 — Data-source health is explicit

Each major input source reports its own health.

Pass conditions:

- `kanban`, `cron`, `sessions`, and `topics` each report `ok`, `partial`, `missing`, `unavailable`, or `error`.
- One source failure does not prevent other sections from rendering.
- Error summaries are compact and redacted.

### A008 — Redaction behavior is testable

The MVP exposes or internally records a redaction policy version/report.

Pass conditions:

- `OfficeState.redactions.policy_version` exists.
- Omitted sensitive sections are named by category, not shown in content.
- Serializer tests can verify sensitive fields are absent.

### A009 — Existing Hermes chat remains untouched

The MVP does not replace the existing dashboard `/chat` architecture.

Pass conditions:

- The embedded `hermes --tui` remains responsible for chat transcript/composer/slash command behavior.
- AI Office is a sidecar observability page/panel.
- No second React chat implementation is introduced.

### A010 — Localhost/security posture is preserved

The MVP is designed for localhost use only until a separate security review.

Pass conditions:

- No public/remote exposure is part of MVP acceptance.
- Plugin route authentication gap from Stage 2 is addressed in Stage 5 before implementation.
- Remote/Tailscale mode is deferred.

## Implementation acceptance preconditions

Before Stage 6 can begin, the project still needs:

1. Stage 4 provenance/routing design.
2. Stage 5 technical architecture and endpoint/auth design.
3. Redaction serializer test plan.
4. Explicit user approval for implementation.

## Non-acceptance examples

The MVP is not acceptable if it:

- silently hides source failures,
- shows raw transcript/tool args/log output by default,
- offers browser mutation controls,
- relies on hardcoded user-specific Telegram ids in core code,
- replaces the existing TUI-backed chat,
- requires NAS/Obsidian sync for dashboard startup,
- treats missing provenance as known.

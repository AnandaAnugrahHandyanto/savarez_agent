# Hermes AI Office — Stage 5 Deferred Pixel Renderer Adapter Contract

Last updated: 2026-05-08 12:17 KST
Status: Optional Stage 5 technical architecture note. Documentation-only; no pixel implementation approved.

## Purpose

Pixel/game visualization remains deferred, but the data architecture should avoid blocking it later. This document defines a thin adapter contract a future Stage 8 pixel renderer can consume without reaching into Kanban, cron, sessions, Telegram, or raw logs.

## Stage 5 decision

Do not implement a pixel renderer in Stage 6. Stage 6 should build a non-pixel operational map and stable `OfficeState` API first.

Future pixel renderer must consume:

```text
OfficeState DTO -> PixelSceneModel -> Renderer
```

It must not consume:

- raw Kanban DB rows,
- raw cron jobs/output files,
- raw sessions/messages/tool calls,
- raw Telegram API objects,
- plugin mutation endpoints,
- gateway/service state controls.

## Adapter input

The only input is redacted `OfficeState`:

```yaml
rooms: []
agents: []
work_items: []
automations: []
topics: []
events: []
provenance: []
redactions: {}
```

If data is missing, renderer receives explicit unknown/error/source-status fields rather than guessing.

## Adapter output

Logical future `PixelSceneModel`:

```yaml
scene_version: 1
generated_at: "ISO timestamp"
rooms:
  - id: "room:<office_room_id>"
    kind: "board|topic|system|unknown"
    label: "safe label"
    severity: "normal|warning|error"
    counts:
      running: 0
      blocked: 0
      ready: 0
agents:
  - id: "agent:<office_agent_id>"
    label: "safe label"
    status: "active|idle|blocked|unknown"
    room_id: "room:<id>|unknown"
items:
  - id: "item:<office_work_item_id>"
    label: "redacted title or generic label"
    status: "running|blocked|ready|todo|done|unknown"
    room_id: "room:<id>|unknown"
automations:
  - id: "automation:<office_automation_id>"
    label: "safe name"
    status: "scheduled|error|unknown"
    room_id: "room:<topic-or-system-id>|unknown"
warnings:
  - code: "unknown_provenance|source_error|redacted"
```

## Mapping rules

- Kanban board rooms become office rooms/floors.
- Telegram topic rooms become destination/source rooms only when known through topic registry/provenance.
- Unknown provenance becomes a visible unknown room/bucket.
- Cron jobs become automation machines/bots.
- Kanban assignees become agents only when safe display labels exist.
- Blocked/error states receive high visual priority.
- Redaction and unknown warnings should remain visible, not hidden behind cute animation.

## Renderer technology decision deferred

Possible later choices:

- CSS/SVG pixel-style cards,
- Canvas,
- PixiJS,
- Phaser.

Stage 5 does not choose or install any of these. Stage 8 should revisit after:

1. OfficeState API is stable.
2. Redaction tests pass.
3. Pixel Agents asset/code licensing is reviewed again for the exact reuse proposal.
4. The user approves dependency additions.

## Non-goals

The pixel adapter must not add:

- synthetic Smallville-style memory/agent society,
- fabricated speech bubbles,
- direct chat UI,
- task/cron/gateway controls,
- hidden polling of raw APIs,
- public dashboard exposure.

## Stage 8 preconditions

Before pixel implementation:

1. Stage 6 read-only operational map works.
2. User confirms pixel UX priority.
3. Renderer library and asset license are approved.
4. Performance budget is defined.
5. Accessibility fallback/list view remains available.
6. Pixel renderer consumes existing `OfficeState` only.

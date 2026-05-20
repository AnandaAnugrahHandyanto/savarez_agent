# Marketing Agent Factory MVP Implementation Plan

> **For Hermes:** Use subagent-driven-development skill to implement this plan task-by-task.

**Goal:** Build a dry-run-first Marketing Agent Factory inside Hermes that can maintain isolated app brand profiles, generate campaign drafts, queue approvals/schedules, dry-run publishing, and expose operator visibility.

**Architecture:** Implement as a bundled Hermes plugin (`plugins/marketing_factory`) with a JSON-backed durable store under `HERMES_HOME/marketing_factory/`, a deterministic MVP pipeline, agent-callable tools, and an operator CLI command (`hermes marketing-factory`). This keeps the feature modular and avoids risky core agent-loop changes.

**Tech Stack:** Python stdlib, Hermes plugin loader, Hermes CLI plugin command registry, JSON/JSONL durable state, pytest via `scripts/run_tests.sh`.

---

## Phase 1: Core store and domain models

- Create `plugins/marketing_factory/store.py` with JSON durable state and JSONL audit log.
- Store apps, campaigns, drafts, approvals, schedules, publish events, analytics, model routing policy, and budgets.
- Enforce brand isolation by app slug on every lookup.

## Phase 2: MVP pipeline

- Create `plugins/marketing_factory/pipeline.py` with deterministic MVP agents:
  - Brand Brain setup
  - campaign planner
  - draft generator
  - review/safety gate
  - scheduler
  - dry-run publisher
  - analytics feedback placeholder
- Seed Pupular and SetVenue sample brand profiles.
- Generate a dry-run campaign for both apps.

## Phase 3: CLI and tool surfaces

- Create `plugins/marketing_factory/cli.py`:
  - `status`
  - `init`
  - `generate --app <slug>`
  - `queue`
  - `approvals`
  - `approve <draft_id>`
  - `schedule`
  - `publish-dry-run`
  - `audit`
  - `export`
- Create `plugins/marketing_factory/tools.py` so agents can initialize, inspect, generate, approve, schedule, and dry-run publish without shelling out.
- Register plugin in `plugins/marketing_factory/__init__.py` and `plugin.yaml`.

## Phase 4: Tests and docs

- Add tests for store initialization, brand profile isolation, campaign generation, approval flow, schedule queue, dry-run publish, audit trail, model routing metadata, and CLI smoke path.
- Add docs at `docs/marketing-agent-factory.md` explaining operations and extension points.
- Run targeted tests with `scripts/run_tests.sh` and fix failures.

## Verification

- `scripts/run_tests.sh tests/plugins/test_marketing_factory.py`
- `hermes marketing-factory init --store-path /tmp/...`
- `hermes marketing-factory generate --app pupular --store-path /tmp/...`
- `hermes marketing-factory publish-dry-run --store-path /tmp/...`

## Guardrails

- No real public posting in MVP.
- Dry-run publisher only records would-post events.
- Approval is required before scheduling/publishing.
- App memories and campaign state remain isolated by brand slug.

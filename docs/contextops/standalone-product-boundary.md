# ContextOps/ESE Standalone Product Boundary and Hermes Dogfood Strategy

> **Lane anchor:** This is a `#contextops` lane artifact and the canonical
> product-boundary statement for ContextOps/ESE. It is documentation-only: it
> adds no runtime behavior, no mutation, and no Hermes upstream path.
>
> **Companion docs:** [`standalone-boundary.md`](standalone-boundary.md) (repo/
> package boundary and migration steps), [`epistemic-state-engine.md`](epistemic-state-engine.md)
> (object model + contract surface), and
> [`../plans/2026-05-17-contextops-epistemic-state-engine-roadmap.md`](../plans/2026-05-17-contextops-epistemic-state-engine-roadmap.md)
> (milestones + lane contract). Where this doc and `standalone-boundary.md`
> overlap, this doc owns *product positioning and dogfood strategy* and
> `standalone-boundary.md` owns *where the code lives and how it stays
> extractable*. Neither makes Hermes the upstream destination.

## Verdict

ContextOps/ESE is **not** a Hermes upstream contribution and should not become a tightly-coupled Hermes feature. Hermes is the first harsh dogfood environment and a thin adapter/client only.

The operating model is:

```text
strong dogfood, weak coupling
Hermes runtime -> Hermes adapter -> standard ContextOps JSON contract -> ContextOps core -> findings/recommendations -> ContextOps backlog
```

## Product Positioning

ContextOps/ESE is an independent context-operations layer for agentic systems: it observes runtime events, normalizes context, detects missing operational edges, explains risk, and recommends safe next actions.

Target runtimes include:

- Hermes
- Claude Code / Codex / OpenCode style coding agents
- Discord/Slack/Telegram operator bots
- Kanban-based multi-agent systems
- cron/webhook-driven automation
- custom autonomous workflows

Hermes is only the first adapter because it has rich real-world failures: session splits, ACK gaps, passive delivery vs active wake confusion, Kanban graph drift, stale handoffs, duplicate work, and context compaction residue.

## Non-goals

- Do not contribute ContextOps/ESE upstream into Hermes.
- Do not embed ContextOps core inside Hermes.
- Do not let Hermes internals become the product contract.
- Do not make Hermes DB/schema/session objects part of core.
- Do not auto-mutate Hermes state during initial dogfood.
- Do not treat Hermes backlog as ContextOps product backlog.
- Do not optimize for automatic fixes before detection quality is proven.

## Hard Boundary Rules

1. ContextOps core has zero Hermes imports.
2. ContextOps core has zero Hermes-specific assumptions.
3. All runtime input/output crosses a versioned JSON contract.
4. Hermes-specific interpretation lives only in the Hermes adapter.
5. Safety gates live in ContextOps core and fail closed.
6. Initial dogfood is read-only and suggestion-only.
7. Dogfood findings route to ContextOps backlog by default.
8. Detectors must be portable beyond Hermes or explicitly marked adapter-local.
9. No automatic mutation without explicit future approval, evidence, idempotency, audit trail, and rollback/compensation.
10. No Hermes upstream path unless separately and explicitly re-approved.

## Architecture

```text
Hermes / Other Agent Runtime
        ↓
Runtime-specific Adapter
        ↓
Versioned ContextOps JSON Contract
        ↓
ContextOps Core
  - schema validation
  - normalization
  - detector framework
  - recommendation model
  - evidence bundles
  - safety gate
  - policy decision
        ↓
Suggestion / Report / Review Queue
        ↓
ContextOps Product Backlog
```

## Ownership Split

### ContextOps Core owns

- Standard event schema
- Finding/recommendation schema
- Evidence bundle schema
- Detector framework
- Safety decision model
- Policy gate
- Duplicate/staleness/missing-edge detection
- Product backlog signals
- Portable tests and fixtures

### Hermes Adapter owns

- Hermes session export/read mapping
- Hermes Kanban state mapping
- Gateway delivery event mapping
- ACK / passive delivery / active wake classification
- Hermes-specific evidence extraction
- Formatting results back to operator channels
- Suggestion-only sink into #contextops

### Hermes owns

- Runtime execution
- Gateway delivery
- Kanban execution
- Sessions
- Skills/tools
- Platform adapters
- Live mutations

## Contract-first Interface

Core should consume serialized DTOs, not Hermes Python objects.

Minimum contract types:

- `runtime_event`
- `session`
- `message`
- `task`
- `handoff`
- `ack`
- `tool_call`
- `operator_action`
- `finding`
- `recommendation`
- `safety_decision`
- `evidence_bundle`

Example handoff event:

```json
{
  "schema_version": "contextops.v0.1",
  "type": "handoff",
  "runtime": "hermes",
  "adapter": "hermes",
  "source": {
    "kind": "session",
    "id": "opaque-session-ref"
  },
  "target": {
    "kind": "channel",
    "id": "opaque-channel-ref"
  },
  "delivery_mode": "passive",
  "expected_ack": true,
  "observed_ack": false,
  "evidence_refs": [
    "session:event:...",
    "kanban:task:..."
  ]
}
```

Required contract properties:

- `schema_version` on every object.
- Unknown fields handled explicitly, not silently trusted.
- Unknown event/action types fail closed.
- Evidence references are opaque; raw transcript/provider payload must not leak into previews.
- Contract tests run adapter output through core validation.

## Safety Model

Initial policy:

```json
{
  "default_mode": "suggestion_only",
  "allow_mutation": false,
  "allow_external_send": false,
  "allow_memory_write": false,
  "allow_task_create": false,
  "require_evidence": true,
  "require_idempotency_key_for_future_mutation": true,
  "fail_closed_on_unknown": true
}
```

Safety decision states:

- `ALLOW_READ`
- `SUGGEST_ONLY`
- `NEEDS_REVIEW`
- `BLOCK`
- `UNSUPPORTED`
- `UNKNOWN_FAIL_CLOSED`

Before any future mutation, all of these must exist:

- evidence bundle
- confidence score
- idempotency key
- duplicate guard
- target validation
- human/operator approval path
- audit trail
- rollback or compensating action
- adapter capability declaration
- explicit product decision to enable that action class

## Dogfood Phases

### Phase 0 — Contract fixtures

Goal: prove ContextOps can process Hermes-shaped data without depending on Hermes internals.

Acceptance:

- Versioned JSON schemas exist.
- Hermes-like fixtures validate.
- Core tests run without Hermes imports.
- Leak fixtures prove fail-closed behavior.

### Phase 1 — Read-only Hermes observation

Goal: observe Hermes state and emit findings only.

Candidate detectors:

- Missing origin ACK after delegated work.
- Passive delivery mistaken for active wake.
- Kanban task done but origin not informed.
- Duplicate remediation loops.
- Stale handoff / idle dependency graph.
- Session continuity split after compaction.
- Lane contamination / wrong owner lane evidence.
- Adapter leaking raw transcript/provider payload fields.

No mutation, no task creation, no memory write, no cross-channel send.

### Phase 2 — Suggestion sink to #contextops

Goal: turn findings into reviewable product-learning artifacts.

Each report should include:

- finding type
- concise explanation
- evidence refs
- confidence
- suggested operator action
- routing category
- false-positive feedback option

Routing categories:

- ContextOps core improvement
- Hermes adapter improvement
- schema/fixture improvement
- documentation/product clarification
- false positive / not actionable
- separate Hermes issue only if explicitly approved

### Phase 3 — Operator review loop

Goal: learn detector quality before automating anything.

Track:

- useful finding rate
- false positive rate
- evidence completeness
- time-to-human-awareness
- duplicate suppression rate
- adapter leakage count
- detector portability beyond Hermes
- suggestion-to-backlog conversion rate
- avoided unsafe mutation count

Avoid optimizing for:

- number of automatic task creations
- number of automatic fixes
- number of Hermes patches
- number of upstream contributions

### Phase 4 — Dry-run action plans

Goal: generate proposed actions but do not execute them.

Examples:

- proposed ACK relay plan
- proposed duplicate-card archive plan
- proposed fix/review graph plan
- proposed memory exclusion plan
- proposed contextpack redaction plan

Output is JSON action plan plus safety decision. Operator applies manually if desired.

### Phase 5 — Limited approved mutations, later

Only after Phases 0–4 prove reliability.

Allowed candidates, eventually:

- local report generation
- redacted preview suppression
- idempotent low-risk observation comments
- explicitly approved Kanban hygiene suggestions

Still forbidden until separately approved:

- automatic commits
- automatic upstream changes
- automatic memory rewrites
- automatic worker spawn
- automatic cross-channel send
- automatic state mutation after ambiguous evidence

## Implementation Guardrails

### Code/package guardrails

- Put ContextOps core in a standalone package boundary.
- Keep Hermes adapter physically separate from core.
- Add import-lint/CI guard to prevent core importing Hermes modules.
- Keep separate `pyproject.toml`, version, dependencies, and schema files even if still repo-local for now.
- Ensure core test suite runs without Hermes runtime installed.
- Treat adapter tests as integration tests, not core tests.

### Contract guardrails

- Every adapter emits only versioned JSON.
- Core validates schema at the boundary.
- Unknown event/action fails closed.
- Raw message/provider payload fields are never included in user-facing previews.
- Evidence refs are opaque handles, not raw secrets/transcripts.

### Product guardrails

- Findings go to ContextOps backlog, not Hermes upstream.
- Hermes-specific issues must be classified as adapter-local unless proven portable.
- A detector that cannot run on non-Hermes fixtures must be labeled adapter-local.
- Product metrics reward detection quality, not automation volume.

## Naming note: `contextops_ese` is a prototype-phase disambiguator only

The in-repo skeleton uses the import root `contextops_ese` (distribution
`contextops-ese`). The `_ese` suffix ("Epistemic State Engine") is a
**prototype-phase, in-repo disambiguator only** — it exists solely because two
packages cannot share the `contextops` import root inside a single repo while
the prototype still owns it. It is **not** the product name. The product target
is the standalone **ContextOps** (repo and distribution `contextops`, import
root `contextops`). At migration the `_ese` suffix is dropped. See
[`standalone-boundary.md`](standalone-boundary.md) for the full naming decision.

## First Concrete Slice Proposal

Title:

```text
Define ContextOps standalone product boundary and Hermes dogfood adapter contract
```

Acceptance criteria:

- Document ContextOps as independent product, not Hermes upstream.
- Define core vs adapter vs Hermes ownership.
- Define minimum JSON contract and schema-versioning rule.
- Define fail-closed safety decision states.
- Define read-only/suggestion-only dogfood phases.
- Define backlog routing categories and metrics.
- Add anti-coupling rules: no Hermes imports in core, no Hermes DB schema in core, no automatic mutation.

Second slice:

```text
Build read-only Hermes dogfood adapter prototype for ContextOps/ESE
```

Acceptance criteria:

- Adapter exports Hermes session/Kanban/gateway observations into standard JSON fixtures.
- Core consumes fixtures without Hermes imports.
- Findings are emitted as suggestion-only reports.
- Leak probes pass fail-closed.
- No Hermes state mutation.
- #contextops receives operator-readable reports.

## Open Questions for #contextops

1. What is the minimum v0 event schema?
2. Which Hermes data sources are acceptable for read-only dogfood?
3. Where should findings live: markdown, local DB, Kanban, issues, or a dedicated ContextOps backlog?
4. What is the human review UI for useful/false-positive/duplicate findings?
5. What evidence bundle is enough for a finding to be trusted?
6. Which second non-Hermes adapter should prove portability?
7. When, if ever, should approved mutations be considered?

## Standing Decision Record

```text
CONTEXTOPS PRODUCT BOUNDARY: GO
```

Decision points:

1. ContextOps/ESE remains a separate product.
2. Hermes is first dogfood adapter only.
3. No Hermes upstream contribution path by default.
4. Core has no Hermes imports or Hermes schema assumptions.
5. All IO crosses versioned JSON contracts.
6. Initial dogfood is read-only/suggestion-only.
7. Safety gates live in core and fail closed.
8. Dogfood findings route to ContextOps backlog by default.

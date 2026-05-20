# ContextOps standalone repo/package boundary

> **Lane anchor:** This is a `#contextops` lane artifact. ContextOps is an
> independent, repo-local lane today and a separate repository/package
> long-term. It is **not** subordinate to the `#hermes-main` memory/compaction
> track. `#hermes-main` carries only a minimal, stable integration shim — if any
> is needed at all — never ContextOps core logic.
>
> **Companion docs:**
> [`standalone-product-boundary.md`](standalone-product-boundary.md) (canonical
> product positioning + Hermes dogfood strategy),
> [`epistemic-state-engine.md`](epistemic-state-engine.md)
> (object model + contract surface), and
> [`../plans/2026-05-17-contextops-epistemic-state-engine-roadmap.md`](../plans/2026-05-17-contextops-epistemic-state-engine-roadmap.md)
> (milestones + lane contract). This document specifies *where the code lives*
> and *how it stays extractable*; `standalone-product-boundary.md` owns *what
> the product is and how Hermes is dogfooded*. Both add no new behavior.

## Purpose

This document answers Open Question #1 of the roadmap ("Should ContextOps live
inside the Hermes repo initially, or become its own repo/package after MVP?")
with an operational boundary spec. It defines the standalone repo name/path,
package layout, import policy, the integration contract with Hermes, what stays
in Hermes as an adapter/shim, and the migration steps — so the boundary is
managed deliberately by the `#contextops` lane and never drifts into Hermes
upstream `main`.

It is a documentation-only artifact. It moves no code, modifies no prototype
Python, and modifies no tests.

## Product boundary: ContextOps/ESE is a separate product

This boundary spec assumes — and this section makes explicit — that
ContextOps/ESE is its **own product**, not a Hermes feature. The full product
positioning and dogfood strategy live in the canonical
[`standalone-product-boundary.md`](standalone-product-boundary.md); the
non-negotiable points it establishes, and that this document is consistent
with, are:

- **ContextOps/ESE is a separate product.** It is an independent
  context-operations layer for agentic systems, with its own backlog, schema,
  and release cadence. Hermes is one of several target runtimes, not the owner.
- **Hermes is a dogfood adapter/client only.** Hermes is the first — and
  deliberately harsh — dogfood environment because it surfaces rich real-world
  failures (ACK gaps, session splits, Kanban drift, compaction residue). It is
  a thin adapter/client, never the product itself.
- **No Hermes upstream-by-default.** Hermes is not the upstream destination for
  ContextOps work. There is no Hermes upstream contribution path unless it is
  separately and explicitly re-approved by the `#contextops` lane.
- **Versioned JSON contract between adapters and core.** All runtime input and
  output crosses a versioned JSON contract (`schema_version` on every object).
  Adapters emit only that contract; core validates it at the boundary. Core
  never consumes Hermes Python objects, DB rows, or session objects directly.
- **Read-only / suggestion-only initial dogfood.** The initial dogfood phases
  are strictly read-only and suggestion-only: no mutation, no task creation, no
  memory write, no cross-channel send. Mutation is gated behind separate future
  approval with evidence, idempotency, audit trail, and rollback.
- **Fail-closed core safety gates.** Safety gates live in ContextOps **core**
  (not the adapter) and fail closed: unknown event/action types and ambiguous
  evidence resolve to a blocking/`UNKNOWN_FAIL_CLOSED` decision, never to a
  permissive default.
- **Dogfood findings route to the ContextOps backlog by default.** Findings
  produced while dogfooding on Hermes are ContextOps product-learning
  artifacts; they route to the ContextOps backlog by default and become a
  "separate Hermes issue" only when explicitly approved.

In short: **strong dogfood, weak coupling.** Hermes exercises ContextOps hard
and feeds it real failure signal, but the code, the contract, the safety gates,
and the backlog all belong to ContextOps. Nothing here makes Hermes the
upstream destination.

## Terminology guard

This doc preserves the non-negotiable distinctions from
`epistemic-state-engine.md`. Any boundary decision that blurs one of these is a
contamination bug, not a packaging convenience:

- **Thread != topic** — a persistent cognitive line, not a topic label.
- **Heat != recency** — a composite signal, not last-mention time.
- **Compaction != summary** — preservation of unresolved cognitive pressure.
- **Context pack != transcript/history** — a minimal phase-restoration packet
  with `restore` and `avoid` fields.
- **StateDelta != note-taking** — only the cognitive deltas that change the
  *next* response, with evidence refs.

The boundary exists to keep these distinctions enforceable in one owned place,
rather than diffused across Hermes upstream code where they would erode.

## Decision summary

| Question | Decision |
| --- | --- |
| Long-term home | A standalone repository, owned by the `#contextops` lane. |
| Current home | Repo-local module `contextops/` inside the Hermes repo (prototype proximity, not ownership). |
| Hermes coupling | `#hermes-main` holds at most a thin, stable adapter/shim — and only if live integration is approved (roadmap Milestone 8). |
| Import direction | ContextOps core never imports Hermes. Hermes may import the published ContextOps package. |
| Trigger to extract | After the MVP acceptance checklist in `epistemic-state-engine.md` is fully GO (roadmap fan-in card). |

ContextOps lives in this repo *now* only because the prototype needs Hermes
session/runtime evidence as fixtures. That is proximity, not ownership. Every
interface is designed so the core lifts out cleanly.

## Extraction skeleton (added)

A minimal, contained extraction/productization skeleton now exists in-repo so
the boundary is concrete rather than purely planned. It does **not** move the
existing `contextops/` prototype and adds no behavior to Hermes core:

- `packages/contextops_ese/` — standalone package skeleton for distribution
  `contextops-ese`, import root `contextops_ese`, `src/`-layout. Contains a
  dependency-free, harness-free core (`Observation`, `ContextPack`,
  `PreviewConfig`, `build_context_pack_preview`, `safe_ref`) plus tests that
  prove no raw transcripts, absolute paths, or raw ids reach a context pack
  and that injection is disabled by default.
- `plugins/context_engine/contextops/` — thin Hermes adapter skeleton. It
  imports `contextops_ese` *optionally* and fails closed (returns `None`) if
  the package is missing, disabled, fed an invalid schema, produces unsafe
  output, or hits a storage error. Defaults are `enabled=false`,
  `preview=true`, `inject=false`. It never calls `gateway/run.py` or
  `agent/prompt_builder.py` and performs no dispatch, memory write, or
  prompt injection.

This skeleton is the seed for the "Target" layout below; the prototype
`contextops/` module and `tests/contextops/` are untouched and their planned
migration is still governed by the gated steps in "Migration steps".

### Naming decision: `contextops_ese` skeleton vs `contextops` target

There is a real naming tension between three names now present in the repo:

| Name | Where | What it is |
| --- | --- | --- |
| `contextops` (import root + dir) | `contextops/`, `tests/contextops/` | the **prototype** module, in-repo today |
| `contextops_ese` (import root) / `contextops-ese` (distribution) | `packages/contextops_ese/` | the standalone **extraction skeleton** |
| `contextops` (repo + distribution) | future standalone repo | the **target** name in "Decision summary" |

**Decision.** The extraction skeleton is deliberately named `contextops_ese`
(import root `contextops_ese`, distribution `contextops-ese`) — *not*
`contextops` — for one concrete reason: two packages cannot share the
`contextops` import root inside a single repo, and the prototype already owns
it. The `_ese` suffix ("Epistemic State Engine") is a **prototype-phase
disambiguator**, not the long-term name. It lets the harness-free core and the
prototype coexist for side-by-side development without an import collision.

This does **not** change the "Decision summary": the *target* standalone
repository and distribution remain canonically `contextops` with import root
`contextops`. At migration (step 5 below), the skeleton is renamed by dropping
the `_ese` suffix as it merges into the extracted core; the adapter's
`package: contextops_ese` config key (see `adapter.py`) is updated to
`contextops` at the same step. No code outside `packages/contextops_ese/` and
`plugins/context_engine/contextops/` depends on the `_ese` name today, so the
rename stays a contained, single-step change. Until then, `contextops_ese` is
the correct and intentional name for the in-repo skeleton — reviewers should
not treat the suffix as drift.

## Proposed standalone repo name/path

- **Repository name:** `contextops`
  - Rationale: the prototype already uses `contextops` as its single top-level
    import root (`from contextops.context_pack import ...`). Keeping the repo
    name equal to the import root means extraction needs **zero import
    rewrites** in the core package.
- **Distribution / package name:** `contextops` on the internal index
  (PyPI-compatible metadata; no public publish required for MVP).
- **Import root:** `contextops` (unchanged from today).
- **Suggested clone path once extracted:** a sibling of the Hermes checkout,
  e.g. `~/.hermes/contextops/`, so neither repo nests inside the other.
- **Lane ownership:** the `#contextops` Kanban lane. `origin` and `return_to`
  for all related cards stay `Devhub/#contextops` (roadmap "Required return
  path").

## Package layout

### Today (repo-local prototype, inside the Hermes repo)

This is the **current on-disk state** — described for reference only. Do not
reshape it as part of this task.

```text
hermes-agent/                      # Hermes repo
  contextops/                      # repo-local ContextOps module
    __init__.py                    # public surface re-exports
    models.py                      # Event, Thread, Tension, ContextPack, StateDelta
    store.py                       # file-backed JSONL/YAML store
    router.py                      # cognitive router
    context_pack.py                # context pack builder
    extractor.py                   # state delta extractor
    heat.py                        # (roadmap Milestone 6) heat/lifecycle rules
    cli.py                         # (roadmap) contextops CLI entrypoint
    hermes_adapter.py              # read-only Hermes record -> Event mapper
    hydrate.py                     # read-only ChannelWorkingState hydration preview
  tests/contextops/
    test_models.py  test_store.py  test_router_contracts.py
    test_context_pack.py  test_state_delta_update.py
    test_hermes_adapter.py  test_hydrate.py
    fixtures/
  docs/contextops/
    epistemic-state-engine.md
    standalone-boundary.md         # this document
  docs/plans/
    2026-05-17-contextops-epistemic-state-engine-roadmap.md
```

### Target (standalone `contextops` repository)

The future layout splits the package into a Hermes-free **core** and a clearly
isolated **integration** subpackage. The core never imports Hermes; the
integration subpackage holds only read-only adapters and depends on Hermes via a
declared *optional extra*.

```text
contextops/                        # standalone repo
  pyproject.toml                   # package metadata; no hermes runtime dep in [project.dependencies]
  README.md
  contextops/                      # import root (unchanged)
    __init__.py                    # public surface re-exports
    models.py
    store.py
    router.py
    context_pack.py
    extractor.py
    heat.py
    cli.py
    integration/                   # all Hermes-facing code lives here, isolated
      __init__.py
      hermes_adapter.py            # read-only Hermes record -> Event mapper
      hydrate.py                   # read-only ChannelWorkingState hydration preview
  tests/
    contextops/                    # core tests (offline, no Hermes import)
    integration/                   # adapter/hydrate tests, fixture-driven
    fixtures/
  docs/
    epistemic-state-engine.md
    standalone-boundary.md
    roadmap.md
```

Moving `hermes_adapter.py` and `hydrate.py` under `contextops/integration/` is
the only structural change versus today, and it is **deferred to the migration
step** — this task does not perform it. The core modules (`models`, `store`,
`router`, `context_pack`, `extractor`, `heat`) keep their paths exactly.

## Import policy

The boundary is enforced as a one-directional import rule:

1. **ContextOps core must not import Hermes.** Core modules (`models`, `store`,
   `router`, `context_pack`, `extractor`, `heat`, `cli`) import only the Python
   standard library, ContextOps siblings, and small declared third-party deps
   (e.g. Pydantic, PyYAML). A core module importing anything under a Hermes
   namespace is a boundary violation and a review BLOCK.
2. **Hermes-facing code is quarantined.** Everything that knows about Hermes
   record shapes or `ChannelWorkingState` lives in `contextops/integration/`.
   Today that is `hermes_adapter.py` and `hydrate.py`; they sit at the repo top
   level only because the integration subpackage does not exist yet.
3. **Adapters depend on *shapes*, not on Hermes imports.** `hermes_adapter.py`
   already takes a plain `dict` record and never imports a Hermes module — that
   is the pattern. Integration code consumes duck-typed mappings/protocols so
   the core stays installable with no Hermes present.
4. **Hermes may import the published ContextOps package**, never the reverse.
   Hermes code uses only the public surface re-exported from
   `contextops/__init__.py` (`build_context_pack`, `build_hydration_preview`,
   `route_context_event`, `extract_state_deltas`, the model classes, etc.).
   Hermes must not import private helpers (leading-underscore names such as
   `_load_seed`, `_pressure_heat`).
5. **Optional dependency direction.** In the standalone `pyproject.toml`, Hermes
   is never a hard dependency. If integration tests need Hermes fixtures, that
   is an optional extra (`pip install contextops[hermes-integration]`) used in
   CI only, never required to install or run the core.
6. **No control-plane assumptions.** Per the roadmap, ContextOps core stays free
   of gateway dispatch, Hermes durable-memory mutation, Obsidian/Qdrant/Neo4j
   writes, and any non-ContextOps control-plane assumptions.

A lightweight enforcement test (added during migration, not now) can assert that
no module under `contextops/` except `contextops/integration/` imports a Hermes
namespace.

## Integration contract with Hermes

The Hermes ↔ ContextOps interface is **read-only and dry-run** for the entire
prototype phase. It has three surfaces:

### 1. Inbound: Hermes evidence → ContextOps Events

- Entry point: `hermes_record_to_event` / `hermes_records_to_events`.
- Hermes hands ContextOps **plain record dicts** (session/event-like). ContextOps
  treats each record as immutable input — read, never written.
- Safety guarantees enforced by the adapter today and part of the contract:
  - `Event.refs` holds only short structured pointers (`message:`, `session:`,
    `channel:`, `hermes:` namespaces, or benign hashtags) — never raw transcript
    content, filesystem paths, or secret-like material.
  - Oversized text is truncated to an excerpt; the full transcript is referenced
    by a `hermes:transcript:<id>` safe ref, not embedded.
  - Metadata is allowlisted and secret-scrubbed (fail-closed).
- This keeps the **Context pack != transcript/history** distinction intact at
  the boundary: Hermes transcripts never flow into ContextOps as raw history.

### 2. Outbound: ContextOps → Hermes hydration preview

- Entry point: `build_hydration_preview` / `render_hydration_preview` and the
  `contextops hydrate-preview` CLI.
- Output is a `ChannelWorkingState`: selected threads/tensions, a context pack
  (`restore` + `avoid`), and explicitly **excluded** candidates with reasons
  (`stale`, `contaminating`, `low_score`).
- Mode is fixed: `dry-run/read-only: no gateway restart, no memory write, no
  message dispatch` (`HYDRATION_AUTHORITY`). The preview never dispatches.
- ContextOps returns a packet for Hermes to inspect. It does not mutate Hermes
  state, does not write durable memory, and does not call the gateway.

### 3. Authority ranking

When ContextOps-derived context meets live Hermes state, the authority ranking
in `epistemic-state-engine.md` governs. The latest explicit user message and the
active ContextContract/TaskContract outrank any ContextOps context pack or
compaction. ContextOps output is background bias; it never overrides a live user
correction or active scope.

### Contract stability rule

The three entry points above (`hermes_record_to_event`,
`hermes_records_to_events`, `build_hydration_preview`,
`render_hydration_preview`, plus the model classes) are the **stable contract**.
Their signatures and the safe-ref / read-only guarantees may not change without
a `#contextops` lane review. Everything else in the package is internal and may
be refactored freely.

## What stays in Hermes as adapter/shim

Long-term, **the goal is that nothing ContextOps-specific stays embedded in
Hermes upstream `main`.** Hermes consumes ContextOps as an installed package.

If live integration is later approved (roadmap Milestone 8 — a hard stop
requiring separate operator approval), the *only* Hermes-resident code is a
minimal, stable shim:

- **A thin call site**, behind a feature flag that is **disabled by default**,
  that (a) collects Hermes session records, (b) calls the published ContextOps
  entry points, and (c) consumes the returned preview/pack.
- **No ContextOps core logic** — no routing, no heat math, no context-pack
  construction, no extraction — lives in Hermes. Those stay in the `contextops`
  package.
- The shim depends on the published package's public surface only.
- Shadow mode first: build packs without injecting; live opt-in is per
  lane/channel with a rollback switch (roadmap Milestone 8).

Until Milestone 8 is approved, **no shim exists in Hermes at all**. The current
`hermes_adapter.py` and `hydrate.py` are ContextOps-owned integration code that
happens to sit in the Hermes repo for prototype proximity — they are *not* a
Hermes shim and will move into the standalone repo's `contextops/integration/`
during migration.

Explicit statement of the boundary:

- **`#contextops`** is independent and repo-local long-term: it owns the
  ContextOps repo, the Epistemic State Engine object model, router/context-pack/
  extractor behavior, Thread/Tension/Heat semantics, the evaluation rubric, and
  all prototype storage and experiments.
- **`#hermes-main`** carries only minimal, stable integration if and when it is
  needed — a flagged shim calling the published package — and never ContextOps
  core logic. `#hermes-main` does **not** own ContextOps and ContextOps work is
  never folded into the Hermes-main memory/compaction track.

## Migration steps

These steps are **planned, not executed by this task**. Each maps to roadmap
gating and the `#contextops` lane review path. None should run before the MVP
acceptance checklist in `epistemic-state-engine.md` is fully GO.

1. **Gate.** Confirm the MVP acceptance checklist (`epistemic-state-engine.md`)
   is fully checked and the roadmap fan-in card returned GO. Extraction before
   GO is premature.
2. **Quarantine integration code in place.** Inside the Hermes repo, move
   `contextops/hermes_adapter.py` and `contextops/hydrate.py` into
   `contextops/integration/`, update `contextops/__init__.py` re-export paths,
   and adjust `tests/contextops/`. This is a separate, reviewed `#contextops`
   card — verified by `pytest tests/contextops -q` staying green.
3. **Add a boundary enforcement test.** Assert no module outside
   `contextops/integration/` imports a Hermes namespace. Reviewed `#contextops`
   card.
4. **Create the standalone `contextops` repository.** Initialize with
   `pyproject.toml` (import root `contextops`, no Hermes runtime dependency;
   `hermes-integration` optional extra). Repo owned by the `#contextops` lane.
5. **Move the package, tests, and docs** into the new repo, preserving git
   history where practical (e.g. `git filter-repo` / subtree split). Layout per
   "Target" above. Core module paths are unchanged, so no core import rewrites.
6. **Move ContextOps docs** (`epistemic-state-engine.md`, this file, the
   roadmap) into the standalone repo's `docs/`. Leave at most a one-line pointer
   in the Hermes repo if discoverability requires it.
7. **Wire CI in the new repo:** offline `pytest` only, no paid/remote calls
   (roadmap implementation guardrails). The `hermes-integration` extra runs only
   the fixture-driven adapter tests.
8. **Publish to the internal index** so Hermes (and other agents/apps) can
   `pip install contextops`.
9. **Remove ContextOps from the Hermes repo.** Delete `contextops/` and
   `tests/contextops/` from Hermes. If/when Milestone 8 is approved, replace
   them with the minimal flagged shim only — nothing more.
10. **Update the `#contextops` lane record** with the new repo location;
    keep `origin`/`return_to` as `Devhub/#contextops`.

Until step 1's gate is met, ContextOps stays repo-local and this document is the
standing record of intent — it keeps the boundary owned and explicit so the
prototype never silently merges into Hermes upstream `main`.

## Verification

This task is documentation-only. Verification performed:

- `docs/contextops/standalone-boundary.md` exists.
- Markdown code fences are balanced (every opening code fence has a close).
- No prototype Python or tests under `contextops/` or `tests/contextops/` were
  created, modified, or reformatted.
- No broad test suite was run (none was needed for a docs-only change).

To re-verify:

```bash
test -f docs/contextops/standalone-boundary.md && echo "file: OK"
[ $(grep -c '^```' docs/contextops/standalone-boundary.md) -eq $(( $(grep -c '^```' docs/contextops/standalone-boundary.md) / 2 * 2 )) ] && echo "fences: balanced"
git status --porcelain docs/contextops/standalone-boundary.md
```

## Review checklist

For the `#contextops` reviewer (`ccreviewer`) and future agents:

- [ ] Only `docs/contextops/standalone-boundary.md` was added; no other file was
      changed (no `git diff` outside this doc).
- [ ] Existing dirty/untracked ContextOps prototype files were not overwritten
      or reformatted.
- [ ] The doc names a proposed standalone repo (`contextops`) and path.
- [ ] The doc specifies package layout (current + target).
- [ ] The doc specifies a one-directional import policy.
- [ ] The doc specifies the read-only/dry-run integration contract with Hermes.
- [ ] The doc states what stays in Hermes as an adapter/shim (minimal, flagged,
      or nothing pre-Milestone 8).
- [ ] The doc lists ordered migration steps gated on MVP GO.
- [ ] The doc explicitly states `#contextops` is independent/repo-local
      long-term and `#hermes-main` carries only minimal stable integration.
- [ ] Terminology preserved: Thread != topic, Heat != recency,
      Compaction != summary, Context pack != transcript/history,
      StateDelta != note-taking.
- [ ] Markdown fences balanced; doc is operational and reviewable.
- [ ] No broad code moves proposed for *this* card — moves are deferred to the
      migration steps and their own reviewed cards.

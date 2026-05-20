# contextops-ese

Standalone, harness-agnostic **cognitive-state middleware**.

```
Event -> Thread / Tension / EpistemicMode -> StateDelta -> ContextPack
```

- **Distribution name:** `contextops-ese`
- **Import root:** `contextops_ese`
- **Layout:** `src/` (this directory is the future standalone repo root)

This package is the extraction/productization skeleton for the ContextOps
Epistemic State Engine. It lives at `packages/contextops_ese/` inside the
Hermes repo today purely for prototype proximity — it is **not** Hermes core
and never imports any harness.

## Scope

A minimal, dependency-free core that turns observed evidence into a **safe
context pack preview**:

- `Observation` — one unit of harness-agnostic evidence.
- `ContextPack` — a compact `restore` / `avoid` / `refs` contract.
- `PreviewConfig` — fail-safe behaviour flags.
- `build_context_pack_preview()` — builds a safe pack.
- `safe_ref()` — deterministic, opaque ref tokens.

## Non-goals

ContextOps/ESE is **not**:

- generic Memory or RAG,
- a transcript store or conversation summary,
- a Hermes core feature.

A context pack is **not** a transcript; a `StateDelta` is **not** note-taking;
`Thread != topic`; `Heat != recency`; `Compaction != summary`.

## Preview-first, fail-closed behaviour

`PreviewConfig` defaults are deliberately inert:

| flag | default | meaning |
| --- | --- | --- |
| `enabled` | `False` | engine off unless a harness opts in |
| `preview` | `True` | build packs for inspection only |
| `inject` | `False` | never write a pack into a live prompt |
| `include_raw_transcript` | `False` | transcripts never enter a pack |
| `include_raw_ids` | `False` | raw ids never enter a pack |
| `include_paths` | `False` | filesystem paths never enter a pack |

The builder **fails closed**: it raises `ValueError` on empty input or any
signal carrying an absolute path, and `Observation.raw_text` is never copied
into a `ContextPack`.

## Safe refs

Raw ids are replaced by deterministic opaque tokens (`ref:<sha1[:12]>`) via
`safe_ref()`, so packs cannot leak provider/session/message ids downstream.

## Harness adapters

The core is harness-agnostic. Each harness adapts *to* it; the core never
imports a harness. Intended harnesses: Hermes, Claude Code, Codex/OpenCode,
Kanban workers, AgentFlow-style supervisors.

The Hermes adapter skeleton lives at
`plugins/context_engine/contextops/` in the Hermes repo. It imports this
package optionally and fails closed if it is missing, disabled, fed an
invalid schema, or produces unsafe output.

## Tests

```bash
pytest packages/contextops_ese/tests -q
```

Tests prove no raw transcripts, no absolute paths, and no raw ids reach a
context pack, and that injection is disabled by default.

## TODO

- This is an extraction *skeleton*. Broader ESE logic (router, heat,
  extractor) is intentionally not copied here yet — see
  `docs/contextops/standalone-boundary.md` for the migration plan.

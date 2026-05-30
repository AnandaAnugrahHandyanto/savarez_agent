# RFC: Tiered Vector Memory and Dreaming Organizer

## Goals

Hermes currently injects curated `MEMORY.md` and `USER.md` entries as bounded text snapshots. This RFC adds a safe, opt-in local memory index that improves recall order and prepares Hermes for faster semantic search across profile-scoped memory.

## Phase 1 shipped in this branch

- Add a dependency-light SQLite memory index at `<HERMES_HOME>/memories/memory_index.sqlite3`.
- Index built-in memory entries with deterministic local hashed embeddings (`local-hash`) so it works without API keys or network calls.
- Track per-entry metadata: profile, namespace, target (`memory` or `user`), content hash, tier (`hot`, `warm`, `cold`), sensitivity, use count, relevance, last used, created, updated, and embedding.
- Preserve profile isolation by default. Rebuilding another profile is ignored unless `memory.tiered.cross_profile_enabled` is true and optional `authorized_profiles` allows it.
- Skip sensitive entries rather than storing cleartext in the index when threat-pattern or token/secret-like content is detected.
- Add non-destructive CLI commands:
  - `hermes memory index` — status and counts.
  - `hermes memory rebuild [--profiles a,b]` — backfill from `MEMORY.md`/`USER.md`.
  - `hermes memory dream [--apply]` — propose/apply tier metadata changes only; never rewrites memory files.
- Add optional prompt snapshot ordering behind `memory.tiered.enabled`: active profile entries are rebuilt at session start and ordered hot → warm → cold while keeping the frozen snapshot/prefix-cache invariant.
- Record retrieval usage (`use_count`, `last_used_at`, best relevance) when `search_index()` returns hits; index rebuilds preserve `updated_at` for unchanged entries so dreaming can still identify stale memories.

## Retrieval pipeline

Phase 1 exposes `tools.memory_index.search_index()` for internal callers. Ranking combines:

1. local hashed-vector cosine score,
2. exact token overlap,
3. recency,
4. frequency (`use_count`),
5. tier boost (`hot` > `warm` > `cold`).

Hot and warm are searched by default. Cold entries are only returned when requested and the combined score clears `memory.tiered.cold_min_score`.

## Dreaming organizer

The dream pass is intentionally conservative:

- proposes/promotes `hot` when use count is high or memory was updated/used recently,
- keeps useful less-recent entries `warm`,
- demotes unused old entries to `cold`,
- reports duplicate content hashes and stale candidates,
- never deletes, summarizes, or rewrites `MEMORY.md`/`USER.md`.

Future phases can wire this into cron/curator with a review report artifact before any destructive or summarizing action.

## Privacy and cross-profile safety

Default behavior is profile-local only. Aggregate indexing requires explicit config:

```yaml
memory:
  tiered:
    enabled: true
    cross_profile_enabled: true
    authorized_profiles: [anulu, researcher]
```

Even with aggregate indexing, sensitive entries are skipped from the local DB. The initial implementation does not expose a cross-profile tool to the model; it only provides CLI/admin rebuild and internal APIs.

## Migration/backfill

No migration runs automatically while the feature is disabled. To backfill the active profile:

```bash
hermes config set memory.tiered.enabled true
hermes memory rebuild
hermes memory index
```

To review tier changes:

```bash
hermes memory dream
hermes memory dream --apply   # metadata only; safe/non-destructive
```

## Future phases

1. Add pluggable embedding backend interface for hosted/local embedding models while keeping `local-hash` as fallback.
2. Wire `search_index()` into memory prefetch/tool recall with usage updates (`last_used_at`, `use_count`).
3. Add a scheduled dreaming job that emits review reports/diffs and can create curator tasks.
4. Extend indexing to session summaries once a summarization privacy policy is defined.
5. Add admin UI/dashboard visibility for tier counts, stale candidates, and duplicate reports.

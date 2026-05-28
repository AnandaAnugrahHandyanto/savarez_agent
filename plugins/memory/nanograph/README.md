# nanograph memory provider

Local embedded property-graph memory for Hermes, backed by
[nanograph](https://github.com/nanograph/nanograph) (Rust core on Arrow/Lance).

- **On-device.** No server, no cloud. The graph lives under `$HERMES_HOME`.
- **Recall.** Full-text + graph traversal today; optional local-LM-Studio
  semantic / hybrid recall when an embedding provider is configured.
- **Audit trail.** Every write lands in nanograph's ACID store with a CDC
  mutation ledger — a reviewable record of what the agent committed to memory.

## Install

The provider talks to nanograph through the in-process `nanograph_py` PyO3
module. Build/install it into the same environment as Hermes:

```bash
# from a checkout of the nanograph repo
maturin develop -m crates/nanograph-py/Cargo.toml   # dev
# or, once published:
pip install nanograph-py
```

`is_available()` returns False (provider stays dormant) if `nanograph_py`
isn't importable, so it's safe to ship the plugin without the binding present.

## Enable

```yaml
# $HERMES_HOME/config.yaml
memory:
  provider: nanograph
plugins:
  nanograph:
    db_path: $HERMES_HOME/nanograph/memory.nano   # omit for default
    recall_mode: fulltext        # fulltext | semantic | hybrid
    recall_limit: 6
    persist_turns: true
```

Or run `hermes memory setup` and pick `nanograph`.

## Semantic recall (opt-in)

1. Uncomment the `embedding: Vector(768)? @embed(statement) @index` line in
   `schema.pg` (match the dim to your embedding model).
2. Point nanograph's embedding config at a local LM Studio endpoint
   (OpenAI-compatible), so content never leaves the machine.
3. Set `recall_mode: semantic` (or `hybrid`) and uncomment the matching query
   in `queries.gq`. Backfill existing rows with `nanograph embed`.

## Tool

Exposes one tool, `memory_graph`, with actions `recall` / `about` / `recent` /
`remember`. The schema and queries are git-versioned in `schema.pg` and
`queries.gq` (schema-as-code).

## Notes

- The key property is `slug`, never `id` — `id` is nanograph's reserved
  internal node identifier.
- `sync_turn()` writes on a daemon thread; the `nanograph_py` binding releases
  the GIL during database work, so turn persistence is non-blocking.

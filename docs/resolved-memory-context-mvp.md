# Resolved Memory Context MVP

## Goal

Ship a small, reversible memory-context improvement for Hermes Agent:

1. Audit raw recalled memory context.
2. Build a compact packet from that context.
3. Mark possible conflicts passively without deleting or auto-resolving memories.

This MVP is intentionally local/shadow-first. It must not change production behavior unless explicitly enabled.

## Non-goals

- No Qdrant/Memgraph integration.
- No sleep-cycle/drainage changes.
- No voice pipeline changes.
- No automatic memory deletion, merge, or conflict resolution.
- No Hostinger/OVH runtime changes.

## Architecture

### Baseline path

`MemoryManager.prefetch_all()` returns raw provider context.
`run_agent.py` injects that context into the current user message via `build_memory_context_block()`.
The system prompt remains byte-stable for prompt caching.

### MVP path

`build_memory_context_block(raw_context, packet_builder_enabled=True)`:

1. Sanitizes any nested `<memory-context>` fences.
2. Parses raw context into sections.
3. Builds a structured packet:
   - `facts`
   - `preferences`
   - `operational_state`
   - `conflicts` (passive markers only)
   - `excluded_context`
   - `source_precedence`
4. Renders only the resolved packet inside the memory fence.

When `packet_builder_enabled=False`, output must remain compatible with the existing raw memory-context block.

## Config gate

Default behavior is off.

```yaml
memory:
  packet_builder:
    enabled: false
```

Runtime integration must read this gate and pass it into `build_memory_context_block()`.

## Gates

- Gate 1: `memory.packet_builder.enabled` defaults to `false`.
- Gate 2: with gate off, memory block remains raw and does not include `# Resolved Memory Context`.
- Gate 3: with gate on, resolved packet replaces raw context; it must not duplicate raw + resolved.
- Gate 4: system prompt is not modified; memory remains user-message injection only.
- Gate 5: tests cover sanitization, packet sections, conflict markers, default-off behavior, and enabled behavior.

## Abort criteria

- Abort activation if resolved packet grows more than 10% over raw context on real fixtures.
- Abort automatic conflict resolution; only passive markers are allowed in this MVP.
- Abort if prompt caching requires system-prompt mutation.
- Abort if config gating requires broad changes outside `run_agent.py`, `agent/memory_manager.py`, docs, and tests.

## Fixtures

Minimum local fixtures:

1. Plain raw context: preserves raw path when disabled.
2. Provider-tagged context: `[Provider: honcho]`, `[Provider: builtin]`.
3. Sectioned context: `# Facts`, `# Preferences`, `# Operational State`, `# Excluded Context`.
4. Conflict marker context: two model/path/identity values.
5. Pre-wrapped context: nested `<memory-context>` is stripped safely.

## Rollback

Set:

```yaml
memory:
  packet_builder:
    enabled: false
```

or remove the key. Default false restores raw-context behavior.

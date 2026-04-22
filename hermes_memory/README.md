# hermes_memory

Bundled implementation of Hermes **curated persistent memory** and **memory provider orchestration**.

## Contents

| Module | Role |
|--------|------|
| `memory_provider.py` | Abstract `MemoryProvider` base class for plugins (`plugins/memory/<name>/`). |
| `memory_manager.py` | `MemoryManager`, `build_memory_context_block`, `sanitize_context` — wires providers into `run_agent`. |
| `builtin_memory_tool.py` | `MemoryStore`, `MEMORY.md` / `USER.md` I/O, `memory_tool` handler, `MEMORY_SCHEMA`. |

Tool **registration** (`registry.register`) stays in `tools/memory_tool.py` so `tools/` auto-discovery continues to load the `memory` tool exactly once.

## Related (not in this folder)

- `plugins/memory/` — optional backends (Honcho, Mem0, …).
- `run_agent.py` — session wiring, prefetch, background memory review.
- `hermes_state.py` — **session transcript** storage (separate from curated memory).

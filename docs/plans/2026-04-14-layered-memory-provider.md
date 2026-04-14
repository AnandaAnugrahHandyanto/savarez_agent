# Layered Memory Provider Implementation Plan

> For Hermes: implement Phase 1 MVP of a hierarchical JARVIS memory system as a single local external memory provider.

Goal: add a local always-available `layered` memory provider that gives Hermes a structured long-term memory bus with distinct layers for identity, semantic memory, episodic memory, reflection, archive, and procedural index metadata.

Architecture: implement one repo-shipped memory plugin under `plugins/memory/layered/` with a small local SQLite store and FTS-backed retrieval. Keep built-in memory as the hot identity layer, mirror explicit built-in writes into the provider, and use provider hooks to persist episodic checkpoints and session summaries. This Phase 1 MVP is local-first, deterministic, and intentionally avoids embeddings or heavy background workers.

Tech Stack: Python, sqlite3, FTS5, Hermes MemoryProvider interface, pytest.

---

## Task 1: Add failing tests for provider discovery and local initialization
Objective: prove the new provider is discoverable, loadable, and initializes a local store under the active Hermes home.

Files:
- Create: `tests/agent/test_layered_memory_provider.py`
- Create: `plugins/memory/layered/plugin.yaml`
- Create later: `plugins/memory/layered/__init__.py`

Steps:
1. Write tests that expect `discover_memory_providers()` to include `layered`.
2. Write tests that expect `load_memory_provider("layered")` to return an available provider.
3. Write tests that initialize the provider with a temp `HERMES_HOME` and assert the database file is created.
4. Run only the new tests and confirm RED.

Verification:
- `pytest tests/agent/test_layered_memory_provider.py -q`
- Expected before implementation: FAIL

## Task 2: Implement provider config and local SQLite store bootstrap
Objective: add the plugin metadata, config loading/saving, SQLite schema creation, and minimal system prompt block.

Files:
- Create: `plugins/memory/layered/__init__.py`
- Modify: `plugins/memory/layered/plugin.yaml`
- Modify: `hermes_cli/main.py` (provider help text if needed)

Steps:
1. Add `LayeredMemoryProvider` implementing `MemoryProvider`.
2. Add config loading from `memory.layered` and `save_config()` writing back to `config.yaml`.
3. Create a SQLite schema with a single `memory_items` table plus FTS virtual table.
4. Add `system_prompt_block()` with a short status summary only.
5. Re-run the provider discovery/init tests and confirm GREEN.

Verification:
- `pytest tests/agent/test_layered_memory_provider.py -q`

## Task 3: Implement built-in write mirroring and typed storage
Objective: make the provider persist stable facts into the correct memory layers when Hermes built-in memory is explicitly written.

Files:
- Modify: `plugins/memory/layered/__init__.py`
- Modify: `tests/agent/test_layered_memory_provider.py`

Steps:
1. Add tests for `on_memory_write()`.
2. Map built-in `target=user` to `identity_core`; map `target=memory` to `semantic`.
3. On `replace`, append a fresh record with a superseding marker rather than mutating history in place.
4. Re-run tests and confirm GREEN.

Verification:
- `pytest tests/agent/test_layered_memory_provider.py -q -k memory_write`

## Task 4: Implement episodic capture via `sync_turn()`, `on_pre_compress()`, and `on_session_end()`
Objective: persist active-work history without polluting the hot prompt.

Files:
- Modify: `plugins/memory/layered/__init__.py`
- Modify: `tests/agent/test_layered_memory_provider.py`

Steps:
1. Add tests for `sync_turn()` creating archive/turn records.
2. Add tests for `on_pre_compress()` creating an episodic checkpoint and returning a compact preservation note.
3. Add tests for `on_session_end()` creating a session recap entry.
4. Implement deterministic summarization heuristics using truncated recent messages only.
5. Re-run tests and confirm GREEN.

Verification:
- `pytest tests/agent/test_layered_memory_provider.py -q -k 'sync_turn or pre_compress or session_end'`

## Task 5: Implement retrieval and prefetch bundling
Objective: return a small, structured memory bundle suitable for Hermes prompt injection.

Files:
- Modify: `plugins/memory/layered/__init__.py`
- Modify: `tests/agent/test_layered_memory_provider.py`

Steps:
1. Add tests for `prefetch()` returning layered sections.
2. Implement retrieval priority: `identity_core`, then `semantic`, then recent `episodic`, then `reflection`.
3. Use FTS + simple recency ordering + per-layer limits from config.
4. Keep the prefetch result compact and deterministic.
5. Re-run tests and confirm GREEN.

Verification:
- `pytest tests/agent/test_layered_memory_provider.py -q -k prefetch`

## Task 6: Integrate repo surfaces and run regression checks
Objective: ensure the provider is visible in repo-shipped provider surfaces and does not regress existing memory behavior.

Files:
- Modify: `hermes_cli/main.py` (provider help text list)
- Optionally modify: `hermes_cli/web_server.py` only if the static provider option list is touched in this pass
- Modify: `tests/agent/test_memory_provider.py` if needed for plugin discovery expectations

Steps:
1. Update any static provider lists that should mention `layered`.
2. Keep scope tight: only patch surfaces that already enumerate built-in providers in repo code.
3. Run targeted provider tests.
4. Run existing memory manager/provider tests.

Verification:
- `pytest tests/agent/test_layered_memory_provider.py tests/agent/test_memory_provider.py tests/agent/test_memory_user_id.py -q`

## Phase 1 MVP acceptance criteria
- A new `layered` provider is discoverable by Hermes.
- It is local-only and always available on standard Python + SQLite.
- Built-in explicit memory writes are mirrored into the provider with typed layers.
- Turn history, compression checkpoints, and session summaries are persisted.
- `prefetch()` returns a compact layered bundle instead of a flat blob.
- No changes are required to built-in memory behavior to activate the provider.
- Targeted memory tests pass.

## Out of scope for this phase
- Embeddings or vector databases
- Background workers
- Full procedural-memory/skill promotion pipeline
- Importance learning beyond simple heuristics
- Reflection auto-extraction from complex reasoning traces
- UI overhauls for all memory provider selector surfaces

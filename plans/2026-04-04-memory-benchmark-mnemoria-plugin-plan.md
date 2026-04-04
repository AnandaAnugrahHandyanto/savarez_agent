# Memory Benchmark Suite + Mnemoria Plugin PR Plan

**Date:** 2026-04-04
**Author:** Moonsong
**Status:** Draft — awaiting build start
**Reference:** Builds on `plans/2026-04-03-benchmark-capability-aware-memory-comparison.md`

---

## Executive Summary

Two coordinated PRs to hermes-agent:

| PR | Branch | Purpose | Gate |
|----|--------|---------|------|
| **PR 1** | `pr/benchmark-suite` (continue) | Benchmark all 7 existing memory plugins | All 7 plugins run without import errors |
| **PR 2** | `pr/mnemoria-plugin` (new) | Add `mnemoria` as the 8th official memory plugin | Passes benchmark suite, MemoryProvider interface |

**Key decision — naming:** `unified_memory` → **`mnemoria`** (plugin name: `plugins/memory/mnemoria/`). Distinctive, memory-themed, matches honcho/mem0 naming convention. NOT "memory-agent" or "actr-memory."

**Key decision — ori-mnemos-ref:** Design inspiration only. No integration. Mnemoria is a native Python implementation, not a wrapper.

**Key decision — pr/benchmark-suite:** Do NOT push until ALL benchmarks are complete and verified.

---

## Context: The Memory Plugin Landscape

### The 7 Official Memory Plugins

| Plugin | Type | Key Capability | Benchmark Adapter? |
|--------|------|---------------|-------------------|
| `builtin` | File-based | MEMORY.md/USER.md (always on) | ❌ |
| `byterover` | CLI tool | Hierarchical knowledge tree, fuzzy→LLM search | ❌ |
| `hindsight` | Cloud/local | Knowledge graph, entity resolution, multi-strategy | ❌ |
| `holographic` | Local SQLite | FTS5, trust scoring, HRR compositional retrieval | ✅ |
| `honcho` | Cloud API | Cross-session user modeling, dialectic Q&A | ✅ |
| `mem0` | Cloud API | LLM fact extraction, semantic search, reranking | ❌ |
| `openviking` | Self-hosted | Tiered retrieval, filesystem hierarchy | ❌ |
| `retaindb` | Cloud API | Hybrid vector+BM25+rerank, 7 memory types | ❌ |

**Only 2 of 7 have benchmark adapters.** That's the gap PR 1 fills.

### Existing Code in pr/benchmark-suite (already written)

```
pr/benchmark-suite:
├── unified_memory/           # ~5,000 lines — ACT-R + PageRank + Hebbian + LinUCB
│   ├── store.py              # 959 lines — SQLite + ACT-R activation decay
│   ├── retrieval.py          # 916 lines — Personalized PageRank, multi-hop
│   ├── links.py              # 515 lines — Wiki-link graph, Tarjan SCC, NPMI
│   ├── bandit.py             # 283 lines — LinUCB query routing (RL on retrieval)
│   ├── ingestion.py          # 292 lines — dedup, memorability scoring
│   ├── hooks.py              # 168 lines — Icarus lifecycle hooks
│   └── benchmark_adapter.py  # adapter for BenchmarkableStore interface
├── tools/structured_memory/  # ~1,381 lines — simple native SQLite, fact-scoped
│   └── benchmark_adapter.py  # StructuredMemoryBenchmarkAdapter
├── benchmarks/               # Suites A-L + hotpotqa + locomo + longmemeval
│   ├── runner.py             # benchmark runner with backend registry
│   ├── interface.py          # BenchmarkableStore ABC
│   ├── backends/             # holographic_adapter, honcho_adapter
│   └── baseline/             # flat_store (trivial baseline)
├── hermes_cli/memory_layers.py  # 353 lines — recovered from aegis backup
│                                # hermes memory layers init/apply/update
└── tools/unified_memory_tool.py # 924 lines — 9 MCP tools
```

### Relationship: structured_memory vs unified_memory

These are **sibling systems, not competitors**:

- **`structured_memory`** (`tools/structured_memory/`) — lightweight native Python SQLite, fact-scoped, gauge tracking. Designed as a **simple adapter target** that backends like holographic can share via `StructuredMemoryBenchmarkAdapter`. NOT a standalone plugin.
- **`unified_memory`** → **`mnemoria`** — sophisticated multi-strategy engine. ACT-R decay + Personalized PageRank + Wiki-links + Hebbian co-occurrence + LinUCB routing + RL on retrieval. This is the **new plugin candidate**.

---

## PR 1 — Benchmark Suite (Continue pr/benchmark-suite)

### Purpose

Prove the benchmark framework is legitimate by demonstrating it can evaluate all 7 memory plugins fairly. Adds the 5 missing backend adapters.

### Non-Goals

- Does NOT add mnemoria as a plugin
- Does NOT modify any MemoryProvider implementation
- Does NOT change hermes-agent core memory logic

### What Already Exists in This PR

Everything listed above. The PR has 7 commits, 111 files, +27,732 lines. It is feature-complete for the existing backends.

### What Still Needs to Be Added

#### 5 Missing Backend Adapters

Each adapter goes in `benchmarks/backends/<name>_adapter.py` and exports:

```python
from benchmarks.interface import BenchmarkableStore

class <Name>BenchmarkAdapter(BenchmarkableStore):
    def __init__(self, config: dict = None):
        # Initialize the backend with optional config
        pass

    def store(self, content: str, category: str = "factual",
              scope: str = "global", importance: float = 0.5) -> None:
        ...

    def recall(self, query: str, top_k: int = 10,
               scope: Optional[str] = None) -> List[str]:
        ...

    def simulate_time(self, days: float) -> None:
        ...

    def simulate_access(self, content_substring: str) -> None:
        ...

    def consolidate(self) -> None:
        ...

    def get_stats(self) -> Dict[str, Any]:
        ...

    def reset(self) -> None:
        ...

    def reward_memory(self, memory_id: str, signal: float) -> None:
        ...  # optional, default no-op

    def explore(self, query: str, top_k: int = 20,
                 scope: Optional[str] = None) -> List[str]:
        ...  # optional, default recall fallback


BACKEND_NAME = "<name>"
BACKEND_CLASS = <Name>BenchmarkAdapter
BACKEND_CAPABILITIES = BackendCapabilities(
    # declare which capabilities this backend supports
)
```

Required adapters:

| Adapter | Plugin | Difficulty | Notes |
|---------|--------|-----------|-------|
| `byterover_adapter.py` | byterover | High | CLI-based, needs `brv` CLI installed. May need mock if CLI unavailable. |
| `hindsight_adapter.py` | hindsight | Medium | Has `hindsight-client` pip package. Local or cloud mode. |
| `mem0_adapter.py` | mem0 | Medium | Has `mem0ai` pip package. Cloud API key needed for live test. |
| `openviking_adapter.py` | openviking | Medium | Self-hosted server. Needs `OPENVIKING_ENDPOINT` configured. |
| `retaindb_adapter.py` | retaindb | Medium | Cloud API, `$20/month` account. Needs `RETAINDB_API_KEY`. |

Optional adapter:

| Adapter | Plugin | Difficulty | Notes |
|---------|--------|-----------|-------|
| `builtin_adapter.py` | builtin | Low | MEMORY.md/USER.md — may not be feasible to benchmark as a store/recall system. Decide: skip or mock. |

**Important fairness note (from existing plan):** Each adapter must honestly declare its capabilities via `BACKEND_CAPABILITIES`. If a backend doesn't support a feature (e.g., time simulation), the suite is **skipped** for that backend, not scored as failure. See `plans/2026-04-03-benchmark-capability-aware-memory-comparison.md` Section 4 for the `BackendCapabilities` dataclass spec.

#### Backend Capability Declarations

The existing plan (`plans/2026-04-03-benchmark-capability-aware-memory-comparison.md`) defines `BackendCapabilities` with these fields:

```python
@dataclass
class BackendCapabilities:
    universal_store_recall: bool = True
    time_simulation: bool = False
    access_rehearsal: bool = False
    consolidation: bool = False
    scopes: bool = False
    typed_facts: bool = False
    supersession: bool = False
    reward_learning: bool = False
    exploration: bool = False
    turn_sync: bool = False
    precompress_hook: bool = False
    session_end_hook: bool = False
    delegation_hook: bool = False
```

Each adapter in `benchmarks/backends/` must export this.

### Tasks for PR 1

- [ ] Add `benchmarks/backends/byterover_adapter.py`
- [ ] Add `benchmarks/backends/hindsight_adapter.py`
- [ ] Add `benchmarks/backends/mem0_adapter.py`
- [ ] Add `benchmarks/backends/openviking_adapter.py`
- [ ] Add `benchmarks/backends/retaindb_adapter.py`
- [ ] Add `BackendCapabilities` to `benchmarks/interface.py` (or create `benchmarks/capabilities.py`)
- [ ] Update `benchmarks/backends/__init__.py` to auto-register backends with capability declarations
- [ ] Add capability declarations to existing `holographic_adapter.py` and `honcho_adapter.py`
- [ ] Verify all 7 backends load without import errors: `python -c "from benchmarks.backends import *" ; print(BACKENDS.keys())`
- [ ] Run benchmark suite against all available backends: `python -m benchmarks.runner --backend all --suite a,b,c --runs 1`
- [ ] Update `benchmarks/README.md` with fairness principles (from existing plan Section 6)
- [ ] Add `benchmarks/backends/builtin_adapter.py` OR explicitly document why builtin is not benchmarkable
- [ ] Review `structured_memory` and `unified_memory` benchmark adapters — verify they still work after any changes
- [ ] Verify `hermes_cli/memory_layers.py` doesn't have import/syntax errors

### Merge Gate for PR 1

- All 7 plugin adapters load without import errors
- Benchmark runner executes without crashes
- No modification to existing MemoryProvider implementations
- CI passes (if applicable)

---

## PR 2 — Mnemoria Plugin (new branch: pr/mnemoria-plugin)

### Purpose

Add `mnemoria` as the 8th official hermes-agent memory plugin, implemented as a proper `MemoryProvider`. Demonstrate it competes favorably against the other 7 via the benchmark framework.

### Depends On

PR 1 must be merged first. Mnemoria's comparative benchmark results depend on the framework existing.

### What It Is

**Mnemoria** (renamed from `unified_memory`) is an adaptive, self-optimizing memory system that:

- Uses **ACT-R activation decay** for cognitively-plausible forgetting curves
- Uses **Personalized PageRank** on a memory graph for multi-hop retrieval
- Uses **Wiki-links + Hebbian co-occurrence** for associative connections
- Uses **LinUCB** to learn the best retrieval strategy per query type (RL on retrieval itself)
- Supports RL **reward signals** to reinforce useful memories
- Provides 9 MCP tools: write, recall, search, reflect, reward, explore, stats, consolidate, export_training

**What it is NOT:** A wrapper around ori-mnemos-ref. It's a native Python implementation that draws from the same cognitive science ideas (documented in `unified_memory/FUTURE.md` citing Ori, PLUR, Icarus).

### Naming Rationale

- Mnemoria (one word, memory-themed) — distinctive, pronounceable, memorable
- Matches naming convention of existing plugins: honcho, mem0, holographic, byterover
- NOT "memory-agent" (too generic) or "actr-memory" (descriptive but clunky)
- Plugin directory: `plugins/memory/mnemoria/`

### File Structure (Target — matches holographic/honcho pattern exactly)

```
plugins/memory/mnemoria/           # ← Source lives here (like holographic/, honcho/)
├── __init__.py                    # MnemoriaMemoryProvider + register(ctx)
├── plugin.yaml                    # Plugin metadata, pip dependencies
├── SKILL.md                       # User-facing documentation
├── store.py                       # ACT-R + SQLite (moved from unified_memory/)
├── retrieval.py                   # Personalized PageRank, multi-hop
├── links.py                       # Wiki-links, Hebbian, Tarjan SCC
├── bandit.py                      # LinUCB query routing
├── ingestion.py                   # Dedup, memorability scoring
├── hooks.py                       # Icarus lifecycle hooks
├── config.py                      # Mnemoria-specific config
├── schema.py                      # DB schema
├── types.py                       # Type definitions
├── intent.py                      # Intent detection
├── lifecycle.py                   # Lifecycle helpers
├── migrate.py                     # Migration tools
├── export.py                      # Training data export
├── tools/
│   └── mnemoria_tool.py           # 9 MCP tools
└── benchmarks/
    └── mnemoria_adapter.py        # BenchmarkableStore adapter
```

**Source location decision:** `plugins/memory/mnemoria/` (inside the plugin directory, matching holographic and honcho exactly). The `__init__.py` imports from `.store`, `.retrieval`, etc. — standard Python package relative imports.

### MemoryProvider Interface Implementation

The current `unified_memory/` has MCP tools (`tools/unified_memory_tool.py`) but is NOT yet a `MemoryProvider`. Mnemoria must implement:

```python
# plugins/memory/mnemoria/__init__.py
from agent.memory_provider import MemoryProvider

class MnemoriaMemoryProvider(MemoryProvider):
    name = "mnemoria"
    
    def is_available(self) -> bool:
        """Return True if mnemoria is installed and configured."""
        
    def initialize(self, session_id: str, **kwargs) -> None:
        """Initialize the store, run migrations."""
        
    def system_prompt_block(self) -> str:
        """Return memory context for system prompt."""
        
    def prefetch(self, query: str, *, session_id: str = "") -> str:
        """Recall relevant memories before each turn."""
        
    def sync_turn(self, user_content: str, assistant_content: str, 
                  *, session_id: str = "") -> None:
        """Ingest a completed turn."""
        
    def get_tool_schemas(self) -> List[Dict[str, Any]]:
        """Return 9 MCP tool schemas."""
        
    def handle_tool_call(self, tool_name: str, args: Dict[str, Any], 
                         **kwargs) -> str:
        """Dispatch to mnemoria tool implementation."""
        
    def on_turn_start(self, turn_number: int, message: str, **kwargs) -> None:
        """Hook: topic tracking, decision detection."""
        
    def on_session_end(self, messages: List[Dict[str, Any]]) -> None:
        """Hook: session summary extraction."""
        
    def on_pre_compress(self, messages: List[Dict[str, Any]]) -> str:
        """Hook: extract insights before context compression."""
        
    def on_delegation(self, task: str, result: str, 
                      *, child_session_id: str = "", **kwargs) -> None:
        """Hook: preserve useful delegation outcomes."""
        
    def on_memory_write(self, action: str, target: str, content: str) -> None:
        """Hook: mirror built-in memory writes to mnemoria."""
        
    def shutdown(self) -> None:
        """Clean shutdown."""
        
    def get_config_schema(self) -> List[Dict[str, Any]]:
        """Config fields for hermes memory setup."""
        
    def save_config(self, values: Dict[str, Any], hermes_home: str) -> None:
        """Write config to mnemoria's native location."""
```

### plugin.yaml

```yaml
name: mnemoria
version: 1.0.0
description: "Mnemoria — adaptive multi-strategy memory with ACT-R decay, Personalized PageRank retrieval, and RL query routing."
pip_dependencies:
  - numpy  # for HRR algebra, statistical operations
hooks:
  - on_turn_start
  - on_session_end
  - on_pre_compress
  - on_delegation
  - on_memory_write
```

### Renaming Tasks

- [ ] Rename `unified_memory/` → `mnemoria/` at repo root
- [ ] Rename `unified_memory/benchmark_adapter.py` → `mnemoria/benchmark_adapter.py`
- [ ] Rename `unified_memory/ARCHITECTURE.md` → `mnemoria/ARCHITECTURE.md` (update internal references)
- [ ] Rename `unified_memory/FUTURE.md` → `mnemoria/FUTURE.md` (update internal references)
- [ ] Rename `tools/unified_memory_tool.py` → `tools/mnemoria_tool.py`
- [ ] Rename `StructuredMemoryBenchmarkAdapter` → keep as-is (structured_memory is separate)
- [ ] Rename `UnifiedBenchmarkAdapter` → `MnemoriaBenchmarkAdapter`
- [ ] Update all import paths throughout codebase: `from unified_memory.*` → `from mnemoria.*`
- [ ] Update `benchmarks/runner.py` import: `from unified_memory.benchmark_adapter import UnifiedBenchmarkAdapter` → `from mnemoria.benchmark_adapter import MnemoriaBenchmarkAdapter`
- [ ] Update `benchmarks/backends/` auto-registration if applicable
- [ ] Update `hermes_cli/memory_layers.py` references to unified_memory
- [ ] Verify no remaining `unified_memory` references in codebase: `grep -r "unified_memory" --include="*.py" .`

### Plugin Implementation Tasks

- [ ] Create `plugins/memory/mnemoria/__init__.py` with `MnemoriaMemoryProvider`
- [ ] Create `plugins/memory/mnemoria/plugin.yaml`
- [ ] Create `plugins/memory/mnemoria/SKILL.md` (user-facing docs)
- [ ] Implement `is_available()` — check dependencies installed
- [ ] Implement `initialize()` — init store, run migrations
- [ ] Implement `system_prompt_block()` — inject memory context
- [ ] Implement `prefetch()` — Personalized PageRank recall
- [ ] Implement `sync_turn()` — conversation ingestion
- [ ] Implement `get_tool_schemas()` — 9 MCP tool schemas
- [ ] Implement `handle_tool_call()` — dispatch to tool implementation
- [ ] Implement all lifecycle hooks (`on_turn_start`, `on_session_end`, `on_pre_compress`, `on_delegation`, `on_memory_write`)
- [ ] Implement `get_config_schema()` + `save_config()` for `hermes memory setup`
- [ ] Implement `shutdown()`
- [ ] Add `benchmarks/backends/mnemoria_adapter.py` with `BACKEND_NAME = "mnemoria"`, `BACKEND_CLASS = MnemoriaBenchmarkAdapter`, and full `BACKEND_CAPABILITIES`
- [ ] Run benchmark suite: `python -m benchmarks.runner --backend mnemoria --suite all --runs 3`
- [ ] Verify mnemoria competes favorably on core track vs other plugins
- [ ] Document comparative results in `benchmarks/results/mnemoria-vs-all.md` (or similar)

### Testing Tasks

- [ ] `python -c "from mnemoria.store import MnemoriaStore; print('store OK')"`
- [ ] `python -c "from mnemoria.retrieval import fts5_search; print('retrieval OK')"`
- [ ] `python -c "from mnemoria.benchmark_adapter import MnemoriaBenchmarkAdapter; print('adapter OK')"`
- [ ] `python -c "from plugins.memory.mnemoria import MnemoriaMemoryProvider; print('provider OK')"`
- [ ] `python -m pytest tests/memory/test_mnemoria.py -x -q --tb=short` (if tests exist)
- [ ] `python -m pytest tests/benchmarks/ -x -q --tb=short`

### Merge Gate for PR 2

- Mnemoria passes the full benchmark suite (Suites A-L + hotpotqa + locomo + longmemeval)
- All MemoryProvider interface methods implemented and documented
- `plugin.yaml` and `SKILL.md` complete
- Benchmark adapter with full capability declaration
- Comparative results showing mnemoria's performance profile vs other plugins
- No remaining `unified_memory` references in codebase

---

## Shared Technical Decisions

### 1. DB Path Resolution

All memory provider data must live under `hermes_home` (profile-scoped), not hardcoded `~/.hermes`. The `MemoryProvider.initialize()` receives `hermes_home` in kwargs. Mnemoria should store its DB at `{hermes_home}/memory/mnemoria/mnemoria.db`.

### 2. Honcho Coexistence

Mnemoria and Honcho are **mutually exclusive** per `MemoryManager` (only one external provider allowed). This is by design. Mnemoria should not try to be Honcho-compatible. The benchmark framework provides the公平 comparison surface.

### 4. Backward Compatibility

- Existing `unified_memory/` users: migration path needed. Document in `plugins/memory/mnemoria/MIGRATION.md`.
- `hermes memory layers apply` currently calls unified-memory migration. Update to call mnemoria migration after rename.
- The `unified_memory/` directory at repo root will be deleted after all files are moved to `plugins/memory/mnemoria/`. No dual maintenance.

### 4. Metric: `BenchmarkableStore` vs `MemoryProvider`

The benchmark adapter (`MnemoriaBenchmarkAdapter`) is separate from the `MemoryProvider`. The adapter is for benchmarking; the provider is for runtime. They share the underlying `mnemoria.store` implementation.

```
mnemoria.store  ← shared implementation
    ↑
    │
MnemoriaBenchmarkAdapter ← benchmark runner uses this
MnemoriaMemoryProvider   ← hermes-agent runtime uses this
```

### 5. Dependencies

Mnemoria's `plugin.yaml` should declare:

```yaml
pip_dependencies:
  - numpy  # HRR algebra, statistics
```

Core dependencies (SQLite, stdlib) need no declaration. Do NOT add heavy ML dependencies (transformers, torch) — keep it lean. The retrieval is graph-based (PageRank on SQLite), not embedding-model-based.

---

## Reference: Existing Plan (plans/2026-04-03-benchmark-capability-aware-memory-comparison.md)

Key sections to respect:

- **Section 4** — `BackendCapabilities` dataclass spec (required for fair adapter declarations)
- **Section 5** — Three-layer scoring: core track, capability-track scores, coverage profile
- **Section 6** — Fairness principles to document in benchmarks README
- **Section 7** — Implementation sequence (Phase 1 capability metadata, Phase 2 track reclassification, Phase 3 new suites, Phase 4 external adapters, Phase 5 result interpretation)
- **Section 9** — How to compare mnemoria fairly once the framework exists

---

## Command Reference

```bash
# === Verify adapters load ===
cd /workspace/Projects/hermes-agent
python -c "from benchmarks.backends import *; print(list(BACKENDS.keys()))"

# === Run benchmark suite (specific backend) ===
python -m benchmarks.runner --backend mnemoria --suite a,b,c --runs 3

# === Run benchmark suite (all available backends) ===
python -m benchmarks.runner --backend all --suite a --runs 1

# === Verify mnemoria imports ===
python -c "from mnemoria.store import MnemoriaStore; print('store OK')"
python -c "from mnemoria.retrieval import fts5_search; print('retrieval OK')"
python -c "from mnemoria.benchmark_adapter import MnemoriaBenchmarkAdapter; print('adapter OK')"

# === Verify hermes memory layers CLI ===
python -c "from hermes_cli.memory_layers import *; print('memory_layers OK')"
hermes memory layers --help

# === Verify MemoryProvider interface ===
python -c "from agent.memory_provider import MemoryProvider; print('provider ABC OK')"
python -c "from plugins.memory.mnemoria import MnemoriaMemoryProvider; print('mnemoria provider OK')"

# === Run tests ===
python -m pytest tests/gateway/test_approve_deny_commands.py -x -q --tb=short
python -m pytest tests/benchmarks/ -x -q --tb=short
```

---

## Decisions Made (2026-04-04)

| # | Question | Decision |
|---|----------|---------|
| 1 | `builtin` adapter | Explicitly skip with documentation note. Builtin is always-on baseline, not a competitive store/recall system. Not every plugin needs benchmarking. |
| 2 | Source location | `plugins/memory/mnemoria/` (match holographic/honcho pattern exactly). Source lives inside the plugin directory. |
| 3 | Mnemoria + Honcho | Competing for the same MemoryManager slot. Mnemoria is local-first (privacy, no cloud dependency), Honcho is cloud API. We focus on building mnemoria as the best possible alternative — not integrating with honcho, not calling honcho APIs internally. Both available for users to choose. |
| 4 | PR overlap | `pr/mnemoria-plugin` based on `pr/benchmark-suite` current HEAD. If PR 1 merges first, rebase. If both are up simultaneously, PR 2 notes dependency on benchmark suite infrastructure. Mnemoria benchmark scores run against current `pr/benchmark-suite` HEAD. |

## Next: Update Plan → Start Building

See Section "Tasks for PR 1" and "Tasks for PR 2" below for the full build checklist.

# Multi-Provider Memory — Release Notes

**Fork:** [someaka/hermes-agent](https://github.com/someaka/hermes-agent) — branch `main`
**Base:** upstream v0.13.0 (v2026.5.7)
**18 source files · +881 / −299 lines**

> Adds **multi-provider memory** to Hermes Agent — run multiple memory backends
> (Mnemosyne, Hindsight, Holographic, Mem0, etc.) simultaneously instead of
> being locked to a single provider.

---

## What changes

### 1. Multi-provider config key

New `memory.providers` (list) in `config.yaml` alongside the legacy
`memory.provider` (string, still works as fallback):

```yaml
memory:
  providers:
    - mnemosyne
    - holographic
    - mem0
```

**File:** `hermes_cli/config.py`

---

### 2. Concurrent provider loading

`MemoryManager.add_provider()` registers all configured providers at agent
startup. Each provider gets its own tool namespace. The built-in memory
provider is always registered first and cannot be removed.

**Files:** `agent/memory_manager.py`, `run_agent.py`

---

### 3. Thread-safe MemoryManager

`RLock`-guarded registration and removal. Safe for concurrent subagent and
gateway use.

**File:** `agent/memory_manager.py`

---

### 4. Runtime provider removal

`remove_provider(name)` cleanly deregisters a provider: cancels background
tasks, releases tools, updates config state.

**File:** `agent/memory_manager.py`

---

### 5. Provider removal UX

- CLI checklist for removing providers interactively
- Web API endpoint for provider management
- Doctor checks iterate all active providers instead of just one

**Files:** `hermes_cli/memory_setup.py`, `hermes_cli/web_server.py`,
`hermes_cli/doctor.py`, `hermes_cli/plugins_cmd.py`

---

### 6. Schema-first registration

`add_provider()` wraps `get_tool_schemas()` in try/except — a provider that
fails schema loading is never registered. No partial state.

**File:** `agent/memory_manager.py`

---

### 7. Tool budget warning

Warns when 20+ memory tools are registered across all providers (may degrade
tool-calling accuracy).

**File:** `agent/memory_manager.py`

---

### 8. Namespace-prefixed tools

Each provider's tools are prefixed with its name (e.g. `holographic_store`,
`mem0_search`) to avoid collisions. Naming convention is validated at
registration time.

**Files:** `agent/memory_manager.py`, `agent/memory_provider.py`

---

### 9. Memory context preservation across compression

New `on_pre_compress` return value flows into the compressor as a
`memory_context` parameter. Provider insights are injected into the summary
prompt so they survive context compaction.

**Files:** `agent/memory_manager.py`, `agent/context_compressor.py`,
`agent/context_engine.py`, `run_agent.py`

---

### 10. Multi-provider doctor checks

`hermes doctor` now iterates all active memory providers (honcho, hindsight,
holographic, mem0, openviking, etc.) instead of checking only the first one.

**File:** `hermes_cli/doctor.py`

---

### 11. MCP SDK compat fallbacks

Fallback shim types when the MCP SDK is too old or not installed — prevents
import errors in test environments.

**File:** `tools/mcp_tool.py`

---

### 12. Dev dependency group

New `[dependency-groups]` section in `pyproject.toml` for development
dependencies (fastapi, mcp, pytest-asyncio, etc.).

**Files:** `pyproject.toml`, `uv.lock`

---

## Files to copy

These are the 18 source files users need to overlay onto a v0.13.0 install:

| File | What it does |
|------|-------------|
| `agent/memory_manager.py` | Core: multi-provider, thread-safe, removal, schema-first |
| `agent/memory_provider.py` | Updated ABC docs for multi-provider semantics |
| `agent/context_compressor.py` | Memory context injection into compression summaries |
| `agent/context_engine.py` | `memory_context` parameter on abstract `compress()` |
| `hermes_cli/config.py` | `memory.providers` config key |
| `hermes_cli/doctor.py` | Multi-provider health checks |
| `hermes_cli/memory_setup.py` | Multi-select setup wizard + removal UX |
| `hermes_cli/plugins_cmd.py` | Multi-provider listing in `hermes plugins` |
| `hermes_cli/main.py` | Multi-provider loading at startup |
| `hermes_cli/web_server.py` | Provider management API endpoint |
| `hermes_cli/dump.py` | Include multi-provider state in dumps |
| `plugins/memory/__init__.py` | Plugin loader supports `memory.providers` list |
| `plugins/memory/holographic/__init__.py` | Schema-first compat |
| `plugins/memory/honcho/cli.py` | Doctor compat for multi-provider iteration |
| `run_agent.py` | Load multiple providers + memory_context flow |
| `tools/mcp_tool.py` | MCP SDK compat fallback types |
| `pyproject.toml` | Dev dependency group |
| `uv.lock` | Lockfile for dev deps |

---

## Install

```bash
git clone https://github.com/someaka/hermes-agent
cd hermes-agent
git checkout main
uv pip install -e ".[all]"
```

Or overlay files manually onto an existing v0.13.0 install.

---

## Quick start

```bash
# Configure multiple providers
hermes setup   # memory provider step now supports multi-select

# Or edit ~/.hermes/config.yaml directly:
# memory:
#   providers:
#     - mnemosyne
#     - holographic

# Verify
hermes doctor
hermes plugins list
```

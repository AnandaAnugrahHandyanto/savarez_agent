# mcp_lazy Phase 2 — Server-Level Discovery

**Status:** Draft v3 — Codex + hermes-agent self-review amendments integrated
**Target version:** mcp_lazy v1.1
**Builds on:** Phase 0 (#6), Phase 1 (#7) — both shipped on main
**Author:** Rohit + Claude collaboration, architect-reviewed

---

## Problem

Phase 1 collapses MCP tool token cost from ~58k → ~24k by stubbing per-tool schemas. But the floor is still O(N_tools). With 305 tools across 10 servers, the model wastes capacity scanning 305 entries every turn just to know what's available.

Real usage pattern: users (and the model) reference MCPs by **server** (`"check trek"`, `"send via gmail"`, `"context_mode search"`). The model rarely needs all 305 tools visible — it needs to know the 10 servers exist and what each does, then drill down.

## Solution

Add a second discovery tier above Phase 1: **one stub per server** instead of per tool. Model sees ~10 entries (~2.5k tok). To use any tool, it calls a new meta-tool `load_mcp_server(server_names=[...])` which promotes that server's tools (as Phase 1 tool stubs for further drill-down). Existing `load_mcp_tools` stays for surgical tool-level promotion.

Token target: **8-11k typical turn** (vs Phase 1's 24k) = ~58% further reduction.

## Token math (verified against live data)

Measured 2026-05-26 against hermes-switch profile, 305 MCP tools / 10 servers:

| Mode | Discovery layer | After 1 server promoted | After 1 tool promoted |
|---|---|---|---|
| No plugin | 58,700 tok | — | — |
| Phase 1 (today) | 24,400 tok | 24,400 (1 tool full) | — |
| **Phase 2 `server` mode** | 2,500 tok | 2,500 + N×80 (e.g. trek = +11k) | 2,500 + 500 (single tool) |
| **Phase 2 `both` mode** | 4,500 tok | 4,500 + N×80 (server stubs stay visible) | 4,500 + 500 |

Plus ~5-7k for the 38 builtin tools (always full schemas, out of scope).

**Realistic cold-turn estimate: 8-11k tok** depending on mode and which server gets promoted.

## Design decisions (locked)

| # | Decision | Rationale |
|---|---|---|
| Q1 | Server promote → **tool stubs by default**, full schemas only if ≤10 tools | Promoting trek to full = 24k = worse than today |
| Q2 | Direct tool call without `load_mcp_server` → **auto-promote server + retry** | Avoid friction for model that recalls tool names |
| Q3 | Server description fallback → **auto-synth `"N tools: {first 5-6 names}..."` capped 150ch** | Upgrade path: author writes real description in config |
| Q4 | New sentinel `__lazy_server_stub__` distinct from `__lazy_stub__` | Required for dispatch routing |
| Q5 | `load_mcp_tools` direct path when only server stubs visible → **allowed** | Power-user fast path; resolver looks up server from tool name |
| Q6 | MCP server hot-reload → **rebuild server stubs every `transform_tools` call** | Cheap (~µs); correctness > caching |
| **Default mode** | **`discovery_mode: both`** | Best UX; server stubs stay visible after promotion |

## Config additions

```yaml
mcp:
  lazy_loading: true                    # existing master toggle
  lazy_stub_max_desc: 200               # existing per-tool stub desc cap
  discovery_mode: both                  # NEW: tool | server | both
  server_stub_max_desc: 150             # NEW: per-server stub desc cap
  server_eager_threshold: 10            # NEW: servers with ≤N tools promote full

mcp_servers:
  trek:
    description: "Trip planning: itineraries, bookings, weather, packing"  # NEW
    lazy: true
  gmail:
    description: "Email: search, send, draft, labels, filters"
    lazy: true
  # ... if description missing, plugin auto-synthesizes from tool names
```

## File-level implementation plan (Option A — minimal reuse)

### New files

**`plugins/mcp_lazy/server_stubs.py`** (~80 LOC)
- `SERVER_LAZY_SENTINEL = "__lazy_server_stub__"`
- `make_server_stub_schema(server_name, description, tool_count, max_desc) -> dict` — synthesizes pseudo-tool with name `mcp_server_{name}`, description, and sentinel param
- `is_server_stub_schema(schema) -> bool`
- `derive_servers_from_tools(tools) -> dict[str, list[str]]` — fallback grouping when config is empty
- `synth_server_description(tool_names, max_chars=150) -> str` — auto-synth fallback

**`plugins/mcp_lazy/meta_tool_server.py`** (~80 LOC, copy-edit of `meta_tool.py`)
- `SCHEMA` for `load_mcp_server` with `server_names: list[str]`
- `check(name) -> bool` — handler routing
- `async handler(args, agent)` — expands server names → tool names → calls `pool.promote(tool_names)`; supports `eager=true` flag to promote to full schema instead of tool stub

### Modified files

**`plugins/mcp_lazy/stubs.py`** (~30 LOC delta)
- Extend `mix_full_and_stubs` to accept `discovery_mode` param
- Branch logic:
  - `tool` mode: today's behavior unchanged
  - `server` mode: emit one server stub per eligible server; omit individual tool stubs entirely
  - `both` mode: emit server stubs always + tool stubs for tools whose server is in `pool.promoted_servers`
- Reuse `_server_in_set` as-is

**`plugins/mcp_lazy/pool.py`** (~40 LOC delta) — **BLOCKER #1 fix**
- Add `promoted_servers: set[str]` slot AND extend `__slots__` to include it (else AttributeError)
- Add `promote_server(name)` / `is_server_promoted(name)` / `promoted_servers_snapshot()` methods
- Extend `clear()` / `evict()` to reset both `_promoted` and `promoted_servers`
- Lock-protected idempotent `promote_server(name, eager: bool)` — last-writer-wins for eager flag, log conflict at WARNING (BLOCKER #7 fix)

**`plugins/mcp_lazy/hook_impl.py`** (~30 LOC delta)
- Read `discovery_mode` from config in `transform_tools`
- Pass to `mix_full_and_stubs`
- Update diagnostic log to show server_stubs count + tool_stubs count + full_mcp count
- **Remove** `/tmp/mcp_lazy_tools_dump.json` dev scaffold from current diagnostic patch

**`plugins/mcp_lazy/__init__.py`** (~10 LOC delta)
- Register `load_mcp_server` meta-tool alongside existing `load_mcp_tools`
- Both visible always — model picks based on what it sees

**`plugins/mcp_lazy/promote.py`** (~30 LOC delta) — **BLOCKER #3 fix**
- Accept `eager: bool` flag for server-level promote
- Server → tool-name expansion via `agent.valid_tool_names` (NOT the nonexistent `agent.get_tool_definitions()`). Cross-reference with `model_tools.get_tool_definitions()` at `model_tools.py:263` for full schema lookup when eager promotion needed.
- Resolver: given a server name, return list of tool names whose prefix matches via existing `_server_in_set` semantics

**`plugins/mcp_lazy/README.md`** — new section: "Phase 2: Server Discovery"

### Test additions

- `tests/plugins/mcp_lazy/test_server_stubs.py` — stub schema construction, server description synthesis, discovery mode branches
- `tests/plugins/mcp_lazy/test_meta_tool_server.py` — handler expands names, promotes, returns correct hint
- Extend `tests/plugins/mcp_lazy/test_integration_phase1.py` for `discovery_mode=both` end-to-end

## Gap analysis amendments (Codex review)

### BLOCKER #2 — Dispatch-layer routing for stub calls

`handle_function_call()` at `model_tools.py:808,:818` sends every tool call straight to `registry.dispatch()` with no sentinel-aware fallback. Phase 1 today relies on the model voluntarily calling `load_mcp_tools` because direct stub-tool calls aren't routed. Phase 2's "auto-promote server + retry" answer to Q2 is unwired.

**Fix:** Add dispatch interception in `meta_tool_server.py` register flow:
- Register a `pre_tool_dispatch` hook (or extend an existing one) that inspects the tool name
- If name matches a *server stub* sentinel → promote that server, return synthetic "promoted, retry" message
- If name matches a real MCP tool whose server isn't yet promoted → auto-promote server, return retry hint
- If `discovery_mode=tool` → preserve Phase 1 behavior (no interception)

Touches `model_tools.py:808-820` OR introduces a new plugin hook. **Decision:** add new `pre_tool_dispatch` hook to `VALID_HOOKS` in `hermes_cli/plugins.py` rather than patching `model_tools.py` directly — keeps the plugin self-contained and submittable upstream.

### MAJOR #4 — Cache-key coupling with `get_tool_definitions`

`model_tools.get_tool_definitions()` at `model_tools.py:242,:297` caches on toolsets + registry generation + config fingerprint. `transform_tools` runs later at `build_api_kwargs()` (`chat_completion_helpers.py:233`). Server-promotion state must live **outside** the cache, otherwise promoting a server invalidates the entire definition cache.

**Fix:**
- Keep `promoted_servers` on the `DeferredToolPool` (per-session, in-memory only)
- `transform_tools` reads from pool snapshot AFTER `get_tool_definitions` returns
- Canonical `agent.tools` never mutates — only the request-time tool list reshapes
- Same pattern as Phase 1, just at a coarser grain. No cache-key changes needed.

### MAJOR #5 — `discovery_mode=both` post-promotion visibility

After `load_mcp_server("trek")` promotes trek, plan didn't specify how trek's tool stubs appear. Two valid choices:

**Choice A (selected):** Promotion adds `trek` to `promoted_servers`; next `transform_tools` call emits server stub for trek + tool stubs for all trek's tools. Model now sees trek server stub + 140 trek tool stubs.

**Choice B:** Promotion immediately emits full schemas for trek's tools. Rejected — risks 24k token blow-out on big servers.

**Plan amendment to `mix_full_and_stubs`:** in `both` mode, for each MCP tool:
- If tool's server in `promoted_servers` and tool name in `_promoted` → full schema
- Else if tool's server in `promoted_servers` → Phase 1 tool stub
- Else → omitted (server stub covers it at server-stub layer)

`load_mcp_tools` remains visible/callable in all modes for surgical promotion.

### MAJOR #6 — Background review fork shares promotion pool

`background_review.py:420,:428` copies parent `session_id`. Phase 1 had this same risk and resolved via Codex review (mutate `session_id` to derived form). Phase 2 inherits it unchanged but now both `_promoted` AND `promoted_servers` get shared.

**Fix:** Same Phase 1 mitigation already applied — no new code, but **add regression test** confirming background review fork doesn't see parent's `promoted_servers`. If Phase 1's fix is purely session-id mutation, Phase 2 inherits the fix automatically. Verify in test.

### MAJOR #8 — Config defaults and validation

`DEFAULT_CONFIG` at `hermes_cli/config.py:470` has no `mcp.lazy_loading` or new Phase 2 keys. `validate_config_structure()` at `config.py:3191` has no MCP-specific checks. Bad values silently misbehave.

**Fix:**
- Add to `DEFAULT_CONFIG`: `mcp: { lazy_loading: false, discovery_mode: "tool", lazy_stub_max_desc: 200, server_stub_max_desc: 150, server_eager_threshold: 10 }`
- Add validation: `discovery_mode in {"tool", "server", "both"}`, `server_eager_threshold` int ≥0, `server_stub_max_desc` int ≥0, `mcp_servers.<name>.description` str if present
- `hermes doctor` lights up if config invalid

### MAJOR #9 — Rollback discipline

Plan said `__init__.py` always registers `load_mcp_server`. If user sets `discovery_mode: tool` for rollback, the new meta-tool is still visible — confusing surface.

**Fix:** `__init__.py` reads `discovery_mode` at registration time:
- `tool` → register only `load_mcp_tools` (Phase 1 only)
- `server` or `both` → register both `load_mcp_tools` AND `load_mcp_server`
- Default `tool` preserves zero new surface area on upgrade

### MINOR #10 — Stale `/tmp` reference

Already removed from `hook_impl.py`. Plan still references it. **Fix:** delete bullet from plan (this commit).

### MINOR #11 — VALID_HOOKS already complete

`transform_tools` + `on_session_reset` already in `VALID_HOOKS` (`hermes_cli/plugins.py:128,:152`). Plan listed this as open question — **it's resolved**. But BLOCKER #2 introduces NEW hook need: `pre_tool_dispatch` likely needs adding to `VALID_HOOKS`. Verify during implementation.

### MINOR #12 — Test plan expansion

Original 3 test files insufficient. Add coverage:

| Test | Covers |
|---|---|
| `test_config_validation.py` | Malformed `discovery_mode`, non-int thresholds, non-str descriptions |
| `test_server_edge_cases.py` | Server with 0 tools, nonexistent server name, missing description (synth fallback), server name collision after sanitisation |
| `test_concurrent_promotion.py` | Two requests promote same server simultaneously, eager vs non-eager conflict |
| `test_background_review_isolation.py` | Forked review agent does not see parent's `promoted_servers` |
| `test_mode_transitions.py` | Live config switch from `tool` → `both` mid-session behavior |
| `test_phase0_continuity.py` | Phase 0 baseline logger still captures cache stats correctly under Phase 2 |
| `test_rollback.py` | Setting `discovery_mode: tool` after `both` removes `load_mcp_server` visibility |

## Hermes-agent self-review amendments (v3)

### CRITICAL #1 — Auto-promote control flow & scope (was hand-waved)

**Decision:** auto-promote on direct tool call promotes the **single tool**, not the whole server. The server stays unpromoted. Server-level promotion only happens when model explicitly calls `load_mcp_server`.

**Why single tool:** promoting trek (140 tools) because model called one trek tool blows the savings (+11k tokens). Single-tool auto-promote keeps savings while removing the friction loop.

**Control flow** (in new `pre_tool_dispatch` hook):
```
1. Tool call arrives at dispatch with name="mcp_trek_create_trip"
2. Hook inspects: is this name in agent.valid_tool_names? (yes — it's a real tool)
3. Hook inspects: is current visible schema a stub? (look up pool.snapshot())
4. If stub → pool.promote(["mcp_trek_create_trip"])
5. Return synthetic tool message: "{tool} promoted; full schema visible next turn. Reissue the call."
6. Model retries next turn with full schema — same Phase 1 retry pattern
```

**Retry semantics:** **next-turn retry, NOT same-turn re-dispatch.** Same as Phase 1. Reason: re-dispatching mid-turn requires the model to have the full schema already (cache invalidation + tool list reshape mid-stream). Single-turn delay is the established Phase 1 contract — keep it.

**Scope toggle for power users:** `load_mcp_server(server_names=[...], eager: bool = false)` lets model opt into bulk promotion when it knows it needs many tools from one server (e.g. orchestrating a trip).

### EDGE #2 — Server↔tool name prefix collision

Current `_server_in_set` (`stubs.py:119-133`) does longest-prefix match. With server names `my_tool` and `my_tool_v2`, the tool `mcp_my_tool_v2_create` is ambiguous.

**Fix:** sort eligible servers by descending sanitised-name length before matching. Longest prefix wins. Add test: `test_prefix_collision.py` with `my_tool` + `my_tool_v2` registered → `mcp_my_tool_v2_X` routes to `my_tool_v2`.

### UX #3 — Auto-synth description quality floor

Auto-synth from tool names can produce useless output (`zerolib-email` → "Email operations: add, delete, get emails"). 

**Fix:**
- Synth format: `"{N} tools: {first_3_tool_names_humanized}, …"` — explicit count + sample, no semantic claim
- Add WARNING log at registration when synth is used: `mcp_lazy: server '{name}' has no description; using auto-synth. Add mcp_servers.{name}.description for better model routing.`
- README documents this as the upgrade path

### DESIGN #4 — `server_eager_threshold` should be token-based, not count-based

A server with 11 tiny tools (avg 50 tok each = 550 tok full) is cheaper full than as stubs + round-trip. Count threshold misses this.

**Fix:** rename to `server_eager_token_threshold: 1500` (tokens, default 1500). Compute server's full-schema cost once at startup; eager-promote if ≤ threshold. Counts the actual cost, not a proxy.

Implementation: cache `server_total_full_tokens` map at first `transform_tools` call (cheap one-shot scan).

### CORRECTNESS #5 — Subagent isolation for `promoted_servers`

`delegate_task` spawns subagents that share `_current_agent_var` ContextVar — same parent session_id, same pool. Phase 1 has this concern for `_promoted` (tool names); Phase 1 today inherits parent's promoted tools. Phase 2's `promoted_servers` follows same rule.

**Decision:** subagents inherit parent's `promoted_servers` and `_promoted` (current Phase 1 behavior). Reason: subagent is doing parent's bidding; parent already paid promotion cost. Re-stubbing for subagent wastes its first turn.

**Risk:** subagent auto-promotes a tool the parent didn't need → leaks back to parent pool. Acceptable — parent will see one extra promoted tool, costs ~500 tok max.

**Background review fork is different** — that's a forensic session, NOT a worker. Already mitigated by Phase 1's session_id mutation (`background_review.py:427-428`). Regression test reuses Phase 1's pattern.

### EDGE #7 — Rollback `both→tool` orphan state

When `discovery_mode` flips `both` → `tool` mid-session, `promoted_servers` set still exists in pool but `tool` mode's `mix_full_and_stubs` ignores it.

**Fix:** plugin reads mode at every `transform_tools` call (already does for hook). On mode change detection (compare to cached previous mode), call `pool.clear_servers()` and log INFO. Stale promotions evicted automatically.

Alternative: leave state in pool, ignored in tool mode. Safer (no destructive op on config edit), but slightly leaks memory. **Pick:** leave state in pool, log WARNING on flip.

### EDGE #8 — Parallel tool calls with multiple stub servers

Model calls 5 tools in one turn; 3 are stubs from different servers. `pre_tool_dispatch` hook fires per-call.

**Fix:** each stub call independently auto-promotes its single tool (per CRITICAL #1). All 5 calls return their results / promotion-pending messages independently. Next turn, the 3 newly-promoted tools are full schemas. Model reissues those 3 calls.

No partial-success ambiguity because each call is independent. Test: `test_parallel_stub_dispatch.py` — 5 mixed stub/full/non-MCP calls in one turn.

### MINOR — five improvements

| # | Change | File |
|---|---|---|
| M1 | `load_mcp_server` returns `{"promoted": ["mcp_trek_create_trip", ...], "available_next_turn": true}` not just "ok" | `meta_tool_server.py` |
| M2 | Extend `cache_report.py` with per-server promotion counts + estimated token saved | `scripts/cache_report.py` |
| M3 | Config validator rejects `discovery_mode` not in `{"tool","server","both"}` with helpful message | `hermes_cli/config.py:3191` |
| M4 | If `mcp_servers.<name>.lazy: false` set AND description provided → log INFO "description ignored for eager server" | `hook_impl.py` registration |
| M5 | `__init__.py` logs at INFO: `mcp_lazy: discovery_mode=both, registered: [load_mcp_tools, load_mcp_server]` | `__init__.py` |

### Locked design table update

Add to decision matrix from `## Design decisions (locked)`:

| # | Decision | Rationale |
|---|---|---|
| **Q7** | Auto-promote scope on direct tool call = **single tool, not server** | Preserves savings; server promote is explicit-only |
| **Q8** | Retry semantics = **next-turn**, not same-turn | Matches Phase 1 contract; avoids mid-stream cache invalidation |
| **Q9** | Eager threshold = **token-based, default 1500 tok** | Correct cost model; 10-tool count was proxy |
| **Q10** | Subagent inherits parent's `promoted_servers` and `_promoted` | Subagent serves parent; avoids re-promotion cost |
| **Q11** | Mode flip `both→tool` mid-session = **leave pool state, log WARNING** | Safer than destructive clear |

## Out of scope (deferred)

- Stubbing the 38 builtin tools — separate plugin or Phase 3
- BM25 pre-selection on server descriptions (was original Phase 2 plan; now Phase 3 candidate)
- Upstream `transform_tools` hook PR to NousResearch/hermes-agent — separate workstream, blocks nothing here

## Risks

| Risk | Mitigation |
|---|---|
| Model ignores server stubs, hallucinates tool calls | Auto-promote-server fallback (Q2) recovers gracefully |
| Server description quality varies | Auto-synth fallback + config upgrade path documented |
| Tool list shape changes break cache | Rebuilt every call (Q6); cache invalidation is per-turn anyway under Phase 1, no regression |
| Dispatch routing confusion (server stub vs tool stub) | Distinct sentinels (Q4) |
| Trek 140-tool promotion floods context | `server_eager_threshold: 10` enforces tool-stub default for big servers (Q1) |

## Rollout plan

1. **Branch:** `feat/mcp-lazy-phase2-server-discovery`
2. **Implement Option A** — new files + modifications above
3. **Run existing tests** + new test additions
4. **Adversarial review via Codex** (same pattern as Phase 1 PR #7)
5. **Open PR** to Interstellar-code/hermes-agent main
6. **Soak 2 weeks** in production with `discovery_mode: both` enabled
7. **If stable + savings confirmed via cache_report:** make `both` the default mode in plugin

## Open questions for soak phase

- Does the model reliably call `load_mcp_server` when it sees only server stubs? (Phase 1 model behavior with `load_mcp_tools` is the proxy — it does)
- What's the realistic ratio of "1 server promoted per turn" vs "3+ servers promoted"? Determines whether `both` mode floors at 10k or 15k.
- Does the auto-promote-on-direct-tool-call (Q2) reduce model meta-tool calls measurably?

## Success metrics

- Cold-turn input tokens drop from ~45k → ~25k (45% session-level reduction)
- `load_mcp_server` called on ≥80% of turns where MCP tools are used (vs 100% having to call `load_mcp_tools` today)
- Zero new error types in 2-week soak vs Phase 1 baseline

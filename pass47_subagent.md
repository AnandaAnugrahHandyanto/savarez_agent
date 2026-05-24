# Findings — Pass #47: Memory Management, Resource Limits & Leak Detection
## Repo: 5b52e26d1 (origin/main)
## Pass date: 2026-05-24
## Scope: Memory leak patterns, resource limits, background task cleanup, LRU eviction, file descriptor leaks, token/statement budget enforcement

---

## 1. MEMORY LEAK PATTERNS

### FINDING P47-001: Feishu `_sent_message_id_order` is dead code — never used
**File**: `gateway/platforms/feishu.py` (lines 1449-1450, 229)
**Severity**: Medium
**Pattern**: Unused global variable + unbounded list potential

```python
_Feishu_BOT_MSG_TRACK_SIZE = 512                   # LRU size for tracking sent message IDs
# ...
self._sent_message_ids_to_chat: Dict[str, str] = {}  # message_id → chat_id
self._sent_message_id_order: List[str] = []  # LRU order for _sent_message_ids_to_chat
```

**Issue**: `_sent_message_id_order` is declared and `_FEISHU_BOT_MSG_TRACK_SIZE` is set to 512, but a grep across the entire feishu.py file shows **zero references** to `_sent_message_id_order` after declaration (no appends, no pops, no membership checks, no len() calls). The list is completely dead code.

Additionally, `_FEISHU_BOT_MSG_TRACK_SIZE` is also unused — nothing enforces the 512 cap since the list it was meant to bound is never touched.

**Assessment**: The LRU list pattern appears to have been started (list + constant declared) but never completed. The companion dict `_sent_message_ids_to_chat` is used (for reaction routing based on message_id → chat_id lookup), but its LRU order tracking list is not. This is a code smell but not an active memory leak since the list is never populated.

**Action**: Either implement the LRU tracking properly (using `OrderedDict` like `_pending_processing_reactions`), or remove the dead `_sent_message_id_order` and the unused `_FEISHU_BOT_MSG_TRACK_SIZE` constant.

---

### FINDING P47-002: Feishu `_pending_processing_reactions` LRU uses correct OrderedDict pattern (positive)
**File**: `gateway/platforms/feishu.py` (line 1469, 2934-2939)
**Severity**: Informational — WELL IMPLEMENTED
**Pattern**: Proper bounded LRU via OrderedDict

```python
self._pending_processing_reactions: "OrderedDict[str, str]" = OrderedDict()
```

The LRU cache in feishu is correctly implemented with `move_to_end()` on access and `popitem(last=False)` to evict the oldest entry when over `_FEISHU_PROCESSING_REACTION_CACHE_SIZE`. This is the reference implementation that `_sent_message_id_order` should mirror.

---

### FINDING P47-003: OpenRouter pre-warm thread leak guard (positive)
**File**: `run_agent.py` (lines 211-215)
**Severity**: Informational — WELL IMPLEMENTED
**Pattern**: Module-level threading.Event guard prevents repeated thread spawn

```python
_openrouter_prewarm_done = threading.Event()
```

**Issue (none)**: This is a correctly implemented singleton guard. When `AIAgent.__init__` checks `_openrouter_prewarm_done` before spawning the pre-warm thread, it prevents a long-running gateway process from leaking one OS thread per incoming message. Confirmed as a best-practice pattern.

---

## 2. RESOURCE LIMITS ENFORCEMENT

### FINDING P47-004: Agent cache LRU enforcement — correctly handles mid-turn agents
**File**: `gateway/run.py` (lines 15160-15229)
**Severity**: Informational — WELL IMPLEMENTED
**Pattern**: LRU eviction with mid-turn protection

The `_enforce_agent_cache_cap()` method correctly:
- Uses `id()` lookup on `_running_agents` to detect mid-turn agents without relying on `AIAgent.__eq__` (which MagicMock overrides in tests)
- Skips eviction of mid-turn agents without compensating by evicting newer entries (avoids penalising freshly-inserted sessions)
- Logs a warning when all excess LRU slots are held by mid-turn agents, with the cache temporarily staying over cap
- Schedules cleanup on daemon threads so the cache lock is not held during teardown

**Status**: Solid implementation.

---

### FINDING P47-005: `_AGENT_CACHE_MAX_SIZE = 128` with idle TTL eviction
**File**: `gateway/run.py` (lines 64-65)
**Severity**: Informational — WELL IMPLEMENTED

```python
_AGENT_CACHE_MAX_SIZE = 128
_AGENT_CACHE_IDLE_TTL_SECS = 3600.0  # evict agents idle for >1h
```

The `_session_expiry_watcher()` runs every 300s and evicts agents idle > 1h regardless of session reset policy. This prevents cached AIAgents from pinning memory for the gateway's entire lifetime.

---

### FINDING P47-006: ProcessRegistry MAX_PROCESSES = 64 with LRU pruning
**File**: `tools/process_registry.py` (lines 58-60, 1314-1339)
**Severity**: Informational — WELL IMPLEMENTED

```python
MAX_OUTPUT_CHARS = 200_000      # 200KB rolling output buffer
FINISHED_TTL_SECONDS = 1800     # Keep finished processes for 30 minutes
MAX_PROCESSES = 64              # Max concurrent tracked processes (LRU pruning)
```

`_prune_if_needed()` correctly:
- Evicts expired finished sessions by TTL first
- Then evicts oldest finished session if still over `MAX_PROCESSES`
- Cleans up stale `_completion_consumed` entries to prevent set growth
- Called atomically under `_lock` on every spawn path (lines 574, 625, 726)

---

### FINDING P47-007: Watch pattern rate limiting — circuit breaker (positive)
**File**: `tools/process_registry.py` (lines 62-75)
**Severity**: Informational — WELL IMPLEMENTED

```python
WATCH_MIN_INTERVAL_SECONDS = 15   # Minimum spacing between consecutive watch matches
WATCH_STRIKE_LIMIT = 3            # Strikes in a row → disable watch + promote to notify_on_complete
WATCH_GLOBAL_MAX_PER_WINDOW = 15   # Global circuit breaker across all sessions
WATCH_GLOBAL_WINDOW_SECONDS = 10
WATCH_GLOBAL_COOLDOWN_SECONDS = 30
```

Multi-layer rate limiting: per-session cooldown + strike limit + global circuit breaker prevents sibling processes from collectively flooding the user.

---

### FINDING P47-008: IterationBudget thread-safe consume/refund (positive)
**File**: `agent/iteration_budget.py` (lines 32-59)
**Severity**: Informational — WELL IMPLEMENTED

```python
def consume(self) -> bool:
    with self._lock:
        if self._used >= self.max_total:
            return False
        self._used += 1
        return True
```

Thread-safe, returns False when exhausted, with refund support for `execute_code` turns. Confirmed as solid.

---

### FINDING P47-009: `release_clients()` vs `close()` distinction — correctly implemented
**File**: `run_agent.py` (lines 2052-2130)
**Severity**: Informational — WELL IMPLEMENTED

The critical distinction:
- `release_clients()` — soft cleanup for cache eviction; preserves process_registry entries, terminal sandboxes, browser daemons, and memory providers. Only closes OpenAI/httpx client + active child agents.
- `close()` — hard teardown for session boundaries; kills everything including process_registry entries and sandboxes.

This is correctly implemented and prevents cache eviction from killing user's background shells.

---

### FINDING P47-010: `AIAgent.close()` properly cleans up all resources
**File**: `run_agent.py` (lines 2099-2130)
**Severity**: Informational — WELL IMPLEMENTED

The `close()` method correctly:
1. Kills background processes via `process_registry.kill_all(task_id=task_id)`
2. Cleans terminal sandbox environments via `cleanup_vm(task_id)`
3. Cleans browser daemon sessions via `cleanup_browser(task_id)`
4. Closes active child agents
5. Closes OpenAI/httpx client connections

Each step is independently guarded with `try/except Exception: pass` so a failure in one does not prevent the rest.

---

## 3. BACKGROUND TASK CLEANUP

### FINDING P47-011: Slack Socket Mode zombie connection prevention
**File**: `gateway/platforms/slack.py` (lines 552-556)
**Severity**: Informational — WELL IMPLEMENTED

```python
# Close any previous handler before creating a new one so that
# calling connect() a second time (e.g. during a gateway restart or
# in-process reconnect attempt) does not leave a zombie Socket Mode
# connection alive.
```

Correctly closes previous handler before creating a new one to prevent double-dispatch and zombie connections.

---

### FINDING P47-012: Docker init process reaps zombie children (positive)
**File**: `tools/environments/docker.py` (line 508)
**Severity**: Informational — WELL IMPLEMENTED

```python
"--init",           # tini/catatonit as PID 1 — reaps zombie children
```

Docker container uses `--init` so PID 1 is catatonit/tini which reaps zombie processes. This is correct.

---

### FINDING P47-013: Cron scheduler cleans up httpx clients after worker thread death
**File**: `cron/scheduler.py` (lines 1779-1782)
**Severity**: Informational — WELL IMPLEMENTED

```python
# Each cron run spins up a short-lived worker thread whose event loop
# dies as soon as the ``ThreadPoolExecutor`` shuts down. Any async
# httpx clients cached under that loop are now unusable — reap them
# so their transports don't accumulate in the process-global cache.
```

The cron scheduler correctly cleans up async httpx clients that would otherwise accumulate when the per-run ThreadPoolExecutor shuts down.

---

## 4. MEMORY PRESSURE RESPONSE

### FINDING P47-014: No explicit memory pressure detection / GC trigger
**File**: `gateway/run.py`, `run_agent.py`
**Severity**: Low — design observation

No explicit `psutil` memory pressure monitoring or `gc.collect()` triggers anywhere in the codebase. The only memory management is LRU + TTL eviction in the agent cache and ProcessRegistry pruning.

**Assessment**: Python's default GC (generational) is likely sufficient for the workload. However, in extremely long-running gateway processes with many session churns, explicit memory pressure monitoring could be a future improvement. Current design relies on LRU/TTL to bound memory.

---

### FINDING P47-015: `_sweep_idle_cached_agents` correctly skips mid-turn agents
**File**: `gateway/run.py` (lines 15231-15260)
**Severity**: Informational — WELL IMPLEMENTED

The idle TTL sweeper correctly:
- Builds `running_ids` set from `_running_agents` to skip mid-turn agents
- Uses `id()` lookup to avoid AIAgent `__eq__` issues
- Schedules cleanup on daemon threads (non-blocking)
- Evicts under lock but cleanup is async

---

## 5. FILE DESCRIPTOR LEAKS

### FINDING P47-016: `close()` idempotency prevents double-close FD leaks
**File**: `run_agent.py` (line 2109)
**Severity**: Informational — CORRECTLY HANDLED

```python
# Safe to call multiple times (idempotent).
```

The `close()` method is explicitly documented as idempotent. Each cleanup step is independently guarded, so calling close() multiple times will not cause issues.

---

### FINDING P47-017: ProcessRegistry reader threads — no explicit join() on shutdown
**File**: `tools/process_registry.py`
**Severity**: Low — potential concern

Reader threads (`_reader_thread`) are started for each process but there is no explicit `join()` in the `kill()` or `kill_all()` paths. Threads are daemonic (implicitly) in the reader closure, but the `_reader_thread` field is stored on the `ProcessSession` dataclass and the reader is started with `reader.start()`. If a process is killed before the reader thread naturally exits, the thread may continue until the pipe is closed.

**Assessment**: Low severity since threads are short-lived (bound to pipe EOF), but proper join on explicit kill would be more robust.

---

## 6. TOKEN / STATEMENT BUDGET ENFORCEMENT

### FINDING P47-018: Iteration budget — enforced at loop entry, one grace call
**File**: `run_agent.py` (lines 123-128 in AGENTS.md)
**Severity**: Informational — WELL IMPLEMENTED

```python
while (api_call_count < self.max_iterations and self.iteration_budget.remaining > 0) \
        or self._budget_grace_call:
```

The loop condition correctly combines `api_call_count < max_iterations` with `iteration_budget.remaining > 0`. One grace call is allowed via `_budget_grace_call` after budget exhaustion. The `IterationBudget.consume()` returns `False` when exhausted.

---

### FINDING P47-019: Subagent iteration budget is independent (per-agent, not global)
**File**: `agent/iteration_budget.py` (lines 23-26)
**Severity**: Informational — CORRECT BY DESIGN

```python
# Each subagent gets an independent budget capped at
# ``delegation.max_iterations`` (default 50) — this means total
# iterations across parent + subagents can exceed the parent's cap.
```

This is documented and intentional. Users control per-subagent limits via `delegation.max_iterations` in config.yaml. This is not a bug.

---

## SUMMARY

| Category | Finding | Severity | Status |
|----------|---------|----------|--------|
| Memory leak — Feishu `_sent_message_id_order` dead code | P47-001 | Medium | Needs fix: implement LRU or remove dead code |
| Feishu `_pending_processing_reactions` LRU (reference impl) | P47-002 | Informational | Well implemented |
| OpenRouter pre-warm thread leak guard | P47-003 | Informational | Well implemented |
| Agent cache LRU with mid-turn protection | P47-004 | Informational | Well implemented |
| Agent cache MAX_SIZE=128 + idle TTL | P47-005 | Informational | Well implemented |
| ProcessRegistry MAX_PROCESSES=64 + pruning | P47-006 | Informational | Well implemented |
| Watch pattern rate limiting + circuit breaker | P47-007 | Informational | Well implemented |
| IterationBudget thread-safe consume/refund | P47-008 | Informational | Well implemented |
| release_clients() vs close() distinction | P47-009 | Informational | Well implemented |
| AIAgent.close() idempotent resource cleanup | P47-010 | Informational | Well implemented |
| Slack Socket Mode zombie prevention | P47-011 | Informational | Well implemented |
| Docker init reaps zombies | P47-012 | Informational | Well implemented |
| Cron httpx client cleanup after worker death | P47-013 | Informational | Well implemented |
| No explicit memory pressure / GC trigger | P47-014 | Low | Design observation |
| Idle agent sweeper with mid-turn protection | P47-015 | Informational | Well implemented |
| close() idempotency prevents FD leaks | P47-016 | Informational | Well implemented |
| Reader threads — no explicit join() on kill | P47-017 | Low | Minor robustness gap |
| Iteration budget enforced at loop entry | P47-018 | Informational | Well implemented |
| Subagent budget independent (by design) | P47-019 | Informational | Correct by design |

**Total: 19 findings**
- Critical issues: 0
- Medium issues: 1 (P47-001 — Feishu unbounded LRU list)
- Low issues: 2 (P47-014, P47-017)
- Informational/positive: 16

---

*Generated by Pass #47 audit — Memory Management, Resource Limits & Leak Detection*
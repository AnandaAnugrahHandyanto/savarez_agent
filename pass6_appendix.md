---

## Pass #6 – Performance & Efficiency – 2026-05-23 16:45:00 IST

### [Severity: Medium]
**File**: tools/registry.py
**Line(s)**: 57–74
**Issue**: O(n²) complexity in `discover_builtin_tools()`. The function calls `_module_registers_tools(path)` which does `ast.parse()` on every `.py` file for EVERY tool file in `tools_path.glob("*.py")`. So for n tool files: n glob iterations × n AST parses = O(n²) AST parse operations. Each `ast.parse()` reads the full file from disk and builds an AST tree.
**Why invisible in previous passes**: Pass 1 (lexical) saw the glob and the list comprehension but did not analyze the interaction. Pass 4 (concurrency) did not look at file I/O patterns. Pass 5 (tool-call) focused on dispatch, not discovery overhead.
**Impact**: Tool discovery is O(n²) in number of tool files. With ~200+ tool files, startup and any tool-rescan operation does ~40,000 AST parse calls. Each parse is disk I/O + CPU for the full file. This is the first thing that runs before any agent work begins.
**Suggested fix**: Cache the AST result keyed on file mtime. If the file has not changed since last parse, reuse the cached result. Or pre-compute a manifest file with already-parsed results.
**Confidence**: High

---

### [Severity: Medium]
**File**: run_agent.py
**Line(s)**: 3364, 3392, 3583 — three separate `copy.deepcopy(api_messages)` calls in hot message-preprocessing path
**Issue**: `_prepare_messages_for_api()`, `_prepare_messages_for_non_vision_model()`, and `_prepare_messages_for_anthropic_non_vision_model()` each do `copy.deepcopy(api_messages)` — a full deep copy of the entire conversation history on every API call turn. This happens BEFORE the model call, on every turn. For a 50-message conversation, each deepcopy copies all 50 messages including all nested content.
**Why invisible in previous passes**: Pass 1 (lexical) flagged `copy.deepcopy` usage but did not analyze call frequency. Pass 2 (control flow) did not track per-turn invocation. Pass 5 (tool-call) focused on tool execution, not message transformation overhead.
**Impact**: Memory allocation and CPU time proportional to conversation history length, incurred every single API turn. With 90 max iterations and a 50-message history, this could be 270 deep copies of the full message list. The comment in hermes_cli/config.py line 4399 acknowledges "~135µs for the deepcopy alone" as a known hot-path cost — same pattern here.
**Suggested fix**: Use shallow copy + per-message reference sharing, or only copy messages that actually need transformation (lazy copy-on-write). For non-image messages, pass through without copying.
**Confidence**: High

---

### [Severity: Medium]
**File**: hermes_cli/config.py
**Line(s)**: 4365, 4354
**Issue**: `read_raw_config()` and `_load_config_impl()` both do `copy.deepcopy(data)` on every cache hit return. The cache key is `(st_mtime_ns, st_size)` so cache hits are common. Yet every call returns a fresh deep copy. The docstring at line 4379 explicitly acknowledges this: "read-only callers should use `load_config_readonly()` to skip the defensive deepcopy — that path matters in agent-loop hot spots." But `load_config()` (the default) is still called in many hot paths.
**Why invisible in previous passes**: Pass 1 (lexical) found the deepcopy pattern. Pass 5 (tool-call) did not trace config access from agent hot paths.
**Impact**: Defensive deepcopy on every config access even when config has not changed. For read-heavy operations this is pure overhead.
**Suggested fix**: Ensure hot-path callers use `load_config_readonly()` instead of `load_config()`. Audit all call sites in run_agent.py and model_tools.py to verify they use the read-only variant where no mutation occurs.
**Confidence**: Medium

---

### [Severity: Medium]
**File**: run_agent.py
**Line(s)**: 1589–1591
**Issue**: `_save_session_log()` reads the entire existing session JSON file from disk (`json.loads(log_file.read_text())`) on every save, just to compare `existing_count > len(cleaned)` and skip the write if the existing file has more messages. This is a full file read + JSON parse on every session log save, which can happen at high frequency during long conversations.
**Why invisible in previous passes**: Pass 1 (lexical) saw the read_text + json.loads but did not flag the frequency or purpose. Pass 3 (data flow) did not trace the save path.
**Impact**: Unnecessary disk I/O and JSON parsing on every session log save to protect against partial-history overwrites. For long sessions with frequent saves, this adds up.
**Suggested fix**: Store the message count in memory alongside the session log. Track `_last_saved_message_count` and compare against that without reading the file. Only read the file as a fallback if the in-memory value is unavailable.
**Confidence**: Medium

---

### [Severity: Medium]
**File**: hermes_state.py
**Line(s)**: 416–420
**Issue**: `_write_with_retry()` uses a jittered sleep retry loop for SQLite lock/busy errors: `time.sleep(jitter)` between retries. With `_WRITE_MAX_RETRIES` (default 10) retries and random jitter between `_WRITE_RETRY_MIN_S` and `_WRITE_RETRY_MAX_S`, under database contention the method will sleep and retry up to 10 times. This is a blocking busy-wait — the thread is parked but the sleep duration is non-deterministic.
**Why invisible in previous passes**: Pass 4 (concurrency) studied the executor pools and asyncio tasks but not the SQLite retry mechanism.
**Impact**: Under lock contention, retry delays accumulate. The jitter is good for preventing thundering-herd but the maximum total sleep time could be significant. In long-running gateway processes with many concurrent writers, this pattern is triggered frequently.
**Suggested fix**: Consider exponential backoff with a cap (current jitter is uniform random, not exponential). Or use SQLite built-in busy_timeout PRAGMA to let SQLite handle wait behavior rather than application-level sleep.
**Confidence**: Low

---

### [Severity: Low]
**File**: tools/registry.py
**Line(s)**: 60–64
**Issue**: `discover_builtin_tools()` calls `_module_registers_tools(path)` inside the list comprehension, which does `ast.parse()` on each tool file. The glob result is not cached, so if `discover_builtin_tools()` is called multiple times (e.g., re-discovery after a tool installation), every call re-parses all files from disk again.
**Why invisible in previous passes**: Pass 1 (lexical) saw the glob but not the repeated call sites. Pass 5 (tool-call) did not analyze discovery overhead.
**Impact**: Repeated full AST parse of all tool files on every discovery call. If called in a loop or after plugin changes, this is wasteful.
**Suggested fix**: Add a module-level cache keyed on file path + mtime. Return cached module names if files have not changed since last parse.
**Confidence**: Medium

---

### [Severity: Low]
**File**: run_agent.py
**Line(s)**: 1256–1294
**Issue**: `_flush_messages_to_db()` iterates `messages[flush_from:]` and calls `self._session_db.append_message()` once per message. For each message, it extracts role, content, tool_calls_data, and many optional fields — creating intermediate dicts and lists. This is O(n) per flush, but if called frequently with small flush batches, the overhead of many individual `append_message()` calls adds up. Also, `_is_multimodal_tool_result()` and `_multimodal_text_summary()` are called per message to transform content before writing.
**Why invisible in previous passes**: Pass 2 (control flow) analyzed the loop but did not flag the per-message overhead. Pass 4 (concurrency) focused on thread pools, not DB write batching.
**Impact**: Individual message inserts — no batch insert API is used. For long conversations with many turns, this generates many separate SQL INSERT statements.
**Suggested fix**: Add a `append_messages_batch()` method to session DB that accepts a list of messages and does a single bulk INSERT. This eliminates per-message call overhead and allows the DB to optimize the transaction.
**Confidence**: Medium

---

### [Severity: Low]
**File**: trajectory_compressor.py
**Line(s)**: 640–704, 1031–1058
**Issue**: `_generate_summary_async()` uses async LLM calls with retry and backoff. In `_process_directory_async()`, a semaphore controls concurrency, but the semaphore count is configurable and not bounded. If `max_concurrent_requests` is set high, many coroutines could be simultaneously in memory waiting for the LLM.
**Why invisible in previous passes**: Pass 4 (concurrency) studied asyncio task patterns but did not focus on trajectory processing. Pass 5 (tool-call) did not look at compressor.
**Impact**: Unbounded memory if many trajectory entries are queued and `max_concurrent_requests` is set high. Each pending coroutine holds its entry data in memory.
**Suggested fix**: Add an overall memory-based backpressure mechanism that pauses queuing when memory usage is high, rather than just semaphore-based concurrency control.
**Confidence**: Low

---

### [Severity: Low]
**File**: skills/creative/comfyui/scripts/health_check.py
**Line(s)**: 111
**Issue**: `wf = json.loads(json.dumps(SMOKE_WORKFLOW))` — unnecessary round-trip serialization to do a deep copy. Python's `copy.deepcopy()` would be more efficient and clearer in intent.
**Why invisible in previous passes**: Pass 1 (lexical) flagged json.dumps/loads. Pass 3 (data flow) did not trace the copy purpose.
**Impact**: Minor — one-time initialization code. The JSON round-trip is slower than a direct deep copy and depends on JSON serialization being invertible for the data type.
**Suggested fix**: Use `copy.deepcopy(SMOKE_WORKFLOW)` or a dict comprehension-based copy.
**Confidence**: High

---

### [Severity: Low]
**File**: plugins/memory/supermemory/__init__.py
**Line(s)**: 677
**Issue**: `schema = json.loads(json.dumps(base))  # deep copy` — unnecessary round-trip serialization for a deep copy. Comment explicitly says "deep copy" but uses JSON serialization instead of `copy.deepcopy()`.
**Why invisible in previous passes**: Pass 1 (lexical) flagged it. Pass 3 (data flow) did not note the alternative.
**Impact**: Minor — called during memory operations. The JSON round-trip could silently drop non-JSON-serializable fields if the schema contains any.
**Suggested fix**: Use `copy.deepcopy(base)` directly.
**Confidence**: High

---

**Pass #6 completed** at 2026-05-23 17:15:00 IST
**Strategy**: Performance & efficiency (FULL)
**Files scanned**: tools/registry.py, run_agent.py, hermes_state.py, hermes_cli/config.py, tools/session_search_tool.py, trajectory_compressor.py, skills/creative/comfyui/scripts/health_check.py, plugins/memory/supermemory/__init__.py
**New issues found**: 11
**Total issues so far**: 59
**Next pass strategy**: Security audit (SSRF, command injection, path traversal, unsafe deserialisation, hardcoded secrets, etc.)
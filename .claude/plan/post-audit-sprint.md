# Post-Audit Sprint — Hermes Agent

**Sprint goal:** Address all 28 findings from the May 14, 2026 multi-model audit using a multi-agent parallel execution model. Strictly severity-ordered (P0 → P2 → P3 → Stretch).

**Execution model:** Each ticket = one Claude subagent in its own git worktree. Tickets in the same wave run in parallel where files don't collide; sequential within a file. One stretch agent runs long-form on the gateway/run.py split.

**Tooling note:** `/ccg:plan` / `/ccg:execute` external CLIs (`codex`, `gemini`, `codeagent-wrapper`) are not installed. Substitute: Claude subagents (`performance-optimizer`, `python-reviewer`, `code-reviewer`, `security-reviewer`, `architect`, `tdd-guide`) launched via the Agent tool with `isolation: "worktree"`.

**Branch:** `pr-25159` (already 186 files / 18,776 insertions ahead of main — past imbue red threshold; new work should land on a fresh branch off `pr-25159` to avoid making the diff worse).

**Repo root:** `/Users/blake_t/hermes-agent`

---

## Audit findings → ticket map

| Ticket | Severity | Finding # | File(s) |
|---|---|---|---|
| W1-T01 | P0 | #1 Kanban schema bloat | `tools/kanban_tools.py:685-1060` |
| W1-T02 | P0 | #2 Unbounded LLM fan-out | `tools/web_tools.py:851-879` |
| W1-T03 | P0 | #3 deepcopy on every Anthropic turn | `agent/prompt_caching.py:62`, `run_agent.py:13597` |
| W1-T04 | P0 | #4 jittered_backoff never called | `agent/auxiliary_client.py:4325-4340, 4675-4690` |
| W1-T05 | P0 | #5 Browser snapshot LLM no opt-out | `tools/browser_tool.py:2055-2106` |
| W2-T06 | P2 | #13 _load_gateway_config 15+ calls/msg | `gateway/run.py` (per-message handler) |
| W2-T07 | P2 | #14 Feishu blocking SDK | `gateway/platforms/feishu.py:4291, 4318` |
| W2-T08 | P2 | #15 tool_output_limits no cache | `tools/tool_output_limits.py:55-82` |
| W2-T09 | P2 | #16 holographic.encode_atom no memo | `plugins/memory/holographic/holographic.py:43-67` |
| W2-T10 | P2 | #17 ephemeral aiohttp/httpx clients | `gateway/platforms/discord.py:1694-1768`, `gateway/platforms/yuanbao.py:741` |
| W2-T11 | P2 | #18 Sync httpx in async Tavily | `tools/web_tools.py:417-436` |
| W2-T12 | P2 | #19 35 sequential regex passes | `plugins/hermes-achievements/dashboard/plugin_api.py:340-417` |
| W2-T13 | P2 | #20 Unbounded Feishu caches | `gateway/platforms/feishu.py:1411-1412` |
| W2-T14 | P2 | #21 Browser subprocess no pool | `tools/browser_tool.py:796, 1926` |
| W2-T15 | P2 | #22 Yuanbao logs every WS frame | `gateway/platforms/yuanbao.py:3021, 2985, 2914` |
| W2-T16 | P2 | agent-perf-3 sync compress_context | `agent/auxiliary_client.py`, `run_agent.py:11014,13208,15379,15530,15730,16715` |
| W2-T17 | P2 | agent-perf-4 OAuth tool-name scan | `agent/anthropic_adapter.py:1963-1971` |
| W2-T18 | P2 | agent-perf-5 pricing fetch TTL | `agent/usage_pricing.py:591, 662` |
| W2-T19 | P2 | agent-quality-3 deprecated get_event_loop | `agent/auxiliary_client.py:3560, 3737` |
| W2-T20 | P2 | gateway-quality-1 Feishu drainer time.sleep | `gateway/platforms/feishu.py:2277-2358` |
| W2-T21 | P2 | gateway-quality-6 PID-wait time.sleep | `gateway/run.py:16335, 16344` |
| W2-T22 | P2 | gateway-quality-4 print() in async hot paths | `gateway/platforms/discord.py:2801,2828,...`, `gateway/platforms/telegram.py:3300,3346` |
| W2-T23 | P2 | plugins-perf-1 discover_memory_providers eager | `plugins/memory/__init__.py:123-157` |
| W2-T24 | P2 | plugins-perf-4 yaml + plugin.yaml uncached | `plugins/memory/__init__.py:137-140, 383-388` |
| W2-T25 | P2 | plugins-perf-5 httpx eager imports | `plugins/teams_pipeline/pipeline.py:17`, `plugins/spotify/client.py` |
| W2-T26 | P2 | tools-perf-6 numpy eager imports | `tools/neutts_synth.py:23`, `tools/voice_mode.py:39` |
| W3-S1 | P3 | S1 shell=True injection | `tools/transcription_tools.py:511` |
| W3-S2 | P3 | S2 GITHUB_TOKEN leak | `tools/tirith_security.py:207-213` |
| W3-S3 | P3 | S3 hindsight auto-upgrade | `plugins/memory/hindsight/__init__.py:1083` |
| W3-S4 | P3 | S4 Telegram webhook verification gap | `gateway/platforms/telegram.py:1321-1349` |
| W3-S5 | P3 | S5 retry_scheduled dead state | `plugins/teams_pipeline/pipeline.py:40, 414-420` |
| W3-S6 | P3 | S6 path canonicalization gap | `tools/file_tools.py:158-176` |
| STRETCH | P1 | God-file split | `gateway/run.py` (16,672 lines) |

---

## Wave 1 — P0 (parallel-safe, 5 agents simultaneously)

All five tickets touch different files. Launch as 5 parallel subagents in 5 separate worktrees off `pr-25159`. Each agent gets the audit finding text, the file/line refs, and acceptance criteria. No inter-ticket dependencies.

### W1-T01 — Trim kanban tool schemas
- **File:** `tools/kanban_tools.py:685-1060`
- **Agent profile:** `everything-claude-code:performance-optimizer`
- **Change shape:** Rewrite each of the 9 schema `description` fields from 3-6 sentence workflow rationale to 1-2 sentence call-site guidance. Move removed prose into module-level docstring or `docs/kanban_tools.md` so nothing is lost.
- **Acceptance:**
  - Each schema `description` ≤ 280 characters (~70 tokens).
  - Total kanban schema bytes drop from ~13,810 to ≤4,000 (target: ~1,000 tokens, was ~3,452).
  - Existing kanban tests still pass.
  - Add a unit test that asserts schema-description length ≤ 280 chars for each tool to prevent regression.
- **Pseudo-code (representative trim):**
  ```python
  # BEFORE
  "description": "Used by orchestrator workers to fan out — decompose work into child tasks. "
                 "Each child task becomes its own kanban card. This is the primary mechanism for ..."
  # AFTER
  "description": "Decompose work into child tasks; each becomes a kanban card."
  ```
- **Risk:** LLM picks wrong tool because description is too terse. Mitigation: A/B compare tool-selection accuracy on a held-out set of 20 orchestrator-style prompts before/after.

### W1-T02 — Cap web_tools chunked LLM fan-out
- **File:** `tools/web_tools.py:851-879` (and synthesis call ~880)
- **Agent profile:** `performance-optimizer`
- **Change shape:**
  ```python
  _CHUNK_LLM_SEMAPHORE = asyncio.Semaphore(int(os.getenv("HERMES_WEB_CHUNK_LLM_CONCURRENCY", "3")))

  async def _summarize_chunk_bounded(chunk):
      async with _CHUNK_LLM_SEMAPHORE:
          return await _call_summarizer_llm(chunk, max_tokens=4_000)
  ```
- **Acceptance:**
  - Concurrent in-flight LLM calls in `_process_large_content_chunked` ≤ 3 (env-overridable).
  - Per-chunk `max_tokens` ≤ 4,000 (was 10,000).
  - Synthesis-pass `max_tokens` unchanged at 20,000.
  - Mock auxiliary client, feed 490 KB page, assert ≤ 3 concurrent calls.
- **Risk:** Slower long-page summarization. Mitigation: synthesis pass already does reunification at higher quality; net latency may improve due to reduced auxiliary-provider rate-limiting.

### W1-T03 — Replace deepcopy with targeted shallow mutation in prompt cache markers
- **File:** `agent/prompt_caching.py:62`, call site `run_agent.py:13597`
- **Agent profile:** `python-reviewer`
- **Change shape:**
  ```python
  def apply_anthropic_cache_control(api_messages, ...):
      out = list(api_messages)
      for idx in cache_marker_indices(out):
          msg = dict(out[idx])
          msg["content"] = [dict(b) for b in msg["content"]]
          # mutate cache_control on the final block of msg["content"]
          out[idx] = msg
      return out
  ```
- **Acceptance:**
  - No `copy.deepcopy` in this path.
  - Original `api_messages` list unmodified after function returns (id-comparison test).
  - Profile a 200-turn session: function < 1ms in the hot path.
- **Risk:** Aliasing bug. Mitigation: shallow-copy each block we modify; integration test on a 500-turn synthetic session.

### W1-T04 — Wire jittered_backoff into auxiliary_client retry paths
- **File:** `agent/retry_utils.py` (already exists), `agent/auxiliary_client.py:4325-4340 (sync)` and `4675-4690 (async)`
- **Agent profile:** `python-reviewer` + `tdd-guide`
- **Change shape:**
  ```python
  from .retry_utils import jittered_backoff

  # sync path
  for attempt in range(MAX_RETRIES):
      try: ...
      except RateLimitError as err:
          ra = _parse_retry_after(err.response)
          delay = max(jittered_backoff(attempt), ra or 0)
          time.sleep(delay)
          continue

  # async path mirrors with await asyncio.sleep(delay)
  ```
- **Acceptance:**
  - Both sync and async credential-pool recovery paths call `jittered_backoff`.
  - `Retry-After` honored if present and < 60s.
  - Simulate 3 consecutive 429s; assert total wall time ≥ sum of jittered delays.
- **Risk:** Real production retries slower (intentional). Mitigation: log every backoff at INFO with chosen delay.

### W1-T05 — Add HERMES_BROWSER_SNAPSHOT_LLM opt-out
- **File:** `tools/browser_tool.py:2055-2106`
- **Agent profile:** `performance-optimizer`
- **Change shape:**
  ```python
  async def _summarize_snapshot_with_llm(snapshot, ...):
      if os.getenv("HERMES_BROWSER_SNAPSHOT_LLM", "1") == "0":
          return _truncate_snapshot(snapshot)
      ...
  ```
- **Acceptance:**
  - Env var defaults to `"1"` (preserve current behavior).
  - Document in `.env.example` and `docs/`.
  - Truncation path produces deterministic, parseable output.
- **Risk:** None — pure opt-out, off by default.

**Wave 1 gating:** All five tickets must merge before Wave 2 starts. W1-T02 collides with W2-T11 (both `tools/web_tools.py`); W1-T04 collides with W2-T16, W2-T19 (both `agent/auxiliary_client.py`).

---

## Wave 2 — P2 (sequenced to manage file collisions)

21 tickets. File-collision graph drives sequencing:

```
auxiliary_client.py:  W1-T04 → W2-T16 → W2-T19            (serial within file)
run.py (gateway):     W2-T06 → W2-T21                      (serial)
feishu.py:            W2-T07 → W2-T13 → W2-T20             (serial)
yuanbao.py:           W2-T10 → W2-T15                      (serial; T10 also touches discord.py)
discord.py:           W2-T10 → W2-T22                      (W2-T22 also touches telegram.py)
telegram.py:          W2-T22 → W3-S4                       (serial, W3-S4 in Wave 3)
memory/__init__.py:   W2-T23 → W2-T24                      (serial)
web_tools.py:         W1-T02 → W2-T11                      (serial)
plugin_api.py:        W2-T12                                (standalone)
holographic.py:       W2-T09                                (standalone)
tool_output_limits.py:W2-T08                                (standalone)
browser_tool.py:      W1-T05 → W2-T14                      (serial)
anthropic_adapter.py: W2-T17                                (standalone)
usage_pricing.py:     W2-T18                                (standalone)
neutts_synth.py + voice_mode.py: W2-T26                     (parallel pair)
teams_pipeline.py + spotify/client.py: W2-T25               (parallel pair)
```

**Parallelism plan:**
- **Wave 2A (10 parallel):** W2-T06, W2-T07, W2-T08, W2-T09, W2-T10, W2-T12, W2-T16, W2-T18, W2-T23, W2-T26
- **Wave 2B (8 parallel):** W2-T11, W2-T13, W2-T15, W2-T17, W2-T22, W2-T24, W2-T25, W2-T14
- **Wave 2C (3 parallel):** W2-T19, W2-T20, W2-T21

### Wave 2A tickets

#### W2-T06 — Hoist `_load_gateway_config` into per-message handler
- **File:** `gateway/run.py` (15+ call sites: 6892, 7045, 7195, 7645, 7672, 8885, ...)
- **Change:** Single call at message-handler entry; pass config dict down by parameter. Module-level TTL cache (60s) on `_load_gateway_config` as defense-in-depth.
- **Acceptance:** Per-message `_load_gateway_config` call count = 1. Existing config-hot-reload tests still pass.

#### W2-T07 — Convert Feishu SDK calls to async or shared httpx
- **File:** `gateway/platforms/feishu.py:4291, 4318` (and the other 16 `asyncio.to_thread` sites)
- **Change:** Either upgrade to async Feishu SDK (preferred) or build a thin async wrapper around the REST endpoints with a module-level `httpx.AsyncClient`.
- **Acceptance:** Zero `asyncio.to_thread(client.im.v1...)` calls in hot path. Feishu outbound p95 latency ↓ ≥ 30%.

#### W2-T08 — `lru_cache` on `get_tool_output_limits`
- **File:** `tools/tool_output_limits.py:55-82`
- **Change:** `@functools.lru_cache(maxsize=1)` on `get_tool_output_limits` and `get_max_bytes`. Expose `cache_clear()` for tests.
- **Acceptance:** Per-terminal-call cost < 5µs.

#### W2-T09 — `lru_cache` on `holographic.encode_atom`
- **File:** `plugins/memory/holographic/holographic.py:43-67`
- **Change:** `@functools.lru_cache(maxsize=4096)`. Confirm determinism.
- **Acceptance:** Cache hit rate ≥ 70% on a 20-token, 5-entity fact write across 10 writes.

#### W2-T10 — Reuse HTTP clients in Discord + Yuanbao
- **Files:** `gateway/platforms/discord.py:1694-1768, 2527-2541, 2606-2620`; `gateway/platforms/yuanbao.py:741`
- **Change:** Hoist `aiohttp.ClientSession` to `DiscordAdapter` instance level (created at startup, closed on shutdown). Hoist `httpx.AsyncClient` to `SignManager` class level.
- **Acceptance:** Zero per-call `ClientSession()` / `AsyncClient()` construction in the affected methods.

#### W2-T12 — Combine 35 regex passes into single Scanner
- **File:** `plugins/hermes-achievements/dashboard/plugin_api.py:340-417`
- **Change:** Single `re.compile` with alternation, or `re.Scanner`. Single pass over `full_text` → `Counter` of match types.
- **Acceptance:** `analyze_messages` runtime ↓ ≥ 3× on 100KB session.

#### W2-T16 — Make `_compress_context` async
- **Files:** `agent/auxiliary_client.py`, `run_agent.py:11014, 13208, 15379, 15530, 15730, 16715`
- **Change:** Convert `_compress_context` to `async def`, use `async_call_llm`. Update 6 call sites to `await`. Provide `_sync_compress_context` shim for sync callers.
- **Acceptance:** No sync `call_llm` in compression path. Async-context smoke test does not block event loop.

#### W2-T18 — Increase pricing-fetch TTL
- **File:** `agent/usage_pricing.py:591, 662`
- **Change:** Custom-endpoint TTL 5min → 1h. Add stale-while-revalidate.
- **Acceptance:** Per-turn cost-accounting median latency < 100µs.

#### W2-T23 — TTL-cache `discover_memory_providers`
- **File:** `plugins/memory/__init__.py:123-157`
- **Change:** `@functools.lru_cache(maxsize=1)` keyed on directory mtime hash. Provide `cache_clear()`.
- **Acceptance:** Settings-page warm-cache `_load_provider_from_dir` calls drop from 8 to 0.

#### W2-T26 — Lazy numpy imports
- **Files:** `tools/neutts_synth.py:23`, `tools/voice_mode.py:39`
- **Change:** Move `import numpy as np` from module top to first-use site.
- **Acceptance:** Cold import no longer pulls numpy.

### Wave 2B tickets

#### W2-T11 — Async Tavily request
- **File:** `tools/web_tools.py:417-436`
- **Change:** `httpx.post` → `httpx.AsyncClient().post` inside `async def _tavily_request`. Wrap sync entry with `asyncio.to_thread`.
- **Acceptance:** No `httpx.post` in async-reachable code paths.

#### W2-T13 — Bound Feishu adapter caches
- **File:** `gateway/platforms/feishu.py:1411-1412`
- **Change:** Plain dicts → `cachetools.TTLCache(maxsize=1000, ttl=3600)`. Add `_chat_info_cache` TTL.
- **Acceptance:** Memory growth bounded under 24h load test.

#### W2-T15 — Demote Yuanbao per-frame logs
- **File:** `gateway/platforms/yuanbao.py:3021, 2985, 2914`
- **Change:** Demote "Push received", "HEARTBEAT_ACK", "PING sent" to DEBUG. Gate remaining INFO behind `HERMES_DEBUG_YUANBAO=1`.
- **Acceptance:** INFO log volume ↓ ≥ 80% in a 5-min stream test.

#### W2-T17 — OAuth tool-name scan optimization
- **File:** `agent/anthropic_adapter.py:1963-1971`
- **Change:** Track prefix-applied state on messages at append time (`_mcp_prefixed: True`). Scan only new messages each turn.
- **Acceptance:** Per-turn scan time on 200-turn session → O(1) added blocks.

#### W2-T22 — Replace `print()` in async hot paths
- **Files:** `gateway/platforms/discord.py:2801, 2828, 2834, 2840, 4314, 4316, 4328, 4330`; `gateway/platforms/telegram.py:3300, 3346`
- **Change:** `print(...)` → `logger.debug(...)` / `logger.warning(...)` with lazy `%` formatting.
- **Acceptance:** Zero `print(` in async methods of `discord.py`, `telegram.py`, `feishu.py`. Pre-commit grep rule.

#### W2-T24 — Cache plugin.yaml reads and hoist yaml import
- **Files:** `plugins/memory/__init__.py:137-140, 383-388`; `plugins/context_engine/__init__.py`
- **Change:** Move `import yaml` to module top. mtime-keyed cache for `yaml.safe_load(plugin.yaml)`.
- **Acceptance:** Repeated `discover_*_providers` re-parses YAML only on mtime change.

#### W2-T25 — Lazy httpx imports in plugins
- **Files:** `plugins/teams_pipeline/pipeline.py:17`, `plugins/spotify/client.py`
- **Change:** Move `import httpx` from module top to first-use site.
- **Acceptance:** Plugin import no longer imports httpx unless called.

#### W2-T14 — Browser process pool (LARGE)
- **File:** `tools/browser_tool.py:796, 1926`
- **Agent profile:** `architect`
- **Change:** Replace per-call `subprocess.Popen([agent-browser, ...])` with `BrowserProcessPool` (env: `HERMES_BROWSER_POOL_MAX=4`). Per-process session ID. Health-check via stdin ping; respawn on failure.
- **Acceptance:** 10 sequential `browser_navigate` calls reuse same process. Warm-call latency ↓ ≥ 60%.
- **Risk:** Zombies on hang. Mitigation: timeout + force-kill + respawn. **Defer if scope-creep** — flag as P1 follow-up.

### Wave 2C tickets

#### W2-T19 — Replace `get_event_loop()` with `get_running_loop()`
- **File:** `agent/auxiliary_client.py:3560, 3737`
- **Change:** Surgical replacement. Catch `RuntimeError` for non-coroutine context.
- **Acceptance:** No `_aio.get_event_loop()` in cache paths. Async client cache hit ≥ 95% in a 100-call test.

#### W2-T20 — Feishu drainer `threading.Event` instead of `time.sleep`
- **File:** `gateway/platforms/feishu.py:2277-2358`
- **Change:** 250ms poll loop → `threading.Event` set by asyncio loop on readiness.
- **Acceptance:** Drainer wake-up latency 250ms worst → ≤ 5ms. Thread pile-up eliminated.

#### W2-T21 — PID-wait `asyncio.sleep`
- **File:** `gateway/run.py:16335, 16344`
- **Change:** `time.sleep(0.5)` → `await asyncio.sleep(0.5)` if async-reachable; else `loop.run_in_executor`.
- **Acceptance:** No `time.sleep` in async-reachable code path of `run.py`.

---

## Wave 3 — P3 Security (6 parallel agents, all independent files)

### W3-S1 — Fix shell=True injection
- **File:** `tools/transcription_tools.py:511`
- **Agent profile:** `security-reviewer`
- **Change:** `subprocess.run(command, shell=True, ...)` → `subprocess.run(shlex.split(command), shell=False, ...)`. If template legitimately needs shell features, parse argv at template-definition time, not execution time.
- **Acceptance:** No `shell=True` in this file. Unit test with backticks / `$(...)` asserts no expansion.

### W3-S2 — Scope GITHUB_TOKEN to github hosts
- **File:** `tools/tirith_security.py:207-213`
- **Agent profile:** `security-reviewer`
- **Change:** Inject `Authorization: token ...` only when `urlparse(url).hostname in {"api.github.com", "github.com", "raw.githubusercontent.com"}` or ends with `.githubusercontent.com`. Use existing `tools.url_safety`.
- **Acceptance:** Unit test asserts header absent for `evil.example.com`.

### W3-S3 — Gate hindsight auto-upgrade
- **File:** `plugins/memory/hindsight/__init__.py:1083`
- **Agent profile:** `security-reviewer`
- **Change:** Replace unconditional `subprocess.run([uv_path, "pip", "install", ...])` with: (a) hard `logger.warning` with manual upgrade instructions; (b) refuse plugin init if version too low; (c) only auto-upgrade if `HERMES_HINDSIGHT_AUTO_UPGRADE=1` + interactive consent.
- **Acceptance:** Default behavior: warn and refuse. No implicit network/filesystem mutation.

### W3-S4 — Telegram webhook secret verification middleware
- **File:** `gateway/platforms/telegram.py:1321-1349`
- **Agent profile:** `security-reviewer`
- **Change:** aiohttp middleware rejects POSTs missing/mismatching `X-Telegram-Bot-Api-Secret-Token`. Log rejection at WARNING with source IP. Explicitly pass `secret_token=webhook_secret` to `run_webhook(...)`.
- **Acceptance:** Integration test: missing/wrong header → 401; right header → 200.

### W3-S5 — Fix retry_scheduled dead-end
- **File:** `plugins/teams_pipeline/pipeline.py:40, 414-420`
- **Agent profile:** `python-reviewer`
- **Change:** Either (a) remove `retry_scheduled` from `TERMINAL_PIPELINE_STATES` and add retry loop in `runtime.py` (`max_retries=3`, exp backoff); or (b) rename `failed_retryable` and treat as failure with alert.
- **Acceptance:** No job left in `retry_scheduled`. Unit test: 3 STT failures → terminal state `failed` with alert metadata.

### W3-S6 — Path canonicalization
- **File:** `tools/file_tools.py:158-176`
- **Agent profile:** `security-reviewer`
- **Change:** `Path(path).resolve()` before prefix check. Reject paths whose resolved form leaves allowed roots.
- **Acceptance:** Symlink to `/etc/passwd` is rejected.

---

## STRETCH — Gateway `run.py` god-file split

- **File:** `gateway/run.py` (16,672 lines)
- **Agent profile:** `architect` (single agent, long-running, isolated worktree, **runs LAST** after Waves 1-3 merge)
- **Scope — initial decomposition:**
  - `gateway/runtime/lifecycle.py` — process start/stop, PID file, restart, takeover
  - `gateway/runtime/message_pipeline.py` — `_process_message` + per-message hot path
  - `gateway/runtime/config_loader.py` — `_load_gateway_config` + hot-reload
  - `gateway/runtime/agent_cache.py` — `_AGENT_CACHE_*` (LRU/TTL)
  - `gateway/runtime/health.py` — health-check / readiness
  - `gateway/runtime/cli.py` — CLI entrypoint glue
  - `gateway/run.py` shrinks to a thin re-export shim
- **Approach:**
  1. Identify cohesive function clusters (call-graph via `pyan3` or grep `def `).
  2. Move modules one cluster at a time, each move = one commit.
  3. Run full gateway test suite + manual smoke test of each platform after each commit.
  4. Keep `gateway/run.py` re-exporting old public names; deprecate after caller audit.
- **Acceptance:**
  - `gateway/run.py` ≤ 1,000 lines (mostly imports + CLI entry).
  - No public API breakage (existing `from gateway.run import X` works).
  - Per-message hot path no perf regression.
- **Risk:** Merge conflicts with Waves 1-3 if parallel. Mitigation: runs LAST.
- **Scope-creep escape hatch:** Stop after `lifecycle.py` + `message_pipeline.py` extraction; defer remainder.

---

## Multi-agent execution playbook

```
Stage 0 — branch hygiene
  git checkout pr-25159
  git pull --ff-only
  git checkout -b post-audit-sprint/wave-1

Stage 1 — Wave 1 (5 parallel agents)
  Per W1 ticket: spawn agent with isolation: "worktree" off post-audit-sprint/wave-1
                 agent commits to post-audit-sprint/W1-T0X
  After all 5 complete: PR each → review → merge to post-audit-sprint/wave-1
  Gate: all 5 PRs merged before Stage 2.

Stage 2 — Wave 2A (10 parallel agents)
  Branch post-audit-sprint/wave-1 → post-audit-sprint/wave-2
  10 agents, each in own worktree on post-audit-sprint/W2-T<n>
  Merge in parallel as each lands.

Stage 3 — Wave 2B (8 parallel agents)
  Depends on Stage 2 merges (file-collision sequencing).

Stage 4 — Wave 2C (3 parallel agents — tail collisions)

Stage 5 — Wave 3 (6 parallel security agents)
  Branch off latest; can run as soon as files unblock.

Stage 6 — STRETCH (1 long-running agent)
  Branch off latest. Worktree isolated. LAST.
```

**Tool-substitute reminder:** Each "agent" = Claude subagent invoked via `Agent` tool with `isolation: "worktree"`. Profile per ticket specified above.

---

## Key files (rolled up)

| File | Tickets | Operation |
|------|---------|-----------|
| `tools/kanban_tools.py` | W1-T01 | Modify (schema trim) |
| `tools/web_tools.py` | W1-T02, W2-T11 | Modify (semaphore, async Tavily) |
| `agent/prompt_caching.py` | W1-T03 | Modify (shallow copy) |
| `agent/auxiliary_client.py` | W1-T04, W2-T16, W2-T19 | Modify (retry, async compress, get_running_loop) |
| `tools/browser_tool.py` | W1-T05, W2-T14 | Modify (opt-out + process pool) |
| `gateway/run.py` | W2-T06, W2-T21, STRETCH | Modify + split |
| `gateway/platforms/feishu.py` | W2-T07, W2-T13, W2-T20 | Modify (async, cache bounds, drainer) |
| `tools/tool_output_limits.py` | W2-T08 | Modify (lru_cache) |
| `plugins/memory/holographic/holographic.py` | W2-T09 | Modify (lru_cache) |
| `gateway/platforms/discord.py` | W2-T10, W2-T22 | Modify (session reuse, print → logger) |
| `gateway/platforms/yuanbao.py` | W2-T10, W2-T15 | Modify (client reuse, log demotion) |
| `plugins/hermes-achievements/dashboard/plugin_api.py` | W2-T12 | Modify (regex scanner) |
| `run_agent.py` | W1-T03, W2-T16 | Modify (cache markers, async compress call sites) |
| `agent/anthropic_adapter.py` | W2-T17 | Modify (OAuth scan) |
| `agent/usage_pricing.py` | W2-T18 | Modify (TTL + SWR) |
| `gateway/platforms/telegram.py` | W2-T22, W3-S4 | Modify (logger, webhook auth) |
| `plugins/memory/__init__.py` | W2-T23, W2-T24 | Modify (TTL cache, yaml hoist) |
| `plugins/context_engine/__init__.py` | W2-T24 | Modify (yaml hoist) |
| `plugins/teams_pipeline/pipeline.py` | W2-T25, W3-S5 | Modify (lazy httpx, retry state) |
| `plugins/spotify/client.py` | W2-T25 | Modify (lazy httpx) |
| `tools/neutts_synth.py` | W2-T26 | Modify (lazy numpy) |
| `tools/voice_mode.py` | W2-T26 | Modify (lazy numpy) |
| `tools/transcription_tools.py` | W3-S1 | Modify (shell=False) |
| `tools/tirith_security.py` | W3-S2 | Modify (token scoping) |
| `plugins/memory/hindsight/__init__.py` | W3-S3 | Modify (gate auto-upgrade) |
| `tools/file_tools.py` | W3-S6 | Modify (path canonicalization) |

---

## Risks and mitigation

| Risk | Mitigation |
|------|------------|
| Multiple agents conflict on shared files | Strict file-sequencing per wave; one agent per file per wave. |
| Branch already 18,776 lines ahead — 30 more PRs make it untouchable | Land each ticket as own PR back to `pr-25159`. Optionally use a `post-audit/` parent branch and merge wave branches in. |
| STRETCH conflicts with Wave 2 gateway tickets | Run STRETCH LAST. All Wave 2 gateway tickets must merge first. |
| W1-T04 retry-timing changes surface latent rate-limit bugs | Full integration suite + 1h live test against sandbox provider before merging. |
| W1-T01 schema trim hurts LLM tool-selection accuracy | A/B test on 20 held-out prompts before merging; revert per-tool if accuracy ↓ > 5%. |
| Lazy imports change cold-start ordering, surface import-time side effects | Smoke test that imports each plugin module in isolation and asserts no side effect. |
| W2-T14 (browser pool) larger than others — scope creep | Hard cap: not landed by mid-sprint → defer to follow-up. Document interim state. |
| W3-S3 hindsight gate breaks workflows depending on auto-upgrade | Loud release-note + module-load warning when upgrade needed. |

---

## Out-of-scope (deferred to follow-up sprints)

| Finding | Reason for deferral |
|---|---|
| Split `agent/auxiliary_client.py` (4,750 lines) | Wave 2 makes targeted fixes; full split is its own sprint. |
| Split `tools/browser_tool.py` (3,647 lines) | Wave 2 makes targeted fixes; W2-T14 (process pool) already large. |
| Deduplicate `gateway/platforms/*.py` (Discord/Telegram/Feishu/Yuanbao/API copy-paste) | Separate refactor sprint; touches 25K+ lines. |
| Consolidate `plugins/memory/__init__.py` + `plugins/context_engine/__init__.py` shared loader | Single follow-up ticket worth ~300 lines net deletion. |
| Consolidate `image_gen/openai` vs `image_gen/openai-codex` | Own ticket, ~350 lines net deletion. |
| Audit root-level god-files (`run_agent.py` 17K lines, `cli.py` 16K lines, `hermes_cli/main.py` 11K lines) | Separate audit sprint required first. |

---

## SESSION_ID (for /ccg:execute use)

- **CODEX_SESSION:** N/A — codex CLI not installed; substitute = Claude subagents via `Agent` tool.
- **GEMINI_SESSION:** N/A — gemini CLI not installed; substitute = Claude subagents via `Agent` tool.

**Substitute execution command:** Run each ticket as a Claude subagent invocation. `Agent` tool with `isolation: "worktree"` creates a clean working copy per ticket. The audit context for each ticket = ticket spec in this plan + the audit finding text from the May 14, 2026 review.

---

## Definition of done

- All 28 P0/P2/P3 tickets merged to `pr-25159` (or a fresh branch off it).
- STRETCH split: gateway/run.py either fully split or partially split with explicit follow-up tickets.
- Full test suite green.
- Performance benchmark suite shows:
  - ≥ 30% reduction in per-turn tool-schema tokens.
  - ≥ 30% reduction in long-page web_fetch peak concurrent LLM calls.
  - Zero `time.sleep` in async-reachable code.
  - Zero unbounded caches on platform adapters.
- Sprint retro doc summarizing actual vs. estimated effort per ticket.

# Hermes Runtime Patches

Patches applied via cherry-pick from upstream (NousResearch/hermes-agent). 
Each entry records the upstream commit, our local commit, and what it does.

DO NOT run `hermes update` — it wipes these patches via git pull/reset.
Use `git cherry-pick <sha>` for future upstream integration.

## Active Patches

### P152 — Session state survives gateway restarts
- **Cherry-picked:** 2026-05-16
- **Upstream:** `e0e7397c` fix(session): persist auto-reset state across gateway restarts
- **Local:** `0a67a1a21`
- **Files:** gateway/session.py, gateway/run.py
- **Why:** Session auto-reset state persists across gateway restarts (MOL-576).

### P153 — Skip OpenViking upload symlinks in memory
- **Cherry-picked:** 2026-05-16
- **Upstream:** `63991bbd` fix(memory): skip OpenViking upload symlinks
- **Local:** `ebf5a3a88`
- **Files:** plugins/memory/tiered store + upload
- **Why:** Prevents memory provider from following symlinks in upload dirs.

### P154 — Silence memory provider teardown output
- **Cherry-picked:** 2026-05-16
- **Upstream:** `55ba02be` fix(background-review): silence memory provider teardown output leak
- **Local:** `90964fc77`
- **Files:** run_agent.py
- **Why:** Suppresses noisy memory provider shutdown output during background review.
- **Conflict:** run_agent.py — resolved by accepting incoming (tool whitelist + provider shutdown).

### P155 — Show context compaction status
- **Cherry-picked:** 2026-05-16
- **Upstream:** `00ad3d3c` fix: show context compaction status
- **Local:** (auto-merged into 90964fc77 sequence)
- **Files:** run_agent.py
- **Why:** Visibility into when context compaction fires — we can now see it happening.

### P156 — Compression model context-length detection with custom providers
- **Cherry-picked:** 2026-05-16
- **Upstream:** `7becb19e` fix(auxiliary): forward custom_providers to compression model context-length detection
- **Local:** `2b646ed20`
- **Files:** agent/auxiliary_client.py
- **Why:** Compression model works correctly with custom providers (our DeepSeek setup).

### P157 — Keep image results from poisoning text-only sessions
- **Cherry-picked:** 2026-05-16
- **Upstream:** `a28add19` fix(agent): keep image tool results from poisoning text-only sessions
- **Local:** `f2cf44134`
- **Files:** run_agent.py
- **Why:** Prevents image tool results from silently consuming context in text-only model sessions.
- **Conflict:** run_agent.py — resolved by accepting incoming (new image-rejection error patterns).

### P158 — Docs: media impact on session context
- **Cherry-picked:** 2026-05-16
- **Upstream:** `1dd33988` docs: clarify media impact on session context
- **Local:** `707d40b59`
- **Files:** website/docs/user-guide/sessions.md
- **Why:** Documents how media attachments affect context budget.

## Unreachable (need fetch)

These commits are on upstream main but not in our local object store (after last fetch cutoff):

- `627f8a5f` security: sanitize tool error strings before injecting into model context (May 16)
- `585d6b64` fix(gateway): merge rapid TEXT follow-ups during active sessions (May 16)
- `068c24f8` feat(deepseek): add thinking.type + reasoning_effort mapping for DeepSeek API (Apr 24)
- `518f3955` fix(gateway): keep running when platforms fail; per-platform circuit breaker (May 15)
- `2d7182f7` fix(delegate): prevent orphan heartbeat thread (May 15)
- `60683633` fix(delegate): guard heartbeat join against unstarted thread (May 15)
- `6ba35ec3` terminal: tighten dangerous-command detection (May 16)
- `016c772e` feat(plugins): tool override flag for replacing built-in tools (May 16)
- `395e9dd9` feat: supports_parallel_tool_calls for MCP servers (May 16)
- `4e89c530` fix(async): close unscheduled coroutines in threadsafe bridges (May 15)

### P159 — Skip providers without credentials
- **Cherry-picked:** 2026-05-16
- **Upstream:** `057f5a31` fix(auxiliary): skip providers without credentials immediately
- **Local:** `f15858e90`
- **Files:** agent/auxiliary_client.py
- **Why:** Faster session startup — don't attempt providers that have no credentials.

### P160 — Stop retrying initial MCP auth failures
- **Cherry-picked:** 2026-05-16
- **Upstream:** `1247ff2d` fix: stop retrying initial MCP auth failures
- **Local:** `db6a090fd`
- **Files:** 2 files in agent/
- **Why:** MCP tools fail fast instead of retry-looping on auth errors.

### P161 — Perf: list+join in agent loop
- **Cherry-picked:** 2026-05-16
- **Upstream:** `4f8aaf10` perf(run_agent): accumulate length-continuation prefix via list+join
- **Local:** `d5f60d81a`
- **Files:** run_agent.py
- **Why:** Lower latency, less memory pressure — replaces repeated string concatenation with list append/join.

### P162 — Terminal safety filter false positives
- **Cherry-picked:** 2026-05-16
- **Upstream:** `364ddd45` fix(terminal): prevent safety filter false positives on keywords inside quoted strings
- **Local:** `72d243b5e`
- **Files:** tools/terminal_tool.py
- **Why:** Our terminal commands get blocked less often when keywords appear inside quoted strings.

### P163 — Gateway forward images to background tasks
- **Cherry-picked:** 2026-05-16
- **Upstream:** `3adde245` fix(gateway): forward image attachments to background agent tasks
- **Local:** `a9e7eb773`
- **Files:** gateway/run.py
- **Why:** Image attachments in cron/scheduled tasks actually get forwarded to the agent.

### P164 — Telegram model-switch fix
- **Cherry-picked:** 2026-05-16
- **Upstream:** `26deeea8` fix(telegram): restore model-switch success path + author map
- **Local:** `5fce0dfd9`
- **Files:** gateway/platforms/telegram.py
- **Why:** Model switching in Telegram works again. Uses format_message() wrapper for safe markdown.
- **Conflict:** telegram.py (MARKDOWN_V2 + format_message wrapper — accepted incoming), test file deleted (kept our deletion).

### P165 — Gateway 429 rate-limit guard
- **Cherry-picked:** 2026-05-16
- **Upstream:** `23ac522d` fix(gateway): isinstance-guard string-form 429 error body
- **Local:** `09b31ea09`
- **Files:** gateway/run.py
- **Why:** Properly handles rate-limit responses when OpenRouter throttles us.

### P166 — Cron name-based lookup
- **Cherry-picked:** 2026-05-16
- **Upstream:** `6682f91b` feat(cron): support name-based lookup for job operations
- **Local:** `ccbef02ed`
- **Files:** cron/jobs.py, hermes_cli/cron.py, tools/cronjob_tools.py
- **Why:** Use `cronjob action="list" --name="..."` instead of hunting job IDs. Directly useful for our 14+ cron jobs.

## Skipped (not applicable)

- `12f755c9` fix(codex-runtime): retire wedged sessions — Codex-only, we use DeepSeek. Files deleted in our tree.

# OpenClaw ↔ Hermes Bidirectional MCP + Memory Integration Implementation Plan

> **For Hermes:** Use subagent-driven-development skill to implement this plan task-by-task.

**Goal:** Build the simplest useful bidirectional OpenClaw/Hermes integration: both agents can send/read messages through each other, Hermes can search OpenClaw memory and LCM history through OpenClaw's existing tool surfaces, and OpenClaw can query Hermes memory/session recall through a small Hermes memory MCP server only if needed.

**Architecture:** Prefer existing native bridges and OpenClaw tool projection over new deep agent-brain RPC. Hermes connects to OpenClaw MCP/tool surfaces over SSH and calls OpenClaw recall tools (`memory_search`, `memory_get`, `lcm_grep`, `lcm_describe`, `lcm_expand_query`) when they are exposed. OpenClaw connects to `hermes mcp serve` for Hermes messaging, and optionally to a small `hermes-memory` MCP server for structured Hermes `MEMORY.md`/`USER.md`/`state.db` access. Hermes semantic-memory parity is explicitly deferred.

**Tech Stack:** Hermes Agent, OpenClaw Gateway, OpenClaw MCP servers/tool projection, Hermes native MCP client/server, SSH stdio MCP transport, optional FastMCP Python server, systemd user services, Telegram gateway for human-visible smoke tests.

**Supersedes:** Any previous OpenClaw/Hermes bidirectional integration plan. Treat older plans as deprecated unless this document explicitly references them.

---

## Scope and Non-Goals

### In Scope

1. Hermes → OpenClaw tool access:
   - Discover and expose OpenClaw recall tools to Hermes.
   - Required tools if available:
     - `memory_search`
     - `memory_get`
     - `lcm_grep`
     - `lcm_describe`
     - `lcm_expand_query`
   - Optional convenience tools:
     - OpenClaw message/session tools (`message`, `sessions_send`, or channel bridge equivalents)
     - OpenClaw web/browser tools only if already exposed and useful.

2. OpenClaw → Hermes messaging:
   - Use native `hermes mcp serve` for channel/message bridge tools.
   - Required Hermes MCP tools:
     - `conversations_list`
     - `conversation_get`
     - `messages_read`
     - `events_poll` or `events_wait`
     - `messages_send`
     - `channels_list`

3. Optional OpenClaw → Hermes structured recall:
   - Add/enable a minimal Hermes memory MCP server if OpenClaw needs direct structured access to Hermes memory/session history instead of asking Hermes by message.
   - Required tools for that server:
     - `hermes_memory_status`
     - `hermes_memory_read`
     - `hermes_session_search`
   - Optional write tools only after read-only access is verified:
     - `hermes_memory_add`
     - `hermes_memory_replace`
     - `hermes_memory_remove`

4. Operational verification:
   - Verify every required tool through actual MCP `tools/list` and one safe live call.
   - Verify no credential values are printed into logs, docs, commits, or chat.

### Out of Scope / Deferred

- Full bidirectional arbitrary agent-command RPC.
- Hermes built-in semantic-memory parity with OpenClaw `memory_search`.
- Migrating Hermes memory to embeddings/vector search.
- Replacing either agent's memory model with a shared backend.
- Automatically allowing memory writes from one agent into the other without explicit review.

---

## Key Design Decisions

### Decision 1: `memory_search` is treated as an OpenClaw internal/core agent tool, not an LCM plugin tool

Do not assume `memory_search` comes from `openclaw-plugin-tools`. It may be exposed through OpenClaw's core/gateway-scoped tool surface, bundled loopback MCP, or an OpenClaw tools MCP bridge. The implementation must verify the actual source and tool name at runtime.

**Required verification:** the implementing agent must run a real tool discovery command and show whether `memory_search`/`memory_get` are present, including their exact MCP-visible names.

### Decision 2: LCM is a plugin tool surface

Lossless Claw / LCM tools should be exposed through the plugin/tool projection path when properly registered:

- `lcm_grep`
- `lcm_describe`
- `lcm_expand_query`
- `lcm_expand` (low-level; do not normally expose to Hermes unless needed for diagnostics)

If they are missing, fix OpenClaw/LCM registration before building a custom alternative.

### Decision 3: Corpus-selection behavior must be encoded for Hermes

Hermes should follow the same recall policy OpenClaw gives agents:

- Use `corpus="memory"` by default for durable facts, preferences, standing instructions, project state, decisions, todos, and notes.
- Use `corpus="sessions"` for prior conversations, exact discussion history, channel/session/thread details, transcript details, who said what, previous tool runs, and phrases like “conversation”, “chat”, “thread”, “session”, “transcript”, “earlier we said”, or “what did we discuss”.
- Use `corpus="all"` only when both durable memory and transcript context are genuinely needed, or after a weak/empty narrower search.
- For exact prior wording, IDs, commands, timestamps, config values, causal chains, or tool-call evidence, prefer LCM: `lcm_grep` → `lcm_describe` → `lcm_expand_query`.
- If broadening from a narrower corpus, say that the search was broadened.

### Decision 4: Hermes semantic parity is deferred

Hermes default `session_search` is FTS5/lexical over `state.db`; default `MEMORY.md`/`USER.md` are curated prompt-injected facts. External Hermes memory providers can add semantic recall, but this plan does not enable one unless later requested.

---

## Architecture Target

```text
Hermes Agent
  ├── Native MCP client → OpenClaw recall/tool surface over SSH stdio
  │     ├── memory_search(query, corpus="memory" | "sessions" | "all")
  │     ├── memory_get(...)
  │     ├── lcm_grep(...)
  │     ├── lcm_describe(...)
  │     └── lcm_expand_query(...)
  │
  ├── Native MCP client → optional OpenClaw channel bridge
  │     ├── conversations_list/messages_read/events_poll/messages_send
  │     └── only if separate from recall/tool surface
  │
  └── Existing native Hermes tools
        ├── memory
        ├── session_search
        └── send_message

OpenClaw Agent/Gateway
  ├── MCP client/plugin → `hermes mcp serve`
  │     ├── conversations_list
  │     ├── messages_read
  │     ├── messages_send
  │     └── events_poll/events_wait
  │
  └── Optional MCP client/plugin → `hermes-memory` MCP
        ├── hermes_memory_status
        ├── hermes_memory_read
        └── hermes_session_search
```

---

## Repository/Host Assumptions

The implementation agent must verify these and update this plan or its implementation notes if any are wrong:

- Hermes repo checkout: `~/.hermes/hermes-agent`.
- Hermes profile: default profile at `~/.hermes`.
- OpenClaw server SSH alias: `claw`.
- OpenClaw runtime user: likely `claw` on the remote host.
- OpenClaw config: likely `~/.openclaw/openclaw.json` on `claw`.
- OpenClaw gateway local URL on remote host: likely `http://127.0.0.1:18789`.
- OpenClaw service: likely `openclaw-gateway.service` as a systemd user service.
- Secrets must stay in env files or token files only. Never commit token values.

---

## Acceptance Criteria

The implementation is complete only when all checked items are true:

- [ ] A new Hermes config entry connects to an OpenClaw MCP/tool surface over SSH.
- [ ] Hermes startup/discovery logs show the OpenClaw MCP server connects successfully.
- [ ] Hermes can call an OpenClaw memory search tool with `corpus="memory"`.
- [ ] Hermes can call an OpenClaw memory search tool with `corpus="sessions"`.
- [ ] Hermes can call LCM `lcm_grep` across conversations or the nearest available equivalent.
- [ ] If `lcm_grep` finds a result, Hermes can call `lcm_describe` on a safe test summary/result when applicable.
- [ ] `lcm_expand_query` is verified with a harmless focused query, or a clear blocker is recorded.
- [ ] OpenClaw can call `hermes mcp serve` and list Hermes channel tools.
- [ ] OpenClaw can send one safe test message through Hermes using `messages_send`, or a clear blocker is recorded.
- [ ] Optional Hermes memory MCP is either implemented/read-only verified or explicitly deferred with rationale.
- [ ] A Hermes skill or instruction file exists that teaches Hermes the OpenClaw recall corpus/LCM escalation policy.
- [ ] No credentials are committed or printed in final artifacts.
- [ ] Rollback steps are documented and tested where safe.

---

## Phase 0: Safety, Branch, and Baseline Inventory

### Task 0.1: Create an implementation branch

**Objective:** Ensure all changes are isolated for review.

**Files:** none.

**Commands:**

```bash
cd ~/.hermes/hermes-agent
git status --short
git checkout main
git pull --ff-only origin main
git checkout -b feat/openclaw-hermes-bidirectional-mcp
```

**Expected:** clean working tree before changes; new branch checked out.

**Commit:** none for this task.

### Task 0.2: Inventory local Hermes MCP support

**Objective:** Confirm Hermes has MCP client/server support and the Python MCP SDK is available.

**Commands:**

```bash
cd ~/.hermes/hermes-agent
hermes mcp list || true
python3 - <<'PY'
try:
    import mcp
    print('mcp sdk: available')
except Exception as e:
    print('mcp sdk: missing:', type(e).__name__, str(e))
PY
```

**Expected:** `mcp sdk: available`. If missing, install via the active Hermes environment, not system Python, and record the exact command used.

**Commit:** none for this task.

### Task 0.3: Inventory OpenClaw remote runtime without printing secrets

**Objective:** Identify the actual OpenClaw CLI path, service, config, gateway health, and package versions.

**Commands:**

```bash
ssh claw 'set -euo pipefail
  echo "whoami=$(whoami)"
  echo "hostname=$(hostname)"
  command -v openclaw || true
  openclaw --version || true
  systemctl --user status openclaw-gateway.service --no-pager | sed -n "1,18p" || true
  test -f ~/.openclaw/openclaw.json && echo "config=~/.openclaw/openclaw.json" || true
  openclaw config validate || true
  curl -fsS http://127.0.0.1:18789/health || true
'
```

**Expected:** service active or a clear status; config path known; health endpoint result recorded. Do not print token files or config secret values.

**Commit:** none for this task.

---

## Phase 1: Discover the Real OpenClaw MCP/Tool Surfaces

### Task 1.1: List OpenClaw MCP-related CLI commands

**Objective:** Determine which OpenClaw MCP servers are available in the installed version.

**Commands:**

```bash
ssh claw 'set -euo pipefail
  openclaw mcp --help || true
  openclaw mcp serve --help || true
  openclaw tools --help || true
'
```

**Expected:** Document whether the installed OpenClaw exposes:

- `openclaw mcp serve` channel bridge.
- a built-in/core tools MCP server.
- a plugin-tools MCP server.
- a gateway HTTP `tools/list`/`tools.invoke` surface.

**Commit:** none for this task.

### Task 1.2: Discover OpenClaw channel bridge tools

**Objective:** Confirm the native `openclaw mcp serve` tool list and avoid confusing it with core/plugin tools.

**Files:**
- Create scratch script only if needed: `/tmp/list_mcp_tools.py` locally or remotely. Do not commit scratch files.

**Command option A: use an existing MCP inspector if available**

```bash
# If mcporter or an MCP inspector is installed, use it to list tools.
mcporter tools -- ssh claw openclaw mcp serve --url http://127.0.0.1:18789 --token-file '[REDACTED_TOKEN_FILE]' || true
```

**Command option B: write a short temporary Python MCP-list script**

```bash
python3 /tmp/list_mcp_tools.py -- ssh claw openclaw mcp serve --url http://127.0.0.1:18789 --token-file '[REDACTED_TOKEN_FILE]'
```

**Expected:** Tool list resembles channel/message bridge tools such as conversations/messages/events/permissions. Record exact names.

**Commit:** none for this task.

### Task 1.3: Discover OpenClaw core/gateway-scoped tools that include `memory_search`

**Objective:** Find the correct MCP or HTTP surface for internal/core OpenClaw agent tools, especially `memory_search` and `memory_get`.

**Commands:** Use whichever route exists in the installed OpenClaw version. Try in order:

1. Official OpenClaw tools MCP bridge, if present.
2. Gateway HTTP tools catalog/list endpoint, if documented in the install.
3. Bundled loopback MCP/tool projection used by ACP/Claude/Codex sessions, if present.
4. A direct OpenClaw agent test asking it to list whether `memory_search` and `memory_get` are callable.

**Safety:** If an endpoint needs auth, read token from the configured token file or env var without printing it.

**Expected:** Exact evidence for one of these outcomes:

- `memory_search` and `memory_get` are exposed through an MCP-compatible surface and can be called by Hermes.
- They are available only inside OpenClaw agent runtime and need a small OpenClaw-side wrapper/MCP bridge.
- They are disabled/missing due to config and need OpenClaw memory config repair.

**Commit:** none for this task.

### Task 1.4: Discover LCM plugin tools

**Objective:** Verify `lcm_*` tools are installed, registered, and callable.

**Commands:**

```bash
ssh claw 'set -euo pipefail
  # Show plugin status without secrets. Adjust command if this OpenClaw version differs.
  openclaw plugins list || true
  openclaw plugins status lossless-claw || true
  # Search logs only for registration names, not secrets.
  journalctl --user -u openclaw-gateway.service --since "2 hours ago" --no-pager \
    | grep -E "lossless|lcm_grep|lcm_describe|lcm_expand|plugin tool|toolNames|contracts.tools" \
    | tail -80 || true
'
```

Then check the actual OpenClaw tool catalog discovered in Task 1.3 for:

- `lcm_grep`
- `lcm_describe`
- `lcm_expand_query`
- `lcm_expand`

**Expected:** At least the first three are visible and callable. If plugin loaded but tools are absent, continue to Task 1.5.

**Commit:** none for this task.

### Task 1.5: Repair LCM registration only if tools are missing

**Objective:** Fix known Lossless Claw tool registration/version issues without broad OpenClaw churn.

**Prerequisite:** Only perform this task if Task 1.4 proves LCM tools are missing while the plugin is loaded.

**Steps:**

1. Identify installed LCM package path and version:

   ```bash
   ssh claw 'set -euo pipefail
     npm ls -g @martian-engineering/lossless-claw 2>/dev/null || true
     find ~/.openclaw -maxdepth 5 -iname "*lossless*" -o -iname "*lcm*" | sed -n "1,80p"
   '
   ```

2. Prefer upgrading/pinning to the first released LCM version that includes explicit tool registration names for `lcm_grep`, `lcm_describe`, `lcm_expand`, and `lcm_expand_query`.

3. If no release is available and the user approves, create a managed local hotfix following `openclaw-operations` managed hotfix rules:
   - patch outside `node_modules`
   - idempotent patcher
   - backup original file
   - `node --check`
   - systemd `ExecStartPre` drop-in
   - verification after restart

**Expected:** After restart, OpenClaw catalog shows `lcm_*` tools and `lcm_grep` safe test call succeeds.

**Commit:** commit only local repo documentation/config changes. Do not commit remote hotfix files into Hermes repo unless they are generic templates.

---

## Phase 2: Configure Hermes → OpenClaw MCP Access

### Task 2.1: Add OpenClaw MCP server entries to Hermes config

**Objective:** Register the smallest set of OpenClaw MCP servers Hermes needs.

**Files:**
- Modify: `~/.hermes/config.yaml` (runtime config, not committed).
- Optionally create committed docs/example: `docs/plans/openclaw-hermes-config-example.yaml` only if useful.

**Config pattern:** use SSH as stdio transport. Replace command/args with the actual commands discovered in Phase 1.

```yaml
mcp_servers:
  openclaw_recall:
    command: "ssh"
    args:
      - "claw"
      - "openclaw"
      - "<actual-recall-or-tools-mcp-command>"
      - "<actual-args>"
    timeout: 180
    connect_timeout: 60
    sampling:
      enabled: false
```

If channel bridge is separate:

```yaml
mcp_servers:
  openclaw_channel:
    command: "ssh"
    args:
      - "claw"
      - "openclaw"
      - "mcp"
      - "serve"
      - "--url"
      - "http://127.0.0.1:18789"
      - "--token-file"
      - "[REMOTE_TOKEN_FILE_PATH]"
    timeout: 120
    connect_timeout: 60
    sampling:
      enabled: false
```

**Security:** do not put raw gateway tokens in `config.yaml`; use remote token files or env vars.

**Verification command:**

```bash
hermes mcp test openclaw_recall
hermes mcp list
```

**Expected:** `openclaw_recall` connects and lists recall tools. Tool names in Hermes will be prefixed, e.g. `mcp_openclaw_recall_memory_search`.

**Commit:** runtime config is not committed. Commit only docs/plan updates if needed.

### Task 2.2: Restart Hermes gateway/session to load MCP tools

**Objective:** Ensure MCP discovery happens in the real Telegram/gateway runtime.

**Commands:**

```bash
hermes gateway restart
sleep 5
hermes gateway status
# Or use the active platform slash command /restart if that is the normal operations path.
```

**Expected:** gateway restarts cleanly; logs show OpenClaw MCP discovery without credential leaks.

**Log check:**

```bash
grep -E "MCP|openclaw_recall|openclaw_channel" ~/.hermes/logs/agent.log ~/.hermes/logs/gateway.log | tail -80
```

**Commit:** none for runtime-only task.

### Task 2.3: Verify Hermes can call OpenClaw memory search

**Objective:** Prove OpenClaw memory access works from Hermes.

**Safe test queries:** choose non-sensitive known phrases, e.g. project names or harmless routing terms.

**Required calls:**

1. Durable memory corpus:
   - Tool: exact Hermes-prefixed `memory_search` tool name from discovery.
   - Args: `query="OpenClaw Hermes integration"`, `corpus="memory"`, `limit=5`.

2. Sessions corpus:
   - Tool: exact Hermes-prefixed `memory_search` tool name from discovery.
   - Args: `query="OpenClaw Hermes integration"`, `corpus="sessions"`, `limit=5`.

3. Broadened corpus only if needed:
   - Args: `corpus="all"`.
   - Note in output: “broadened from memory/sessions to all”.

**Expected:** Each call either returns results or a structured empty result, not a transport/auth error.

**Commit:** none for runtime-only task.

### Task 2.4: Verify Hermes can call LCM tools

**Objective:** Prove exact-history recall works from Hermes.

**Required calls:**

1. `lcm_grep`:
   - Args: `pattern="OpenClaw Hermes"`, `mode="full_text"`, `scope="both"`, `allConversations=true`, `limit=10`.

2. `lcm_describe`:
   - Use a safe summary ID returned by grep, if any.
   - Args: `id="<summary id>"`, `allConversations=true`.

3. `lcm_expand_query`:
   - Use only if grep/describe identify a relevant summary.
   - Args: `prompt="Summarize what was decided about the OpenClaw/Hermes integration without exposing secrets."`, `query="OpenClaw Hermes integration"`, `allConversations=true`, `maxTokens=1200`.

**Expected:** `lcm_grep` succeeds. `lcm_describe`/`lcm_expand_query` either succeed or produce a clear, actionable blocker.

**Commit:** none for runtime-only task.

---

## Phase 3: Teach Hermes the OpenClaw Recall Policy

### Task 3.1: Create a Hermes skill for OpenClaw recall over MCP

**Objective:** Persist the corpus-selection and LCM escalation rules so future Hermes sessions use the integration correctly.

**Files:**
- Create: `~/.hermes/skills/devops/openclaw-hermes-recall/SKILL.md` (runtime skill, profile-local, not committed to upstream unless the user wants it promoted).
- Optionally create committed copy: `skills/devops/openclaw-hermes-recall/SKILL.md` only if this belongs in the Hermes repo, not just the user's profile.

**Skill content outline:**

```markdown
---
name: openclaw-hermes-recall
description: "Use OpenClaw MCP memory_search and LCM recall from Hermes."
version: 1.0.0
metadata:
  hermes:
    tags: [openclaw, memory, mcp, lcm, recall]
---

# OpenClaw/Hermes Recall

Use this when the user asks Hermes to recall OpenClaw memory, OpenClaw sessions, or prior OpenClaw conversation details.

## Tool selection

- Use OpenClaw `memory_search(corpus="memory")` for durable facts/preferences/project state/decisions.
- Use OpenClaw `memory_search(corpus="sessions")` for prior chats, transcripts, exact history, tool runs, who said what.
- Use `corpus="all"` only after narrow search is weak or both durable memory and transcripts are required.
- For exact commands, IDs, timestamps, config values, paths, decision rationale, or tool-call chains, use LCM escalation:
  1. `lcm_grep`
  2. `lcm_describe`
  3. `lcm_expand_query`

## Reporting

- Mention when search was broadened.
- Cite source snippets/summary IDs when tools provide them.
- Never reveal token values or secret file contents.
```

**Verification:**

```bash
hermes skills list | grep -i openclaw-hermes-recall || true
```

Start a fresh Hermes session or `/reload-skills` and ask a safe recall question.

**Commit:** If created in repo `skills/`, commit it. If profile-local only, do not commit.

### Task 3.2: Add an implementation-state note

**Objective:** Make future autonomous agents understand what was configured and what remains.

**Files:**
- Create or update: `docs/plans/openclaw-hermes-bidirectional-mcp-state.md` in repo.

**Content required:**

- Active branch/commit.
- OpenClaw tool surfaces discovered.
- Exact MCP server names configured in Hermes.
- Exact Hermes-prefixed tool names observed.
- Verification calls made and results summarized.
- Blockers, if any.
- Rollback commands.

**Commit:**

```bash
git add docs/plans/openclaw-hermes-bidirectional-mcp-state.md
git commit -m "docs: record OpenClaw Hermes MCP implementation state"
```

---

## Phase 4: Configure OpenClaw → Hermes Messaging

### Task 4.1: Verify Hermes MCP server locally

**Objective:** Confirm `hermes mcp serve` exposes Hermes channel tools.

**Commands:**

```bash
cd ~/.hermes/hermes-agent
hermes mcp serve --help
# Use an MCP inspector/list script to run: hermes mcp serve
```

**Expected tools:**

- `conversations_list`
- `conversation_get`
- `messages_read`
- `attachments_fetch`
- `events_poll`
- `events_wait`
- `messages_send`
- `channels_list`
- `permissions_list_open`
- `permissions_respond`

**Commit:** none.

### Task 4.2: Expose Hermes MCP server to OpenClaw

**Objective:** Let OpenClaw agents call Hermes messaging tools.

**Implementation options:** choose the simplest supported by the current OpenClaw install.

Option A: OpenClaw MCP adapter/plugin uses stdio SSH:

```json5
{
  plugins: {
    entries: {
      "mcp-adapter": {
        enabled: true,
        config: {
          toolPrefix: true,
          mcpServers: {
            hermes_channel: {
              command: "ssh",
              args: ["<hermes-host-alias>", "hermes", "mcp", "serve"]
            }
          }
        }
      }
    }
  }
}
```

Option B: Run a small HTTP/SSE adapter around `hermes mcp serve` and point OpenClaw to that HTTP endpoint.

**Security:**

- Prefer local network/Tailscale-only exposure.
- Disable MCP sampling for this server if the adapter supports it.
- Do not expose raw shell access; only the Hermes MCP server process.

**Verification:**

- OpenClaw agent can list `hermes_channel_*` tools.
- OpenClaw agent can call `messages_read` for a safe conversation.
- OpenClaw agent can call `messages_send` to send a harmless test message to an approved target.

**Commit:** Runtime OpenClaw config is not committed unless stored in a managed config repo. Commit only docs/state updates.

---

## Phase 5: Optional Hermes Memory MCP Server for OpenClaw → Hermes Structured Recall

### Task 5.1: Decide whether the optional server is needed

**Objective:** Avoid unnecessary implementation if OpenClaw can simply message Hermes for memory/session recall.

**Decision rule:**

- If OpenClaw only occasionally needs Hermes recall, defer this phase and use Hermes messaging.
- If OpenClaw needs structured, tool-level access to Hermes `MEMORY.md`, `USER.md`, or `state.db`, implement read-only MCP first.

**Commit:** update implementation state with the decision.

### Task 5.2: Implement read-only `hermes-memory` MCP server if approved

**Objective:** Provide structured read-only Hermes recall to OpenClaw.

**Files:**
- Create: `mcp-servers/hermes-memory-mcp.py`
- Create: `mcp-servers/hermes-memory-runner.sh`
- Create tests: `tests/test_hermes_memory_mcp.py`
- Update docs: `docs/plans/openclaw-hermes-bidirectional-mcp-state.md`

**Minimum tools:**

1. `hermes_memory_status()`
   - Returns character counts for `MEMORY.md` and `USER.md` and whether `state.db` exists.

2. `hermes_memory_read(target: "memory" | "user")`
   - Reads the selected memory file.
   - Rejects arbitrary paths.
   - Redacts obvious secret-like values defensively.

3. `hermes_session_search(query: str, limit: int = 5, sort: "relevance" | "newest" = "relevance")`
   - Opens `~/.hermes/state.db` read-only with SQLite URI `mode=ro`.
   - Uses existing Hermes session search logic if importable; otherwise uses FTS5 queries against the session DB after inspecting schema.
   - Returns session IDs, timestamps, titles, snippets, and message IDs.

**Security requirements:**

- Read-only by default.
- Use profile-aware `HERMES_HOME`.
- No arbitrary file reads.
- No tool that executes shell commands.
- No writes until separately approved.

**Test commands:**

```bash
python3 -m pytest tests/test_hermes_memory_mcp.py -v -o 'addopts='
```

**Commit:**

```bash
git add mcp-servers/hermes-memory-mcp.py mcp-servers/hermes-memory-runner.sh tests/test_hermes_memory_mcp.py docs/plans/openclaw-hermes-bidirectional-mcp-state.md
git commit -m "feat: add read-only Hermes memory MCP server"
```

### Task 5.3: Expose read-only Hermes memory MCP to OpenClaw

**Objective:** Let OpenClaw use `hermes_memory_*` tools if Phase 5.2 is implemented.

**OpenClaw config pattern:**

```json5
{
  plugins: {
    entries: {
      "mcp-adapter": {
        enabled: true,
        config: {
          toolPrefix: true,
          mcpServers: {
            hermes_memory: {
              command: "ssh",
              args: ["<hermes-host-alias>", "~/.hermes/mcp-servers/hermes-memory-runner.sh"]
            }
          }
        }
      }
    }
  }
}
```

**Verification:**

- OpenClaw lists `hermes_memory_status`, `hermes_memory_read`, `hermes_session_search` with any configured prefix.
- OpenClaw calls `hermes_memory_status` successfully.
- OpenClaw calls `hermes_session_search` with a harmless query successfully.

**Commit:** docs/state update only.

---

## Phase 6: End-to-End Smoke Tests

### Task 6.1: Hermes searches OpenClaw durable memory

**Objective:** Validate default corpus behavior.

**Test prompt to Hermes:**

```text
Search OpenClaw memory for durable facts about the OpenClaw/Hermes integration. Use the narrowest corpus and summarize only non-secret facts.
```

**Expected behavior:** Hermes calls OpenClaw `memory_search` with `corpus="memory"`.

### Task 6.2: Hermes searches OpenClaw sessions

**Objective:** Validate transcript/history corpus behavior.

**Test prompt to Hermes:**

```text
What did we discuss earlier about exposing LCM tools? Search prior OpenClaw sessions/transcripts, not just durable memory.
```

**Expected behavior:** Hermes calls OpenClaw `memory_search` with `corpus="sessions"`, and uses LCM if exact details are needed.

### Task 6.3: Hermes uses LCM for exact evidence

**Objective:** Validate LCM escalation.

**Test prompt to Hermes:**

```text
Find exact prior evidence about LCM tool exposure problems and summarize the command/tool names involved. Use LCM if available.
```

**Expected behavior:** Hermes starts with `lcm_grep`; uses `lcm_describe` or `lcm_expand_query` if grep snippets are insufficient.

### Task 6.4: OpenClaw sends through Hermes

**Objective:** Validate reverse messaging.

**Test prompt to OpenClaw:**

```text
Use the Hermes MCP channel tool to send a safe test message to the approved Hermes home channel saying: "OpenClaw → Hermes MCP smoke test succeeded." Do not include secrets.
```

**Expected behavior:** Message arrives through Hermes.

---

## Rollback Plan

### Roll back Hermes MCP config

1. Back up current config:

   ```bash
   cp ~/.hermes/config.yaml ~/.hermes/config.yaml.pre-openclaw-mcp-rollback-$(date -u +%Y%m%dT%H%M%SZ).bak
   ```

2. Remove `mcp_servers.openclaw_recall` and `mcp_servers.openclaw_channel` from `~/.hermes/config.yaml`.

3. Restart Hermes gateway:

   ```bash
   hermes gateway restart
   ```

4. Verify OpenClaw MCP tools no longer appear in Hermes logs/tool list.

### Roll back OpenClaw MCP adapter config

1. Back up `~/.openclaw/openclaw.json` on `claw`.
2. Remove `hermes_channel` and/or `hermes_memory` MCP server entries.
3. Validate config.
4. Restart `openclaw-gateway.service`.
5. Verify service health.

### Roll back LCM hotfix, if any

If a managed LCM hotfix was created:

1. Remove or disable the systemd drop-in that runs the hotfix patcher.
2. Restore the backed-up original bundle or reinstall the package version.
3. Restart OpenClaw gateway.
4. Verify service health.

---

## Final Review Checklist

Before asking the user to approve implementation completion, provide:

- [ ] Branch name and commit SHA(s).
- [ ] Exact files changed.
- [ ] Exact runtime config keys changed, with secrets redacted.
- [ ] Exact OpenClaw/Hermes MCP server names.
- [ ] Exact MCP tool names discovered.
- [ ] Smoke test transcript summaries.
- [ ] Known limitations.
- [ ] Rollback instructions.

---

## Notes for Autonomous Implementers

- Never print tokens, env values, config secrets, or token-file contents.
- Prefer official OpenClaw tool projection over custom code.
- `memory_search` may be a core/internal OpenClaw tool, not a plugin tool. Verify its actual exposure path.
- LCM tools are plugin tools; if missing, check plugin registration/version before inventing alternatives.
- Do not enable Hermes semantic memory providers in this plan unless the user separately approves.
- Keep runtime config changes minimal and reversible.
- Commit documentation and code changes frequently; do not commit local secret-bearing config files.

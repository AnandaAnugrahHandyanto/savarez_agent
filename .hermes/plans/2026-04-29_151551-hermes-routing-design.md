# Hermes Routing Policy Upgrade Implementation Plan

> For Hermes: planning only. Do not implement code from this document in this turn.

**Goal:** Add two high-ROI improvements to Hermes Agent: (1) a cheap planner pass that decides retrieval/tool strategy before the first expensive tool call, and (2) a retrieval escalation ladder with hard budgets so failed narrow lookups cannot explode into slow broad searches.

**Architecture:** Keep the main agent loop and tool registry intact. Add a small policy layer that runs before tool execution and produces a structured retrieval plan, then enforce that plan inside tool dispatch for retrieval-class tools (`search_files`, `read_file`, `session_search`, memory lookup paths, and similar future helpers). Reuse the existing auxiliary side-task router for the planner so this remains provider-agnostic and cheap.

**Tech Stack:** Python, existing Hermes auxiliary LLM routing (`agent/auxiliary_client.py`), run loop (`run_agent.py`), tool orchestration (`model_tools.py`), config (`hermes_cli/config.py`), pytest via `scripts/run_tests.sh`.

---

## Why this is worth doing

Current Hermes already has strong building blocks:
- Structured context compression with `## Active Task`, `## Pending`, `## Remaining Work` in `agent/context_compressor.py`
- Auxiliary task routing/fallback in `agent/auxiliary_client.py`
- Credential exhaustion state in `agent/credential_pool.py`
- Gateway agent cache TTL/LRU in `gateway/run.py`

But tool-heavy latency incidents show the missing piece is policy:
- narrow lookup fails
- model escalates to broad search on its own
- repeated retrieval attempts burn 20s+ each
- overall turn latency explodes even when the answer scope was small

This plan adds that missing policy without rewriting the agent loop.

---

## Scope

### In scope
1. Cheap planner pass before first retrieval-heavy tool execution
2. Retrieval escalation ladder with per-turn budget
3. Config knobs for enabling/tuning both features
4. Tool-result metadata so the planner can explain why escalation happened
5. Tests for config, planner output parsing, and retrieval budget enforcement

### Out of scope
- Full semantic/vector index
- New external dependencies
- Rewriting existing tools into async-first architecture
- UI changes beyond optional debug logging

---

## Proposed design

### 1) Cheap planner pass

Before the first retrieval-class tool runs in a turn, Hermes calls a cheap auxiliary model and asks for structured JSON like:

```json
{
  "needs_retrieval": true,
  "goal": "Recover the exact specialist packet path for this Slack thread.",
  "recommended_sequence": [
    "exact_path",
    "known_subtree",
    "session_search"
  ],
  "tool_hints": [
    {"tool": "read_file", "why": "Known packet path likely exists"},
    {"tool": "search_files", "why": "Fallback within constrained subtree only"}
  ],
  "max_retrieval_calls": 3,
  "allow_broad_search": false,
  "stop_if": ["found_exact_path", "subtree_timeout", "two_empty_results"]
}
```

This planner is not a second agent. It is a tiny structured side-task, similar in spirit to compression/session_search helpers.

### 2) Retrieval escalation ladder

All retrieval-class actions in a turn follow fixed escalation stages:
1. `exact_path`
2. `known_subtree`
3. `structured_metadata_lookup` (optional stub now, real index later)
4. `session_search`
5. `broad_search` (only if planner explicitly allows it)

Each stage returns a normalized outcome:
- `success`
- `empty`
- `timed_out`
- `too_broad`
- `permission_denied`
- `invalid_scope`

Escalation happens only when the prior stage fails with an allowed reason.

### 3) Hard per-turn retrieval budget

Add a turn-scoped budget object:
- `max_retrieval_calls`
- `max_broad_search_calls`
- `max_subtree_expansions`
- `max_total_retrieval_seconds`

When exhausted, Hermes should stop expanding search scope and tell the model/tool layer exactly why. This is the key protection against the kind of latency spike seen in specialist retrieval incidents.

### 4) Minimal observability

Log compact retrieval policy events:
- planner started / skipped
- planner output accepted / rejected
- each stage attempted
- stage result
- budget remaining
- escalation denied reason

This should be enough to debug slow turns from logs without dumping huge internal state.

---

## Files likely to change

### New files
- `agent/tool_planner.py` — cheap planner pass, prompt builder, schema validation, fallback behavior
- `agent/retrieval_budget.py` — turn-scoped retrieval budget + escalation policy object
- `tests/agent/test_tool_planner.py` — planner parsing, fallback, malformed JSON handling
- `tests/agent/test_retrieval_budget.py` — budget decrementing, escalation allow/deny logic

### Existing files to modify
- `run_agent.py` — create planner/budget per turn and wire them into the loop
- `model_tools.py` — enforce retrieval policy around retrieval-class tools
- `agent/auxiliary_client.py` — add `auxiliary.planner` config bridge and default routing
- `hermes_cli/config.py` — add config defaults for planner/retrieval policy
- `tests/hermes_cli/test_aux_config.py` — config coverage for `auxiliary.planner`
- `tests/agent/test_auxiliary_config_bridge.py` — planner config bridge tests

### Optional follow-up files
- `tools/session_search_tool.py` — normalize outcome metadata if current return shape is too loose
- `tools/file_operations.py` or specific tool wrapper locations — expose structured “scope/result” metadata for searches

---

## Config proposal

Add a new top-level section plus one auxiliary task profile.

### `hermes_cli/config.py`

```yaml
retrieval_policy:
  enabled: true
  planner_enabled: true
  max_retrieval_calls: 4
  max_broad_search_calls: 1
  max_subtree_expansions: 2
  max_total_retrieval_seconds: 25
  allow_unplanned_broad_search: false
  debug_log_events: true
```

And under existing `auxiliary:`

```yaml
auxiliary:
  planner:
    provider: auto
    model: ""
    base_url: ""
    api_key: ""
    timeout: 15
    extra_body: {}
```

Design note:
- planner config belongs under `auxiliary` because it is a cheap side-task LLM call
- retrieval policy belongs at top level because it controls runtime orchestration, not model selection

---

## Task plan

### Task 1: Add config defaults for planner + retrieval policy

**Objective:** Create stable config surface before touching runtime behavior.

**Files:**
- Modify: `hermes_cli/config.py`
- Test: `tests/hermes_cli/test_aux_config.py`
- Test: `tests/hermes_cli/test_config.py`

**Steps:**
1. Add `auxiliary.planner` alongside `vision`, `compression`, `session_search`
2. Add top-level `retrieval_policy` defaults
3. Add/adjust tests that assert these config keys exist and migrate cleanly

**Validation:**
- Run: `scripts/run_tests.sh tests/hermes_cli/test_aux_config.py tests/hermes_cli/test_config.py`
- Expected: passing config tests; no change-detector assertions

---

### Task 2: Implement turn-scoped retrieval budget object

**Objective:** Build the enforcement primitive before integrating planning.

**Files:**
- Create: `agent/retrieval_budget.py`
- Test: `tests/agent/test_retrieval_budget.py`

**Implementation sketch:**
- dataclass for counters + limits
- `record_attempt(stage, tool, seconds)`
- `can_attempt(stage)`
- `deny_reason(stage)`
- normalized result enum/string helpers

**Validation:**
- Run: `scripts/run_tests.sh tests/agent/test_retrieval_budget.py`
- Expected: unit tests cover call limits, broad-search denial, total-time exhaustion

---

### Task 3: Implement cheap planner helper

**Objective:** Produce a small validated retrieval plan using the auxiliary router.

**Files:**
- Create: `agent/tool_planner.py`
- Modify: `agent/auxiliary_client.py`
- Test: `tests/agent/test_tool_planner.py`
- Test: `tests/agent/test_auxiliary_config_bridge.py`

**Implementation sketch:**
- prompt asks for strict JSON only
- planner reads latest user ask + short recent context, not full transcript
- use existing auxiliary `call_llm()` path
- parse JSON with safe fallback to a conservative default plan
- if planner fails, Hermes should degrade gracefully to narrow-only retrieval

**Validation:**
- Run: `scripts/run_tests.sh tests/agent/test_tool_planner.py tests/agent/test_auxiliary_config_bridge.py`
- Expected: valid plan accepted, malformed output rejected safely, planner timeout falls back cleanly

---

### Task 4: Wire planner + budget into `run_agent.py`

**Objective:** Create per-turn policy state without rewriting the conversation loop.

**Files:**
- Modify: `run_agent.py`
- Test: `tests/run_agent/test_retrieval_policy.py` (new)

**Implementation sketch:**
- on each user turn, initialize retrieval budget from config
- lazily invoke planner only when the first retrieval-class tool is about to run
- store planner result in turn-local state
- pass policy object into tool dispatch layer

**Design constraint:**
Do not mutate prompt/tool availability mid-conversation. This layer should only guide tool execution, not edit the exposed tool list.

**Validation:**
- Run: `scripts/run_tests.sh tests/run_agent/test_retrieval_policy.py`
- Expected: planner called at most once per turn; skipped for non-retrieval turns

---

### Task 5: Enforce escalation ladder in `model_tools.py`

**Objective:** Centralize the rule so individual tools do not each reinvent policy.

**Files:**
- Modify: `model_tools.py`
- Optional modify: `tools/session_search_tool.py`
- Optional modify: retrieval-related tool wrappers if return metadata needs normalization
- Test: `tests/run_agent/test_retrieval_policy.py`

**Implementation sketch:**
- classify retrieval tools: `search_files`, `read_file`, `session_search`, memory-search paths, maybe `web_extract` later but not in v1
- before dispatch, ask budget if the stage is allowed
- after dispatch, normalize outcome and update budget
- deny forbidden broad searches early with a structured tool error message that explains the allowed next step

**Important:**
V1 should classify based on tool name + args heuristics, not AST-level semantics. Keep it simple.

**Validation:**
- Run: `scripts/run_tests.sh tests/run_agent/test_retrieval_policy.py`
- Expected: broad search gets blocked when planner disallows it; exact-path reads still work

---

### Task 6: Add log breadcrumbs for debugging

**Objective:** Make slow-turn diagnosis easy from logs.

**Files:**
- Modify: `run_agent.py`
- Modify: `model_tools.py`
- Maybe modify: `gateway/run.py` only if gateway-specific correlation IDs are helpful

**Implementation sketch:**
Log lines like:
- `retrieval planner: enabled turn=...`
- `retrieval stage=known_subtree tool=search_files result=empty remaining_calls=2`
- `retrieval broad_search denied reason=max_broad_search_calls`

**Validation:**
- Run targeted tests if logs are asserted, otherwise verify manually during dev

---

## Testing strategy

Run in this order:

1. `scripts/run_tests.sh tests/hermes_cli/test_aux_config.py tests/hermes_cli/test_config.py`
2. `scripts/run_tests.sh tests/agent/test_retrieval_budget.py tests/agent/test_tool_planner.py tests/agent/test_auxiliary_config_bridge.py`
3. `scripts/run_tests.sh tests/run_agent/test_retrieval_policy.py`
4. If runtime touches are broader than expected:
   `scripts/run_tests.sh tests/agent/ tests/run_agent/ tests/hermes_cli/`

Avoid snapshot/change-detector tests. Assert relationships and behavior:
- planner fallback stays conservative
- broad search cannot happen unless explicitly allowed
- budget exhaustion returns structured denial
- planner is not called for clearly non-retrieval turns

---

## Risks / tradeoffs

### Risk 1: Planner adds latency
Mitigation:
- only call planner lazily on retrieval-heavy turns
- use cheap auxiliary model with 15s timeout
- skip planner entirely when the tool path is obviously exact (`read_file` on explicit path)

### Risk 2: Over-constraining retrieval hurts success rate
Mitigation:
- allow one explicit broad-search slot by config
- log denial reasons clearly
- provide safe fallback defaults rather than hard-failing the turn

### Risk 3: Tool outcome normalization is messy
Mitigation:
- start with a narrow set of retrieval tools in v1
- if existing tool outputs are too inconsistent, add a tiny wrapper/normalizer instead of rewriting tools

### Risk 4: Prompt cache concerns
Mitigation:
- do not alter tool schemas or system prompt mid-session
- planner runs as a side-task outside the main exposed toolset

---

## Acceptance criteria

This design is successful if all are true:
1. A failed exact-path retrieval can no longer silently spiral into unrestricted broad filesystem search.
2. A retrieval-heavy turn has a visible, loggable escalation path.
3. The planner is cheap, optional, and safe to skip.
4. Existing non-retrieval turns behave exactly as before.
5. Config defaults are conservative and backward compatible.

---

## Suggested implementation order

1. Config
2. Retrieval budget
3. Planner helper
4. `run_agent.py` turn wiring
5. `model_tools.py` enforcement
6. Logging polish

This order keeps rollback simple and lets you ship value incrementally.

---

## Open questions

1. Which tool names should count as retrieval-class in v1 besides `search_files`, `read_file`, and `session_search`?
2. Should memory-provider lookups be folded into the same budget now, or in a second pass?
3. Do we want planner debug output exposed in verbose mode, or logs only?
4. Should `structured_metadata_lookup` ship as a no-op placeholder interface now to make future indexing easier?

---

## Recommendation

Ship this as a narrow v1 centered on local retrieval tools first. Do not try to solve vector indexing, memory ranking, and browser/web retrieval in the same change. The biggest immediate win is simply preventing “narrow miss -> unbounded broad search” behavior while giving Hermes one cheap chance to decide the right search ladder up front.

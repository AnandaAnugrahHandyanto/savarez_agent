# Kaspa/Kasia Capability Layer Implementation Plan

> **For Hermes:** Use Hermes as orchestrator, subagents for archaeology/review, and Codex CLI only for bounded implementation tasks. Do not let Codex decide product/security scope.

**Goal:** Build Hermes into a safe Kaspa/Kasia operator capability layer, not primarily a Kasia chat replacement.

**Architecture:** Start with read-only Kaspa/Kasia observability tools on current upstream Hermes. Keep wallet seeds, transaction signing, Kasia sending, and live gateway integration out of phase 1. Reuse the old `kasia-gateway` and `kasia-jobs-skill` branches as reference material, but port forward selectively into a fresh branch from `NousResearch/hermes-agent:main`.

**Workspace:** `/home/luke/repos/hermes-kaspa-capability`

**Branch:** `spike/kaspa-capability-layer`

**Remotes:**
- `origin`: `https://github.com/elldeeone/hermes-agent`
- `upstream`: `https://github.com/NousResearch/hermes-agent`

---

## Non-negotiable safety/isolation rules

1. Treat Luke's live Hermes install as production.
2. Do not modify:
   - `/home/luke/.hermes/config.yaml`
   - `/home/luke/.hermes/.env`
   - `/home/luke/.hermes/hermes-agent`
   - `hermes-gateway.service`
3. Use this repo-local disposable test home for test commands that might touch Hermes state:
   - `/home/luke/repos/hermes-kaspa-capability/.hermes-dev-home`
4. No live gateway restart/install/start.
5. No Kaspa/Kasia seed phrase handling in phase 1.
6. No transaction signing, sending, broadcasts, or wallet writes in phase 1.
7. No mainnet-affecting action without a later explicit dogfood/write-action approval gate.
8. Public HTTP reads are acceptable for read-only health/status checks, with timeouts and safe error handling.
9. Secrets must never be printed, committed, or included in logs.

---

## Product framing

The useful project is not "Telegram but over Kasia." The useful project is:

> Hermes can understand, monitor, and eventually safely operate Kaspa/Kasia systems.

Native Kasia chat can become a later proof-of-capability, but it is not the first priority.

---

## Phases

### Phase 0 — Archaeology and architecture

**Objective:** Decide what to salvage from old branches and map it onto current Hermes conventions.

**Reference branches:**
- `origin/kasia-gateway`
- `origin/kasia-jobs-skill`

**Inspect:**
- `gateway/platforms/kasia.py`
- `gateway/kasia_config.py`
- `gateway/kasia_identity.py`
- `scripts/kasia-bridge/`
- `optional-skills/autonomous-ai-agents/kasia-jobs/`
- `optional-skills/messaging/kasia/`
- associated tests and docs

**Deliverable:** Short archaeology note appended to this plan or a follow-up plan section identifying reusable modules vs deferred modules.

### Phase 1 — Read-only capability spike

**Objective:** Add a minimal read-only Kaspa/Kasia capability layer that can be tested without wallet secrets.

Candidate tools:
- `kaspa_node_health`
- `kasia_indexer_health`
- `kaspa_address_balance` if a safe public/read-only API is obvious
- `kasia_bridge_status` only if it checks a local bridge health endpoint without starting a bridge

Likely implementation shape:
- New tool file, probably `tools/kaspa_tools.py` or `tools/kasia_tools.py`.
- New toolset name, likely `kaspa` unless archaeology shows a strong reason for `kasia` split.
- Register via `tools.registry` and `toolsets.py` according to current Hermes conventions.
- Unit tests under `tests/tools/` using mocked HTTP responses.
- Docs under `website/docs/reference/toolsets-reference.md` or a new user-guide page if warranted.

Phase 1 must remain read-only and require no seed phrase.

### Phase 2 — Local bridge status layer

**Objective:** Reintroduce a dedicated local bridge only as an optional status/diagnostics component.

Possible capabilities:
- Check bridge process health.
- Check configured indexer/node endpoints.
- Estimate readiness for a future send path.

Deferred until phase 2:
- Starting/managing a bridge process.
- Wallet derivation.
- UTXO management.
- Message send.

### Phase 3 — Dedicated Hermes Kaspa identity design

**Objective:** Design, not necessarily implement, the constrained wallet safety model.

Must include:
- dedicated wallet only,
- low balance expectation,
- per-action spend cap,
- daily spend cap,
- approval requirements,
- allowlisted recipients/channels,
- redaction and logging rules,
- no primary wallet use.

### Phase 4 — Controlled Kasia actions

**Objective:** Add explicit, approval-gated write actions after the safety model is approved.

Potential actions:
- send Kasia DM,
- publish Kasia broadcast,
- check delivery/indexer visibility,
- retry/failover endpoints.

### Phase 5 — Optional Kasia gateway platform

**Objective:** Only after the capability layer is useful, consider a first-class `Platform.KASIA` gateway adapter.

This should reuse lessons from `kasia-gateway` but should not be the initial integration focus.

---

## Orchestration model

### Hermes orchestrator responsibilities

- Maintain project/product intent.
- Keep work isolated from live Hermes.
- Slice implementation into small tasks.
- Spawn Codex only with narrow prompts.
- Run and interpret tests.
- Inspect diffs before accepting changes.
- Use subagents for independent review.
- Decide whether to continue, revert, or adjust.

### Codex responsibilities

Codex may implement bounded tasks, for example:
- add a mocked HTTP helper,
- create one tool and its tests,
- update specific docs,
- fix a specific failing test.

Codex must not decide:
- wallet/security policy,
- whether write actions are allowed,
- gateway vs toolset product direction,
- live deployment/dogfood timing.

### Luke escalation gates

Only interrupt Luke for genuinely material decisions:
- approval to introduce wallet seed handling,
- approval to introduce write actions,
- approval to dogfood on live Hermes,
- upstream PR scope decisions if ambiguous,
- major architecture snag where several reasonable paths exist.

Do not ask Luke for no-brainer continuation decisions.

---

## Initial implementation tasks

### Task 1: Archaeology summary

**Objective:** Inspect old branches and current tool/platform conventions.

**Commands/areas:**
- `git diff --name-status upstream/main...origin/kasia-gateway`
- `git diff --name-status upstream/main...origin/kasia-jobs-skill`
- inspect current `tools/` registry patterns
- inspect current `toolsets.py`
- inspect current `gateway/ADDING_A_PLATFORM.md` if relevant

**Output:** Append an `Archaeology findings` section to this plan.

### Task 2: Decide phase-1 toolset name and API shape

**Objective:** Pick minimal read-only tools and JSON output schemas.

Expected starting point:
- Toolset: `kaspa`
- Tools:
  - `kaspa_node_health(url: str | None = None)`
  - `kasia_indexer_health(url: str | None = None)`

**Rules:** URL defaults may come from env vars, but no env var should be required for tool discovery unless the tool cannot function without it. Tools should accept explicit URLs so tests and users can run read-only checks without global config.

### Task 3: Implement mocked read-only tools

**Objective:** Add tool file and tests with mocked network calls.

**Likely files:**
- Create: `tools/kaspa_tools.py`
- Modify: `toolsets.py`
- Test: `tests/tools/test_kaspa_tools.py`

**Verification:**
- `HERMES_HOME=/home/luke/repos/hermes-kaspa-capability/.hermes-dev-home python -m pytest tests/tools/test_kaspa_tools.py -q -o 'addopts='`
- focused registry/toolset tests as needed

### Task 4: Review and docs

**Objective:** Ensure phase 1 is clearly read-only and safe.

**Likely files:**
- `website/docs/reference/toolsets-reference.md`
- maybe `website/docs/user-guide/tools/kaspa.md` depending current docs structure

**Verification:** Docs are accurate and do not imply wallet/send capability.

---

## Open questions to resolve through archaeology, not by asking Luke yet

1. Does current Hermes prefer bundled optional skills over built-in toolsets for niche capabilities?
2. Are gateway platform plugins mature enough to defer first-class `Platform.KASIA` entirely?
3. Which public Kaspa/Kasia endpoints are safe and stable enough as examples without hardcoding brittle defaults?
4. Should phase 1 include address balance, or only endpoint health until a reliable API path is established?

---

## Archaeology findings

### Salvage now

- Pure/read-only identity logic from old `gateway/kasia_identity.py` is the highest-value salvage target: KNS normalization, Kaspa address canonicalization, KNS URL defaults, read-only KNS lookup, and address/name matching tests.
- Config parsing ideas from old `gateway/kasia_config.py` are useful only after stripping unsafe fields. Keep endpoint-list parsing, network/KNS URL handling, timeout parsing, and address variant helpers. Do not keep seed/bridge/send fields in phase 1.
- Tests from `tests/gateway/test_kasia_identity.py` and selected endpoint/config tests are good salvage material.
- Endpoint failover concepts from `scripts/kasia-bridge/lib/endpoint_pool.js` may be useful later, but port the idea rather than JS code.

### Salvage later

- `gateway/platforms/kasia.py` is later gateway-reference material only. It starts a bridge, handles pairing/handshakes, polls, sends, and has side effects.
- `scripts/kasia-bridge/` is later wallet/bridge material. Phase 1 should not import/launch it.
- `optional-skills/messaging/kasia` and `optional-skills/autonomous-ai-agents/kasia-jobs` are later UX/job references, not phase-1 implementation targets.

### Explicitly defer

- `KASIA_SEED_PHRASE`, wallet derivation, private-key operations, signing, KAS sends, Kasia sends, broadcasts, handshake transactions, bridge process management, port killing, and jobs escrow actions.

### Current Hermes tool conventions

- Add a top-level `registry.register(...)` call in a new `tools/*.py` module so auto-discovery sees it.
- Handlers receive `args: dict` and return JSON strings; use `tool_result(...)` and `tool_error(...)` from `tools.registry`.
- Tool schemas are OpenAI-function style dicts without the outer `type:function` wrapper.
- Add a standalone `kaspa` toolset in `toolsets.py`; keep it opt-in for phase 1 rather than adding to `_HERMES_CORE_TOOLS`.
- Test by importing the module explicitly, checking registry entries/schemas, testing handlers with mocked HTTP, and checking `resolve_toolset("kaspa")`.
- Watch for `check_fn` TTL caching if tests toggle env; likely avoid check_fn for phase-1 read-only explicit-URL tools.

## Current status

- Dedicated workspace created.
- Branch created from current upstream main.
- Live Hermes install untouched.
- Repo-local plan created and updated with archaeology findings.
- Implemented first opt-in read-only `kaspa` toolset slice:
  - `kaspa_api_health`: GET `/info/health` from Kaspa REST API.
  - `kasia_indexer_health`: GET `/metrics` from Kasia indexer.
- Safety retained: no seed phrases, no signing, no sends, no broadcasts, no bridge process, no gateway adapter, no live Hermes config/service changes.
- Verification completed:
  - `HERMES_HOME=/home/luke/repos/hermes-kaspa-capability/.hermes-dev-home python -m pytest tests/tools/test_kaspa_tools.py tests/test_toolsets.py -q -o 'addopts='` → 51 passed.
  - `python -m py_compile tools/kaspa_tools.py tests/tools/test_kaspa_tools.py` → passed.
  - Live read-only smoke checks returned HTTP 200 for `https://api.kaspa.org/info/health` and `https://indexer.kasia.fyi/metrics`.
- Next step: commit/push branch, then extend read-only surface with KNS/address helpers or address balance only after confirming stable public API behavior.

# Memory Control Spine + Proof Spine Implementation Plan

> For Hermes: implement with strict TDD. No production code before a failing test.

Goal: turn the existing continuity rails into one governed runtime system with canonical write/read contracts and one proof surface.

Architecture: keep the existing rails (sqlite memory, wiki, session search, Clerk reset, bootstrap/chain continuity) but add a thin governing layer above them. The governing layer should compile writes into a canonical MemoryEvent, assemble recall into a canonical RecallReceipt, materialize restore-critical breadcrumbs for external continuity lanes, and expose operator-facing proof in CLI/doctor/scripts.

Tech Stack: Python, existing Hermes agent runtime, sqlite-backed persistent memory store, CLI doctor/memory commands, pytest.

## Requested delta
Build the real memory/control spine and proof spine instead of relying on umbrella docs and scattered smoke checks.

## Likely failure mode
We add nice dataclasses and docs, but the live write path still bypasses them, the live recall path still hand-stitches strings, and Clerk/chain/file-anchor proof remains outside the contract.

## Proof of success
1. A memory write returns a canonical MemoryEvent and writes restore-critical sidecars for chain/file-anchor lanes.
2. A runtime recall pass returns a canonical RecallReceipt covering durable memory, wiki, session recall, and any active Clerk/reset continuity lane used.
3. CLI/operator surfaces can inspect the latest event/receipt without digging through raw files.
4. Repo-local smoke scripts prove the contracts exist and the live paths use them.

---

## Task 1: Add canonical contract modules

Objective: create stable machine-readable contracts for write and read paths.

Files:
- Create: `agent/memory_event.py`
- Create: `agent/recall_receipt.py`
- Create: `tests/agent/test_memory_event.py`
- Create: `tests/agent/test_recall_receipt.py`

Acceptance:
- Contracts serialize to dict cleanly.
- Contracts capture lane usage, provenance, degraded flags, suppression, and materialization status.

## Task 2: Add lane registry and recovery policy

Objective: define the lane vocabulary once.

Files:
- Create: `agent/memory_lanes.py`
- Create: `agent/recovery_policy.py`
- Create: `agent/supersession.py`
- Create: `tests/agent/test_memory_lanes.py`
- Create: `tests/agent/test_recovery_policy.py`
- Create: `tests/agent/test_supersession.py`

Acceptance:
- All continuity lanes are declared explicitly.
- Recovery-safe lanes are not guessed from random booleans.
- Derived wiki recall loses to source lanes when both say the same thing.

## Task 3: Add write compiler and wire memory tool through it

Objective: every durable memory write produces one MemoryEvent and one governed materialization result.

Files:
- Create: `agent/write_compiler.py`
- Modify: `tools/memory_tool.py`
- Create: `tests/agent/test_write_compiler.py`
- Create: `tests/tools/test_memory_tool_control_plane.py`

Acceptance:
- `memory` tool responses include `memory_event`.
- Restore-critical writes materialize sidecars under:
  - `~/.hermes/memory/chain-of-shells/control-plane-events/`
  - `~/.hermes/memory/file-anchors/control-plane-events/`
- Partial lane failures are visible, not silent.

## Task 4: Add compact session recall bridge and recall assembler

Objective: replace ad hoc runtime recall stitching with one assembler.

Files:
- Create: `agent/recall_assembler.py`
- Modify: `tools/session_search_tool.py`
- Modify: `run_agent.py`
- Create: `tests/agent/test_recall_assembler.py`
- Create: `tests/tools/test_session_search_compact.py`
- Modify: `tests/run_agent/test_run_agent.py`

Acceptance:
- Add `session_search_compact()` for non-LLM runtime recall.
- Runtime recall uses one assembler to collect lanes and emit `RecallReceipt`.
- Agent stores latest receipt on the instance.
- User-message injection uses assembler output, not a pile of manually joined strings.

## Task 5: Unify Clerk/reset continuity as a governed lane

Objective: make Clerk continuity visible to the same contract model.

Files:
- Modify: `cli.py`
- Possibly create: `agent/clerk_bridge.py`
- Modify: `tests/cli/test_cli_new_session.py`
- Add: `tests/agent/test_recall_assembler.py` coverage for Clerk lane

Acceptance:
- Pending Clerk restore state can be represented as a lane payload for recall receipts.
- Reset continuity is used once and then cleared, with proof visible in the receipt.

## Task 6: Build proof surfaces

Objective: one operator-facing proof surface, not scattered folklore.

Files:
- Create: `hermes_cli/recall.py`
- Modify: `hermes_cli/memory_cli.py`
- Modify: `hermes_cli/doctor.py`
- Create: `scripts/check_memory_reality.py`
- Create: `scripts/check_runtime_recall_end_state.py`
- Add: `tests/hermes_cli/test_recall_cli_receipts.py`
- Modify: `tests/hermes_cli/test_memory_cli.py`
- Modify: `tests/hermes_cli/test_doctor_memory_health.py`
- Create: `tests/e2e/test_memory_control_plane_reality.py`

Acceptance:
- `memory status` shows latest event/receipt proof summaries.
- doctor checks contract files and sidecar lanes, not just memory.db existence.
- smoke scripts print PASS/WARN/FAIL for the governed layer.

## Task 7: Verify end-to-end

Objective: prove the system on the live path.

Commands:
- `source venv/bin/activate && pytest tests/agent/test_memory_event.py tests/agent/test_recall_receipt.py tests/agent/test_memory_lanes.py tests/agent/test_recovery_policy.py tests/agent/test_supersession.py tests/agent/test_write_compiler.py tests/agent/test_recall_assembler.py tests/tools/test_memory_tool_control_plane.py tests/tools/test_session_search_compact.py tests/hermes_cli/test_memory_cli.py tests/hermes_cli/test_doctor_memory_health.py tests/hermes_cli/test_recall_cli_receipts.py tests/e2e/test_memory_control_plane_reality.py tests/run_agent/test_run_agent.py tests/cli/test_cli_new_session.py -q`
- `source venv/bin/activate && python scripts/check_memory_reality.py`
- `source venv/bin/activate && python scripts/check_runtime_recall_end_state.py`

Success condition:
- Tests pass.
- Smoke scripts show governed write/read rails, not just importability theater.
- The final report can name exact remaining gaps honestly if any lane is still partial.

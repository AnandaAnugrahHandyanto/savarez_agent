# Hermes Runtime Organs RFC

> For Hermes: this RFC defines the runtime architecture upgrades needed to close the highest-value gaps identified in `Claude Code 模式映射到 Hermes：差距报告`.

Status: Proposed
Author: Hermes Agent
Date: 2026-04-09
Scope: `run_agent.py`, `model_tools.py`, `agent/context_compressor.py`, `agent/context_references.py`, selected tool runtime surfaces

---

## 1. Goal

Strengthen Hermes as a runtime system without diluting its existing advantages.

Do not turn Hermes into Claude Code.
Do not weaken approval, gateway, or delegation primitives.
Do not start with feature sprawl.

This RFC proposes five runtime organs:

1. Input World Assembly
2. Dynamic Tool Exposure
3. Unified Side-Channel Context Bus
4. Post-Compaction Reconstruction + Lineage
5. Tool Result / Failure Envelope + Hook Chain

The objective is simple:
make Hermes feel less like a powerful bag of subsystems and more like a coherent nervous system.

---

## 2. Current State

Hermes already has strong parts:

- `run_agent.py` provides the main conversation loop, iteration budgets, tool execution flow, prompt assembly, and context compression integration.
- `model_tools.py` provides registry-backed discovery, dispatch, toolset resolution, plugin/MCP discovery, and async bridging.
- `agent/context_compressor.py` already does structured compaction with pruning, protected head/tail, and iterative updates.
- `agent/context_references.py` already gives explicit `@file/@folder/@diff/@url` expansion with root restriction and token guardrails.
- `tools/approval.py` is a mature policy gate for dangerous terminal commands.
- `tools/delegate_tool.py` provides strong child isolation and controlled tool inheritance.

The problem is not missing power.
The problem is that several core runtime decisions are still expressed as scattered implementation details instead of first-class architecture.

---

## 3. Non-Goals

This RFC does not propose:

- replacing the current tool registry
- replacing toolsets with fully autonomous tool search
- changing gateway platform behavior
- rewriting compaction from scratch
- changing memory semantics
- changing approval UX first

This is a runtime-structure RFC.
Not a product redesign.

---

## 4. Design Principles

### 4.1 Preserve Hermes strengths

Do not damage:
- approval enforcement
- session persistence
- multi-platform gateway behavior
- explicit toolsets
- delegation isolation

### 4.2 Add explicit architecture before changing behavior

First introduce named runtime boundaries.
Then migrate existing logic into them.
Only after that add smarter behavior.

### 4.3 Prefer additive refactors

Most phase-1 work should be wrappers and extraction layers.
Existing behavior should remain stable.

### 4.4 Keep policy and capability separate

Approval says whether an action is allowed.
Exposure says whether the model should even see the action.
They are connected but not the same.

---

## 5. Proposed Runtime Organs

## 5.1 Input World Assembly

### Problem

Today the material that defines “what exists for this turn” is spread across:
- prompt builder logic
- context reference expansion
- memory injection
- skill injection
- platform hints
- session/tooling side context
- ad hoc preflight branches in CLI and agent loop

The work happens.
But there is no single named assembly stage.

### Proposal

Introduce a dedicated turn-preparation function and data structure.

New module:
- `agent/turn_assembly.py`

Primary API:
- `assemble_turn_context(...) -> TurnAssembly`

Suggested object:

```python
@dataclass
class TurnAssembly:
    original_user_message: str
    assembled_user_message: str
    system_blocks: list[str]
    side_channel_blocks: list[str]
    warnings: list[str]
    references_expanded: bool
    references_blocked: bool
    injected_token_estimate: int
    tool_visibility_hints: dict[str, object]
    lineage: dict[str, object]
```

### Responsibilities

`assemble_turn_context()` should:
- normalize incoming user text
- expand context references through `agent/context_references.py`
- inject memory/user profile blocks
- inject skill blocks
- include platform or environment hints
- record warnings and token-impact metadata
- prepare later phases for tool exposure and lineage

### Why it matters

This creates a single preflight organ.
It becomes the source of truth for what the model sees at turn start.

---

## 5.2 Unified Side-Channel Context Bus

### Problem

Hermes already has side channels, but they are implicit and fragmented:
- memory/profile context
- skill content
- context refs
- session_search recall
- delegated summaries
- future MCP or plugin-derived context

These are currently “extra prompt text”.
That is too weak as an architecture concept.

### Proposal

Introduce a named side-channel layer.

New object:

```python
@dataclass
class SideChannelContext:
    memory_blocks: list[str] = field(default_factory=list)
    skill_blocks: list[str] = field(default_factory=list)
    reference_blocks: list[str] = field(default_factory=list)
    recall_blocks: list[str] = field(default_factory=list)
    delegation_blocks: list[str] = field(default_factory=list)
    platform_blocks: list[str] = field(default_factory=list)
    extra_blocks: list[str] = field(default_factory=list)

    def flatten(self) -> list[str]:
        ...
```

### Integration

`TurnAssembly` owns one `SideChannelContext` instance.
Prompt construction consumes it in a stable order.

Recommended order:
1. policy / system constraints
2. memory and user profile
3. skills
4. session recall
5. context references
6. delegation outputs
7. platform hints
8. final assembled user message

### Benefits

- clear provenance of injected context
- easier debugging
- easier token accounting
- easier future ranking/truncation of side-channel content

---

## 5.3 Dynamic Tool Exposure

### Problem

Hermes has strong static tool governance via toolsets.
But the model often receives a broad visible tool surface from the start.
That increases prompt size and weakens capability steering.

### Proposal

Keep static allowlists.
Add a dynamic visibility layer on top.

New module:
- `agent/tool_visibility.py`

Primary API:
- `resolve_visible_tools(all_allowed_tools, assembly, runtime_state) -> list[dict]`

New state object:

```python
@dataclass
class ToolVisibilityState:
    visible_tool_names: list[str]
    hidden_tool_names: list[str]
    reason_by_tool: dict[str, str]
    exposure_phase: str
```

### Inputs

The resolver may use:
- platform
- current task text
- detected context refs
- token pressure
- prior failed tool attempts
- explicit user requests
- safe defaults

### Example policies

- If no browser/web cues exist, hide browser tools.
- If no file/reference cues exist, hide file-heavy tools except a minimal file set.
- If the turn is already near context threshold, expose a compact tool subset.
- If the user explicitly asks for background process inspection, expose process tools.
- If a prior attempt failed due to missing capability, widen exposure in the next round.

### Guardrails

- Never expose tools outside static permissions.
- Never bypass approval.
- Prefer deterministic heuristics in phase 1.
- Add learned/LLM-mediated exposure only later, if ever.

---

## 5.4 Post-Compaction Reconstruction + Lineage

### Problem

Hermes compression is already solid.
But the continuation model is still mostly “summary plus surviving tail”.
What is missing is explicit lineage and recovery semantics.

### Proposal

Introduce compaction lineage metadata and a reconstruction block.

New module:
- `agent/lineage.py`

Suggested objects:

```python
@dataclass
class CompactionLineage:
    chain_id: str
    generation: int
    parent_summary_id: str | None
    source_message_range: tuple[int, int] | None
    created_at: str

@dataclass
class RecoveryContext:
    lineage: CompactionLineage | None
    summary_block: str | None
    unresolved_threads: list[str]
    recent_tool_failures: list[str]
    pending_next_steps: list[str]
```

### Behavior

When compaction runs:
- generate/update lineage metadata
- produce a compact reconstruction block, not just a summary blob
- preserve unresolved threads and recent failed attempts in structured form

### Reconstruction block shape

Recommended sections:
- Goal
- Confirmed progress
- Files / state already changed
- Failed attempts to avoid repeating
- Outstanding threads
- Most recent safe next move

### Benefits

- stronger continuation after long runs
- better resilience after compression or provider retries
- future compatibility with session replay and postmortem tooling

---

## 5.5 Tool Result / Failure Envelope + Hook Chain

### Problem

Hermes handles tool execution centrally, but result semantics remain too string-oriented.
Errors often enter the model as plain text blobs.
That works. It does not scale gracefully.

### Proposal

Introduce a standard envelope around tool outcomes plus pre/post hooks.

New module:
- `agent/tool_runtime.py`

Suggested dataclasses:

```python
@dataclass
class ToolFailure:
    category: str
    message: str
    retriable: bool
    suggested_next_step: str | None = None
    details: dict[str, object] = field(default_factory=dict)

@dataclass
class ToolExecutionEnvelope:
    tool_name: str
    ok: bool
    content: str
    structured_content: dict[str, object] = field(default_factory=dict)
    failure: ToolFailure | None = None
    metadata: dict[str, object] = field(default_factory=dict)
```

### Hook points

```python
def run_tool_with_hooks(...):
    pre_tool_hooks(...)
    execute_tool(...)
    normalize_result(...)
    post_tool_hooks(...)
    return envelope
```

### Hook use cases

- standard logging
- approval/policy instrumentation
- normalization of tool errors
- truncation metadata
- persistent storage metadata
- future auditing or observability

### Initial failure taxonomy

Use a conservative enum-like string set:
- `invalid_input`
- `permission_denied`
- `approval_denied`
- `not_found`
- `timeout`
- `environment_error`
- `transient_external_error`
- `internal_tool_error`

---

## 6. Module-Level Changes

## 6.1 `run_agent.py`

### Add
- turn assembly invocation before API calls
- dynamic tool visibility resolution before schema emission
- lineage/recovery state carried on agent instance
- tool runtime hook/envelope consumption

### Reduce
- scattered prompt injection branches
- direct ad hoc preflight logic that belongs in assembly
- string-only tool error shaping inside the main loop

### Target shape

```python
assembly = assemble_turn_context(...)
visible_tools = resolve_visible_tools(..., assembly=assembly, runtime_state=...)
messages = build_messages_from_assembly(...)
response = call_model(messages=messages, tools=visible_tools)
for tool_call in response.tool_calls:
    envelope = run_tool_with_hooks(...)
    messages.append(tool_message_from_envelope(envelope))
```

---

## 6.2 `model_tools.py`

### Keep
- discovery
- registry-backed dispatch
- async bridging
- toolset resolution

### Add
- an execution path that returns structured envelopes, not only plain strings
- hook registration or callback slots

### Avoid
Do not duplicate policy or prompt logic here.
This remains the tool platform boundary.

---

## 6.3 `agent/context_compressor.py`

### Keep
- compaction mechanics
- iterative summary updates
- pruning
- token budgeting

### Add
- structured reconstruction output option
- lineage metadata creation/update
- summary IDs or generation counters exposed to runtime state

---

## 6.4 `agent/context_references.py`

### Keep
- parsing and expansion behavior
- allowed-root restrictions
- token hard/soft limits

### Add
- richer metadata return fields that integrate cleanly into `TurnAssembly`
- optional categorization of reference types for tool visibility hints

Potential additions to `ContextReferenceResult`:
- `reference_kinds: list[str]`
- `paths_touched: list[str]`
- `git_context_present: bool`

---

## 6.5 New modules

Create:
- `agent/turn_assembly.py`
- `agent/tool_visibility.py`
- `agent/lineage.py`
- `agent/tool_runtime.py`

These should be thin and explicit.
No giant god module.

---

## 7. Runtime Flow After RFC

Desired turn lifecycle:

1. Receive user input
2. Assemble turn world (`TurnAssembly`)
3. Resolve visible tools (`ToolVisibilityState`)
4. Build prompt/messages from assembly + side-channel context
5. Call model
6. If tool calls returned, execute via runtime hook chain and structured envelopes
7. Update lineage / recovery state
8. If near threshold, compact and emit reconstruction metadata
9. Continue or finalize

This creates a real phase model without tearing down the existing system.

---

## 8. Migration Plan

## Phase 1: Structural extraction

Goal: introduce new modules with no intentional behavior change.

Work:
- create `agent/turn_assembly.py`
- create `agent/tool_runtime.py`
- wrap existing string tool results in envelopes
- move context-ref preflight into assembly
- keep old code paths available behind compatibility wrappers

Success criteria:
- existing tests still pass
- no user-visible regressions in CLI/gateway
- turn assembly is the single preflight entry point

## Phase 2: Controlled intelligence

Goal: make runtime decisions smarter without changing trust boundaries.

Work:
- create `agent/tool_visibility.py`
- add heuristic dynamic exposure on top of static toolsets
- add reference-derived visibility hints
- add failure taxonomy normalization

Success criteria:
- tool schema count drops on average turns
- no capability escalation
- failed-tool recovery improves on repeated-turn workflows

## Phase 3: Continuity hardening

Goal: improve long-run continuation and post-compaction behavior.

Work:
- create `agent/lineage.py`
- add compaction lineage IDs/generations
- upgrade summary output into reconstruction blocks
- surface lineage in session metadata and diagnostics

Success criteria:
- fewer repeated actions after compaction
- clearer continuation state in long sessions
- better debugging of “why did the agent repeat itself?”

---

## 9. Testing Strategy

### Unit tests

Add tests for:
- turn assembly output stability
- side-channel ordering
- reference expansion metadata
- dynamic visibility heuristics
- failure envelope normalization
- lineage generation and increment behavior

### Integration tests

Cover:
- standard CLI turn without refs
- turn with `@file` / `@diff`
- turn with compaction
- turn with dangerous terminal request needing approval
- delegated subagent run with summarized return

### Regression tests

Protect:
- approval behavior
- toolset restriction behavior
- session persistence
- gateway compatibility
- existing compaction thresholds

---

## 10. Risks

### Risk 1: Over-abstraction

Mitigation:
phase rollout, thin dataclasses, compatibility wrappers.

### Risk 2: Prompt regressions

Mitigation:
snapshot tests for assembled prompt blocks and visible tool lists.

### Risk 3: Hidden capability bugs

Mitigation:
dynamic exposure must only narrow from static permissions, never widen beyond them.

### Risk 4: Compaction churn

Mitigation:
make lineage additive first; do not replace current compactor output immediately.

---

## 11. Open Questions

1. Should dynamic tool exposure be fully heuristic, or partly model-informed later?
2. Should tool envelopes be persisted in session storage as structured JSON alongside text?
3. Should lineage metadata surface in `/status` or diagnostics commands?
4. Should side-channel blocks be token-ranked when context pressure is high?
5. Should subagent summaries carry a formal type so they enter the bus as `delegation_blocks` automatically?

---

## 12. Bottom Line

Hermes already has the weapons.

What it lacks is explicit runtime anatomy.

This RFC does not ask Hermes to imitate Claude Code.
It asks Hermes to keep its own strengths and add five missing organs:
- turn assembly
- side-channel bus
- dynamic tool visibility
- lineage-aware reconstruction
- structured tool runtime semantics

That is the right direction.
Not more tools.
Better nerves.

# Phase 1 Runtime Organs Implementation Plan

> For Hermes: use subagent-driven-development only after this plan is approved. Execute task-by-task. Preserve behavior. Prefer extraction wrappers over rewrites.

Goal: introduce Phase 1 runtime structure for Hermes by extracting turn assembly and tool runtime normalization into explicit modules, while keeping user-visible behavior stable.

Architecture: create thin orchestration modules around existing behavior in `run_agent.py`, `model_tools.py`, `agent/memory_manager.py`, and `agent/context_references.py`. Phase 1 does not change policy, approval, or toolset boundaries. It creates named runtime seams and compatibility wrappers so later phases can add dynamic exposure and lineage without reopening the whole loop.

Tech Stack: Python, dataclasses, existing Hermes agent loop, registry-backed tools, current plugin hook system, current context-reference and memory subsystems.

---

## Preconditions

Before touching code, keep these truths fixed:

- `run_agent.py` currently injects memory prefetch and plugin user context directly into the current user message around lines `7291-7303`.
- `run_agent.py` currently appends `ephemeral_system_prompt` and `prefill_messages` during API-call assembly around lines `7331-7350`.
- `_build_system_prompt()` around line `2605` already assembles the stable system prompt and must remain the source of cached system content.
- `model_tools.handle_function_call()` currently returns plain strings and fires plugin hooks at lines `500-540`.
- `_invoke_tool()` in `run_agent.py` handles agent-loop tools separately at lines `6075-6139`.
- `_execute_tool_calls_concurrent()` currently persists tool results and appends tool messages around lines `6323-6339`.
- `agent/context_references.py` already returns `ContextReferenceResult` with `warnings`, `injected_tokens`, `expanded`, and `blocked`.

Success means these behaviors still work after extraction.

---

## Task 1: Create the Phase 1 design scaffold document inside code comments and module headers

Objective: make the new modules self-explanatory so later work does not collapse back into `run_agent.py` sprawl.

Files:
- Create: `agent/turn_assembly.py`
- Create: `agent/tool_runtime.py`

Step 1: Create `agent/turn_assembly.py` with a module docstring that says this module owns API-call-time turn preparation only.

Add these rules in the docstring:
- no session persistence
- no tool execution
- no policy decisions beyond recording hints/warnings
- compatibility-first extraction from `run_agent.py`

Step 2: Create `agent/tool_runtime.py` with a module docstring that says this module normalizes tool execution results but does not replace approval or registry dispatch.

Step 3: Add stub dataclasses only. No behavior yet.

`agent/turn_assembly.py`
```python
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any


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
        return [
            *self.memory_blocks,
            *self.skill_blocks,
            *self.recall_blocks,
            *self.reference_blocks,
            *self.delegation_blocks,
            *self.platform_blocks,
            *self.extra_blocks,
        ]


@dataclass
class TurnAssembly:
    original_user_message: str
    assembled_user_message: str
    system_blocks: list[str] = field(default_factory=list)
    side_channel: SideChannelContext = field(default_factory=SideChannelContext)
    warnings: list[str] = field(default_factory=list)
    references_expanded: bool = False
    references_blocked: bool = False
    injected_token_estimate: int = 0
    tool_visibility_hints: dict[str, Any] = field(default_factory=dict)
    lineage: dict[str, Any] = field(default_factory=dict)
    metadata: dict[str, Any] = field(default_factory=dict)
```

`agent/tool_runtime.py`
```python
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any


@dataclass
class ToolFailure:
    category: str
    message: str
    retriable: bool
    suggested_next_step: str | None = None
    details: dict[str, Any] = field(default_factory=dict)


@dataclass
class ToolExecutionEnvelope:
    tool_name: str
    ok: bool
    content: str
    structured_content: dict[str, Any] = field(default_factory=dict)
    failure: ToolFailure | None = None
    metadata: dict[str, Any] = field(default_factory=dict)
```

Step 4: Run import smoke test.

Run:
`python - <<'PY'
from agent.turn_assembly import TurnAssembly, SideChannelContext
from agent.tool_runtime import ToolExecutionEnvelope, ToolFailure
print('ok')
PY`

Expected: `ok`

Step 5: Commit.

```bash
git add agent/turn_assembly.py agent/tool_runtime.py
git commit -m "refactor: add runtime assembly and tool envelope scaffolds"
```

---

## Task 2: Implement turn assembly helpers that preserve current injection order

Objective: move API-call-time user-message injection logic out of `run_agent.py` without changing visible behavior.

Files:
- Modify: `agent/turn_assembly.py`
- Test: new test file under `tests/` for assembly behavior

Step 1: Add helper functions in `agent/turn_assembly.py`.

Required functions:
- `build_side_channel_context(...) -> SideChannelContext`
- `assemble_turn_context(...) -> TurnAssembly`
- `apply_turn_assembly_to_user_message(message: dict, assembly: TurnAssembly) -> dict`
- `compose_effective_system_prompt(base_system: str, ephemeral_system_prompt: str | None) -> str`
- `inject_prefill_messages(api_messages: list[dict], prefill_messages: list[dict], effective_system: str) -> list[dict]`

Step 2: Preserve current semantics exactly.

Rules:
- Memory prefetch is fenced using `build_memory_context_block()` from `agent.memory_manager`.
- Plugin user context is appended after memory context.
- These injections affect only the current API call, never persisted session messages.
- `ephemeral_system_prompt` is appended to the cached system prompt only at API-call time.
- `prefill_messages` are inserted immediately after the system message when one exists, otherwise at the start.

Step 3: Put the existing order into code explicitly.

Recommended implementation shape:
```python
def build_side_channel_context(*, memory_context: str = '', plugin_user_context: str = '') -> SideChannelContext:
    side = SideChannelContext()
    if memory_context:
        side.memory_blocks.append(memory_context)
    if plugin_user_context:
        side.extra_blocks.append(plugin_user_context)
    return side


def assemble_turn_context(
    user_message: str,
    *,
    memory_context: str = '',
    plugin_user_context: str = '',
    reference_result=None,
    platform: str | None = None,
) -> TurnAssembly:
    assembled = reference_result.message if reference_result else user_message
    warnings = list(getattr(reference_result, 'warnings', []) or [])
    side = build_side_channel_context(
        memory_context=memory_context,
        plugin_user_context=plugin_user_context,
    )
    return TurnAssembly(
        original_user_message=user_message,
        assembled_user_message=assembled,
        side_channel=side,
        warnings=warnings,
        references_expanded=bool(getattr(reference_result, 'expanded', False)),
        references_blocked=bool(getattr(reference_result, 'blocked', False)),
        injected_token_estimate=int(getattr(reference_result, 'injected_tokens', 0) or 0),
        tool_visibility_hints={
            'platform': platform,
            'has_references': bool(getattr(reference_result, 'references', [])),
        },
    )
```

Step 4: Add tests.

Create tests that assert:
- no injection returns original user content
- memory block is appended before plugin user context
- reference-result message replaces original user text for API-call-time assembly
- effective system prompt joins base + ephemeral with one blank line
- prefill insertion order matches current `run_agent.py` behavior

Step 5: Run focused tests.

Run:
`pytest -q tests/test_turn_assembly.py`

Expected: pass

Step 6: Commit.

```bash
git add agent/turn_assembly.py tests/test_turn_assembly.py
git commit -m "refactor: extract turn assembly helpers from api message prep"
```

---

## Task 3: Wire `run_agent.py` to use turn assembly helpers without changing persistence behavior

Objective: replace duplicated assembly logic in the main loop with calls into `agent/turn_assembly.py`.

Files:
- Modify: `run_agent.py`
- Test: existing or new integration-focused tests for API message assembly

Step 1: Add imports near other agent imports.

```python
from agent.turn_assembly import (
    assemble_turn_context,
    apply_turn_assembly_to_user_message,
    compose_effective_system_prompt,
    inject_prefill_messages,
)
```

Step 2: Identify the current user-turn assembly site.

Relevant region:
- current user message appended around `7047-7050`
- API-call-time injection loop around `7282-7303`
- system/prefill assembly around `7331-7350`

Step 3: Build a `TurnAssembly` once per API request cycle using the already available ephemeral data.

Inputs should include:
- current user message content
- fenced memory context built from `_ext_prefetch_cache`
- `_plugin_user_context`
- any context-reference result if already available in the turn path
- `self.platform`

Step 4: Replace inline injection block with helper call.

Instead of open-coded `_injections`, do this:
```python
if idx == current_turn_user_idx and msg.get('role') == 'user':
    api_msg = apply_turn_assembly_to_user_message(api_msg, turn_assembly)
```

Step 5: Replace open-coded effective-system assembly.

```python
effective_system = compose_effective_system_prompt(
    active_system_prompt or '',
    self.ephemeral_system_prompt,
)
```

Step 6: Replace open-coded prefill insertion.

```python
api_messages = inject_prefill_messages(api_messages, self.prefill_messages, effective_system)
```

Step 7: Preserve storage boundaries.

Verify:
- `messages` list is still not mutated with ephemeral memory/plugin injections
- system prompt cache behavior is unchanged
- session persistence still records the original user message, not the assembled one

Step 8: Run targeted tests.

Run:
`pytest -q tests/test_turn_assembly.py`

Then run a narrower existing suite if available:
`pytest -q -k "prompt or api_messages or context_references"`

Expected: pass or known unrelated skips only

Step 9: Commit.

```bash
git add run_agent.py tests/
git commit -m "refactor: route api-call message prep through turn assembly"
```

---

## Task 4: Extend context-reference metadata for Phase 1 hints, not behavior changes

Objective: enrich `ContextReferenceResult` so later tool visibility work has clean metadata, without changing expansion semantics.

Files:
- Modify: `agent/context_references.py`
- Test: context-reference tests

Step 1: Extend `ContextReferenceResult` fields.

Add:
```python
reference_kinds: list[str] = field(default_factory=list)
paths_touched: list[str] = field(default_factory=list)
git_context_present: bool = False
```

Step 2: Populate fields conservatively.

Rules:
- `reference_kinds` = ordered unique list of kinds seen in parsed refs
- `git_context_present` = `True` if any ref kind is `diff`, `staged`, or `git`
- `paths_touched` = resolved file/folder targets when safe and meaningful; omit URLs and unresolved/blocked entries

Step 3: Do not change these semantics:
- root restriction
- sensitive path blocking
- soft/hard token limits
- final message text format

Step 4: Add tests for the new metadata only.

Assertions:
- `@file:x` yields `reference_kinds == ['file']`
- git-style refs set `git_context_present`
- blocked refs still populate kinds but not unsafe paths

Step 5: Run tests.

Run:
`pytest -q -k "context_references"`

Expected: pass

Step 6: Commit.

```bash
git add agent/context_references.py tests/
git commit -m "refactor: add structured metadata to context reference results"
```

---

## Task 5: Add tool runtime normalization helpers that wrap string results in envelopes

Objective: standardize tool result shape without replacing the current dispatcher.

Files:
- Modify: `agent/tool_runtime.py`
- Test: new tool-runtime unit tests

Step 1: Add helper functions.

Required functions:
- `categorize_tool_failure(tool_name: str, content: str) -> ToolFailure | None`
- `build_tool_envelope(tool_name: str, content: str, *, metadata: dict | None = None) -> ToolExecutionEnvelope`
- `tool_message_from_envelope(envelope: ToolExecutionEnvelope, tool_call_id: str) -> dict`

Step 2: Start with deterministic string heuristics only.

Recommended categories:
- `approval_denied`
- `permission_denied`
- `timeout`
- `not_found`
- `invalid_input`
- `environment_error`
- `internal_tool_error`

Step 3: Use the existing `_detect_tool_failure(...)` semantics as a compatibility anchor where possible. Do not invent speculative failures.

Step 4: Keep `content` untouched.

The envelope adds metadata. It does not rewrite the tool output text in Phase 1.

Step 5: Add tests.

Test cases:
- success string returns `ok=True`, `failure=None`
- timeout-like string maps to `timeout`
- permission/approval-denied strings map correctly
- `tool_message_from_envelope()` returns the same message shape `run_agent.py` already expects

Step 6: Run tests.

Run:
`pytest -q tests/test_tool_runtime.py`

Expected: pass

Step 7: Commit.

```bash
git add agent/tool_runtime.py tests/test_tool_runtime.py
git commit -m "refactor: add tool execution envelope normalization"
```

---

## Task 6: Route concurrent and sequential tool result handling through envelopes

Objective: use the new runtime helper in `run_agent.py` while preserving tool callbacks, persistence, and tool message content.

Files:
- Modify: `run_agent.py`
- Test: tool execution path tests if present

Step 1: Import the new helpers.

```python
from agent.tool_runtime import build_tool_envelope, tool_message_from_envelope
```

Step 2: In `_execute_tool_calls_concurrent()` keep `_invoke_tool()` exactly as the execution mechanism.

Do not replace:
- callbacks
- checkpoint logic
- `maybe_persist_tool_result(...)`
- `enforce_turn_budget(...)`

Step 3: After persistence and subdirectory hint augmentation, build an envelope.

Recommended shape:
```python
persisted_result = maybe_persist_tool_result(...)
if subdir_hints:
    persisted_result += subdir_hints
envelope = build_tool_envelope(
    name,
    persisted_result,
    metadata={
        'tool_call_id': tc.id,
        'duration_seconds': tool_duration,
        'is_error': is_error,
    },
)
tool_msg = tool_message_from_envelope(envelope, tc.id)
messages.append(tool_msg)
```

Step 4: Mirror the same wrapping in the sequential execution path.

Phase 1 is incomplete if only concurrent calls use the envelope.

Step 5: Preserve last-mile message shape.

Tool messages in `messages` must still look like:
```python
{
  'role': 'tool',
  'content': <string>,
  'tool_call_id': tc.id,
}
```

Step 6: Add at least one regression test proving the envelope path does not alter stored tool content.

Step 7: Run targeted tests.

Run:
`pytest -q -k "tool_runtime or tool_call or concurrent"`

Expected: pass

Step 8: Commit.

```bash
git add run_agent.py tests/
git commit -m "refactor: normalize tool results through runtime envelopes"
```

---

## Task 7: Add compatibility diagnostics for assembly and envelopes

Objective: make the extraction debuggable before later phases build on it.

Files:
- Modify: `agent/turn_assembly.py`
- Modify: `agent/tool_runtime.py`
- Optionally modify: `run_agent.py`

Step 1: Add `to_debug_dict()` methods or equivalent serialization helpers on both dataclass families.

Example:
```python
def to_debug_dict(self) -> dict:
    return {
        'original_user_message': self.original_user_message,
        'assembled_user_message': self.assembled_user_message,
        'warnings': self.warnings,
        'references_expanded': self.references_expanded,
        'references_blocked': self.references_blocked,
        'injected_token_estimate': self.injected_token_estimate,
        'tool_visibility_hints': self.tool_visibility_hints,
    }
```

Step 2: Under verbose logging only, emit one debug line for turn assembly creation and one for tool envelope creation.

Do not print these in normal quiet-mode UX.

Step 3: Verify logs do not include secret material beyond what is already present in current debug paths.

Step 4: Run tests or smoke command.

Run:
`python - <<'PY'
from agent.turn_assembly import TurnAssembly
from agent.tool_runtime import build_tool_envelope
print(build_tool_envelope('x', 'ok').metadata == {})
PY`

Expected: `True`

Step 5: Commit.

```bash
git add agent/turn_assembly.py agent/tool_runtime.py run_agent.py
git commit -m "chore: add runtime assembly and envelope diagnostics"
```

---

## Task 8: Run Phase 1 verification sweep

Objective: prove the extraction did not break core runtime behavior.

Files:
- No new files required unless test fixes are needed

Step 1: Run focused unit and integration tests.

Run exactly:
```bash
pytest -q tests/test_turn_assembly.py tests/test_tool_runtime.py
pytest -q -k "context_references or prompt or tool_call"
```

Step 2: Run lightweight import smoke.

```bash
python - <<'PY'
from agent.turn_assembly import assemble_turn_context
from agent.tool_runtime import build_tool_envelope
print('phase1-smoke-ok')
PY`
```

Expected: `phase1-smoke-ok`

Step 3: If Hermes has an existing self-test or CLI smoke command, run one representative command in a safe workspace.

Example shape:
```bash
python run_agent.py --help >/dev/null
```

Step 4: Review git diff for scope control.

Run:
```bash
git diff --stat HEAD~8..HEAD
```

Expected:
- mostly additive changes
- no approval-path rewrites
- no unrelated module churn

Step 5: Final commit if verification required follow-up edits.

```bash
git add -A
git commit -m "test: verify phase 1 runtime organs extraction"
```

---

## Acceptance Criteria

Phase 1 is complete only if all are true:

- `agent/turn_assembly.py` exists and owns API-call-time turn preparation helpers.
- `agent/tool_runtime.py` exists and owns result-envelope helpers.
- `run_agent.py` no longer open-codes memory/plugin user-message assembly or system/prefill composition in the main API request path.
- `ContextReferenceResult` exposes structured metadata for future visibility logic.
- Tool execution still runs through current mechanisms, but result handling is normalized with envelopes before tool messages are appended.
- Persisted conversation history remains behaviorally unchanged.
- Approval, toolsets, memory writes, delegate isolation, and gateway behavior remain intact.
- Focused tests pass.

---

## Known Pitfalls

- Do not mutate stored `messages` with ephemeral injections. That would pollute session persistence.
- Do not move `_build_system_prompt()` responsibilities into turn assembly. Stable system prompt caching must stay separate.
- Do not let envelope helpers rewrite tool text. Phase 1 is normalization, not reinterpretation.
- Do not change tool-message wire format yet. Later phases can add richer metadata elsewhere.
- Do not widen context-reference permissions while collecting `paths_touched`.
- Do not duplicate plugin hook firing in both `model_tools.py` and `agent/tool_runtime.py`.

---

## Recommended Execution Order

1. Task 1 scaffold
2. Task 2 turn assembly helpers
3. Task 3 `run_agent.py` integration
4. Task 4 context-reference metadata
5. Task 5 tool envelope helpers
6. Task 6 `run_agent.py` envelope integration
7. Task 7 diagnostics
8. Task 8 verification sweep

---

## Definition of Done

The codebase gains explicit runtime seams for turn assembly and tool result normalization.

Nothing flashy.
Nothing reckless.
Just cleaner nerves.

Date: 2026-04-09

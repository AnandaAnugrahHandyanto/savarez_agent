# SDAO Improvements Implemented

This document records the concrete improvements already implemented in the SDAO worktree.

## 1. Pure orchestration policy kernel

Implemented
- `agent/orchestration_policy.py`

Improvement
- SDAO decisions are no longer implicit or scattered.
- Core orchestration logic is now testable as a pure function.

Why it matters
- Easier to reason about
- Safer to change
- Enables adversarial testing without full runtime wiring

## 2. Strict delegation gate

Implemented
- `tools/delegate_tool.py`

Improvement
- Delegation now passes through an explicit policy gate before child execution.
- This gate blocks unsafe or low-value delegation patterns.

Current protections
- blocks simple single-task delegation
- blocks ambiguous parallelization
- blocks dependent parallel batches
- blocks decorative, optics-driven, or style-only parallelization
- blocks delegation when the user says `no subagents`
- requires explicit justification for complex single-task delegation

Why it matters
- reduces delegation misuse
- preserves parent-agent accountability
- makes multi-agent behavior predictable

## 3. Parent prompt orchestration guidance

Implemented
- `agent/prompt_builder.py`
- `run_agent.py`

Improvement
- The parent agent now receives explicit orchestration instructions before calling `delegate_task`.
- Guidance is injected only when the delegation tool is available.

Behavior added
- solo by default
- ambiguity resolves conservatively
- prefer sequential over parallel when uncertain
- do not use decorative or style-only delegation
- reject surface-level parallelism signals
- justify delegation internally before calling `delegate_task`

Why it matters
- reduces policy violations before they reach the runtime gate
- aligns prompt behavior with runtime enforcement

## 4. Adversarial and contra-oriented tests

Implemented
- orchestration test suite under `tests/orchestration/`
- targeted adversarial coverage for decorative/style-only parallelization
- targeted adversarial coverage for ambiguity and mixed-signal prompts

Improvement
- Each phase was validated with tests designed against the current behavior, not only happy paths.
- SDAO now has explicit regression coverage for decorative, optics-driven, and superficial parallelization requests.

Why it matters
- catches real regressions
- proves the contract more clearly
- follows the intended SSD/TDD discipline

## 5. End-to-end orchestration coverage

Implemented
- `tests/orchestration/test_sdao_e2e.py`

Improvement
- Added runtime-level validation of parent -> `delegate_task` behavior.

Covered cases
- simple requests stay solo
- dependent batches do not parallelize
- independent complex batches parallelize
- decorative or style-only parallelization is rejected
- explicit `no subagents` stays solo
- batch size above limit errors clearly
- ambiguity resolves to solo

Why it matters
- validates the real runtime path
- proves prompt + gate + delegate wiring work together

## 6. Clearer safety posture

Improvement
- SDAO now favors refusal of unsafe orchestration over permissive delegation.
- Tie-break behavior is explicit and conservative.

Current tie-break order
1. solo
2. sequential
3. parallel only with strong evidence

Why it matters
- safer defaults
- lower surprise cost
- better fit for strict orchestration

# SDAO Documentation

SDAO stands for Strict Delegation & Orchestration.

It defines a strict default behavior for Hermes orchestration:
- solo by default
- sequential when work is complex and dependent
- parallel only when independence is explicit and useful
- explicit user prohibition of subagents must be respected

## What was implemented in this worktree

Phase 1
- Pure policy kernel in `agent/orchestration_policy.py`
- Decision outputs: `solo`, `sequential`, `parallel`
- Conservative tie-breaks: prefer `solo`, then `sequential`

Phase 2
- Strict gate in `tools/delegate_tool.py`
- Rejects simple single-task delegation
- Rejects ambiguous or dependent parallel batches
- Rejects decorative, optics-driven, or style-only parallelization requests
- Requires explicit justification for complex single-task delegation
- Respects explicit `no subagents` instructions

Phase 3
- Parent-agent prompt guidance added through `agent/prompt_builder.py` and `run_agent.py`
- SDAO is injected only when `delegate_task` is available
- Prompt guidance tells the parent agent to:
  - stay solo by default
  - resolve ambiguity conservatively
  - prefer sequential over parallel when uncertain
  - avoid decorative or style-only delegation
  - reject surface-level parallelism signals
  - justify delegation internally before calling `delegate_task`

Phase 4
- End-to-end orchestration tests added in `tests/orchestration/test_sdao_e2e.py`
- Validates runtime parent -> `delegate_task` behavior, not only pure policy helpers

## Test inventory

Policy and gate tests
- `tests/orchestration/test_sdao_baseline_current_behavior.py`
- `tests/orchestration/test_sdao_policy_kernel.py`
- `tests/orchestration/test_sdao_delegate_gate.py`
- `tests/orchestration/test_sdao_phase2_strict_counterexamples.py`
- `tests/orchestration/test_sdao_adversarial_gate.py`

Prompt tests
- `tests/orchestration/test_sdao_prompt_policy.py`
- `tests/orchestration/test_sdao_adversarial_prompt.py`
- `tests/run_agent/test_run_agent.py`

End-to-end tests
- `tests/orchestration/test_sdao_e2e.py`
- `tests/orchestration/test_sdao_adversarial_e2e.py`

Operational validation
- `tests/tools/test_delegate.py`

## Current contract

A request should stay solo when:
- it is simple
- it is ambiguous
- the user says not to use subagents
- delegation does not materially help
- parallelization is requested for style, optics, or appearance only

A request may go sequential when:
- work is complex
- later steps depend on earlier outputs
- isolation or staged review is justified

A request may go parallel only when:
- there are multiple subtasks
- independence is explicit
- dependencies are absent
- concurrency adds real value

## Related docs

- `docs/plans/2026-04-12-sdao-strict-orchestrator-plan.md`
- `docs/sdao/improvements.md`
- `docs/sdao/future-improvements.md`

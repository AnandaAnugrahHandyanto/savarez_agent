# SDAO PR-Ready Summary

This file is intended to be copied into a PR description and used as the basis for the final commit message.

## Suggested PR title

feat: add strict SDAO orchestration policy and adversarial hardening

## Suggested squash commit message

feat: add strict SDAO orchestration policy and adversarial hardening

- add pure orchestration policy kernel for solo/sequential/parallel decisions
- enforce a strict SDAO gate in delegate_task
- inject SDAO prompt guidance when delegation is available
- harden SDAO against decorative and style-only parallelization
- add adversarial, contra-oriented, and end-to-end orchestration tests
- add dedicated SDAO documentation for overview, implemented improvements, and future improvements

## Suggested PR body

## Summary
- Introduces SDAO (Strict Delegation & Orchestration) in the isolated `sdao-lab` worktree.
- Makes Hermes prefer solo execution by default.
- Enforces stricter delegation behavior so parallelism is only allowed for explicitly independent complex subtasks.
- Hardens SDAO against decorative, optics-driven, or style-only parallelization requests.
- Adds dedicated SDAO documentation, including implemented improvements and future improvements.

## What changed

### Runtime behavior
- Added pure orchestration policy kernel in `agent/orchestration_policy.py`.
- Added strict SDAO delegation gate in `tools/delegate_tool.py`.
- Added explicit blocking for decorative or style-only parallelization signals in `tools/delegate_tool.py`.
- Added SDAO prompt guidance in `agent/prompt_builder.py` and `run_agent.py`.
- Strengthened prompt guidance so ambiguity resolves conservatively and surface-level parallelism signals are rejected.
- Added run_agent prompt regression coverage in `tests/run_agent/test_run_agent.py`.

### Tests
Added orchestration tests covering the SDAO rollout and adversarial hardening:
- `tests/orchestration/test_sdao_baseline_current_behavior.py`
- `tests/orchestration/test_sdao_policy_kernel.py`
- `tests/orchestration/test_sdao_delegate_gate.py`
- `tests/orchestration/test_sdao_phase2_strict_counterexamples.py`
- `tests/orchestration/test_sdao_prompt_policy.py`
- `tests/orchestration/test_sdao_e2e.py`
- `tests/orchestration/test_sdao_adversarial_gate.py`
- `tests/orchestration/test_sdao_adversarial_prompt.py`
- `tests/orchestration/test_sdao_adversarial_e2e.py`

### Documentation
Added dedicated SDAO docs:
- `docs/sdao/README.md`
- `docs/sdao/improvements.md`
- `docs/sdao/future-improvements.md`
- `docs/sdao/pr-ready-summary.md`

Updated plan doc:
- `docs/plans/2026-04-12-sdao-strict-orchestrator-plan.md`

## SDAO contract after this PR
- solo by default
- sequential preferred for dependent complex work
- parallel only when independence is explicit and useful
- explicit `no subagents` must be respected
- ambiguity resolves conservatively
- decorative, optics-driven, or style-only parallelization is rejected
- surface-level similarity is not enough to justify parallel delegation

## Test plan
Executed in `/home/jh/.hermes/worktrees/sdao-lab`:

```text
python -m pytest tests/orchestration/test_sdao_baseline_current_behavior.py \
  tests/orchestration/test_sdao_policy_kernel.py \
  tests/orchestration/test_sdao_delegate_gate.py \
  tests/orchestration/test_sdao_phase2_strict_counterexamples.py \
  tests/orchestration/test_sdao_prompt_policy.py \
  tests/orchestration/test_sdao_e2e.py \
  tests/orchestration/test_sdao_adversarial_gate.py \
  tests/orchestration/test_sdao_adversarial_prompt.py \
  tests/orchestration/test_sdao_adversarial_e2e.py \
  tests/tools/test_delegate.py -q
```

Latest focused SDAO results:
- adversarial hardening suite: 11 passed
- expanded focused SDAO suite: 340 passed, 1 failed

Known unrelated focused-suite failure still present in this environment:
- `tests/run_agent/test_run_agent.py::TestRunConversation::test_inline_think_blocks_reasoning_only_accepted`

Warning observed:
- external deprecation warning from `discord.player` / `audioop`
- not introduced by SDAO changes

## Notes
- No rollout/config knobs were added yet; strict default behavior remains the priority.
- Work was developed and validated in the isolated worktree only.
- This PR is structured to keep the policy kernel, runtime gate, adversarial hardening, tests, and docs aligned.
- Full repository test suite is not green in this environment/worktree, so this PR remains draft rather than merge-ready.

## Suggested reviewers’ focus
- correctness of `tools/delegate_tool.py` gate behavior
- conservatism of `agent/orchestration_policy.py`
- prompt/runtime consistency between `agent/prompt_builder.py` and `run_agent.py`
- correctness of the new style-only/decorative parallelization rejection logic
- clarity and completeness of the adversarial orchestration tests
- whether Phase 5 docs are sufficient before any rollout beyond the worktree

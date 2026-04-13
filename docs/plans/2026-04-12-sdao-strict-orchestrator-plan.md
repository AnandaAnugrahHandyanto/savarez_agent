# SDAO Implementation Plan

> For Hermes: implement in the isolated worktree only. Use SSD by phases, TDD inside each phase, and adversarial implementation tests against the current behavior before changing production code.

Goal: build SDAO (Strict Delegation & Orchestration) so Hermes defaults to solo execution, delegates sequentially only when justified, and parallelizes only for genuinely independent subtasks.

Architecture:
- Phase the work so we harden behavior gradually.
- Each phase starts with adversarial tests against current behavior.
- Each phase follows SSD structure and strict TDD internally.
- All work happens in /home/jh/.hermes/worktrees/sdao-lab, never against live runtime config.

Tech stack:
- Python
- Hermes delegate tool and agent loop
- pytest
- isolated git worktree

---

## User-approved constraints

- Name of the system: SDAO
- Implementation by phases
- SSD applied to every phase
- TDD mandatory inside each phase
- Before implementation, add implementation tests against the current behavior to expose true failures
- Work only in isolated worktree/lab first
- Do not touch live ~/.hermes/config.yaml during experimentation
- Tests should be adversarial / against current behavior, not only happy-path

---

## SSD framing for this project

Each phase uses the same SSD structure:

1. Spec
- define exact decision rule for that phase
- define allowed / forbidden behavior
- define examples and counterexamples

2. Stress
- write adversarial tests against the current behavior
- include anti-patterns and edge cases
- verify tests fail for the intended reason

3. Develop
- implement the minimum production logic to satisfy the phase
- no broader refactors unless required by the tests

This means every phase contains TDD loops inside the Develop section:
- RED: write failing test
- GREEN: minimal implementation
- REFACTOR: cleanup while keeping tests green

---

## Worktree/lab

- Repo: /home/jh/.hermes/hermes-agent
- Worktree: /home/jh/.hermes/worktrees/sdao-lab
- Branch: chore/sdao-lab

Rule:
- use fixture configs inside tests
- do not overwrite /home/jh/.hermes/config.yaml as part of SDAO development

---

## High-level SDAO policy

Default mode:
- solo execution

Sequential delegation allowed only when:
- the task is meaningfully complex, and
- phases depend on previous outputs, or
- isolation/review justifies a child

Parallel delegation allowed only when all are true:
- there are at least 2 independent subtasks
- no subtask blocks another
- results can be merged cleanly
- concurrency creates real value over solo/sequential execution

Forbidden patterns:
- delegating simple single-step tasks
- parallelizing for style only
- using subagents for one quick lookup/edit when the parent can do it directly
- splitting dependent tasks into parallel children

Tie-breaker:
- when uncertain, prefer solo
- if not solo, prefer sequential over parallel

---

## Phase breakdown

### Phase 0: Baseline characterization

Objective:
- capture current delegation behavior before changing it

Files:
- Create: tests/orchestration/test_sdao_baseline_current_behavior.py
- Create: docs/plans/2026-04-12-sdao-strict-orchestrator-plan.md

Spec:
- baseline tests describe what current Hermes does today
- these are characterization tests, not final policy tests

Stress tests to write first:
- current behavior allows explicit delegate_task single-task execution
- current behavior allows explicit batch delegate_task when task count <= max_concurrent_children
- current behavior rejects batch size > max_concurrent_children
- current behavior has no strict built-in orchestration gate before delegate_task

Commands:
- pytest tests/orchestration/test_sdao_baseline_current_behavior.py -q

Exit criteria:
- baseline tests pass and document the starting point

---

### Phase 1: Policy kernel (pure decision function)

Objective:
- introduce a pure orchestration policy module that decides solo vs sequential vs parallel

Files:
- Create: agent/orchestration_policy.py
- Create: tests/orchestration/test_sdao_policy_kernel.py

Spec:
- implement a pure classifier with inputs like:
  - task_count_estimate
  - dependency flag
  - complexity band
  - independence flag
  - explicit user prohibition / preference
- outputs one of:
  - solo
  - sequential
  - parallel
- tie-break behavior must prefer solo, then sequential

Stress tests to write first:
- simple task => solo
- complex dependent task => sequential
- complex independent multi-task => parallel
- ambiguous task => solo
- explicit no-subagents preference => solo
- explicit dependency conflict on parallel candidate => sequential or solo, never parallel

Commands:
- pytest tests/orchestration/test_sdao_policy_kernel.py -q

Exit criteria:
- policy kernel exists as pure logic
- tests pass
- no runtime wiring yet

---

### Phase 2: Strict gate in delegation path

Objective:
- route delegation through SDAO policy instead of allowing opportunistic delegation with no strict guard

Files:
- Modify: tools/delegate_tool.py
- Create: tests/orchestration/test_sdao_delegate_gate.py

Spec:
- before batch/single child execution, evaluate SDAO decision
- reject or downgrade disallowed delegation modes
- batch execution should only occur when policy says parallel
- dependent task batches should be rejected or forced to sequential handling path

Stress tests to write first:
- simple single-task explicit delegation is rejected by strict policy when marked simple
- ambiguous batch is rejected for parallel
- more-than-one task with dependency markers does not run in parallel
- allowed independent batch still works
- explicit user “no subagents” blocks delegation

Commands:
- pytest tests/orchestration/test_sdao_delegate_gate.py -q
- pytest tests/tools/test_delegate.py -q

Exit criteria:
- delegate path respects policy
- legacy delegate behavior still works where explicitly allowed

---

### Phase 3: Automatic orchestrator hints before delegate_task

Objective:
- make the parent agent prefer SDAO decisions automatically instead of requiring the user to request delegation explicitly

Files:
- Modify: prompt/policy assembly path after locating exact file(s)
- Create: tests/orchestration/test_sdao_prompt_policy.py
- Possibly modify: run_agent.py or prompt builder path after inspection

Spec:
- parent agent instructions explicitly encode SDAO rules
- prompt should tell the agent:
  - solo by default
  - sequential for dependent complex work
  - parallel only for independent work
  - justify delegation internally before calling delegate_task

Stress tests to write first:
- prompt includes solo-by-default policy
- prompt includes tie-break toward sequential over parallel
- prompt includes explicit no-subagent override handling
- prompt includes prohibition on decorative delegation

Commands:
- pytest tests/orchestration/test_sdao_prompt_policy.py -q

Exit criteria:
- system prompt/policy carries SDAO consistently
- no live config dependency

---

### Phase 4: End-to-end behavior tests (implementation tests in contra)

Objective:
- prove SDAO works against real orchestration scenarios

Files:
- Create: tests/orchestration/test_sdao_e2e.py

Spec:
- these tests target actual behavior, not just pure policy logic

Adversarial cases:
- simple request should remain solo
- dependent multi-step request should not parallelize
- truly independent comparison/audit request should parallelize
- explicit “no subagentes” should stay solo even if task is complex
- task count beyond concurrency limit should still error clearly
- policy ambiguity should resolve to solo

Commands:
- pytest tests/orchestration/test_sdao_e2e.py -q

Exit criteria:
- E2E tests demonstrate SDAO contract clearly

---

### Phase 5: Docs, knobs, and safe rollout

Objective:
- make SDAO understandable and controllable without weakening strict defaults
- add dedicated documentation for implemented improvements and future improvements

Files:
- Create or update docs after implementation discovery
- Create: `docs/sdao/README.md`
- Create: `docs/sdao/improvements.md`
- Create: `docs/sdao/future-improvements.md`
- Possibly extend config schema only if needed and justified
- Add tests for config parsing if knobs are introduced

Status in this worktree:
- dedicated documentation added for SDAO overview
- dedicated documentation added for implemented improvements
- dedicated documentation added for future improvements
- no knobs introduced yet because strict default remains the priority

Potential knobs (only if necessary):
- orchestration.mode = strict
- orchestration.allow_parallel = true
- orchestration.require_explicit_user_opt_in = false

Rule:
- do not add knobs until the strict default behavior is stable and tested

Commands:
- targeted pytest for touched config/docs tests
- full relevant suite for orchestration/delegation

Exit criteria:
- strict default is documented
- rollout path is clear
- implemented improvements are documented in a dedicated file
- future improvements are documented in a dedicated file

---

## Testing policy for all phases

Mandatory rules:
- every phase starts with failing adversarial tests
- tests must be designed against current behavior, not idealized assumptions
- no production code before the failing test is observed
- after green, run adjacent regression suites

Minimum suite per phase:
- targeted new tests
- tests/tools/test_delegate.py -q when delegate behavior changes
- any prompt/agent tests affected by orchestration policy changes

---

## Suggested first implementation slice

Start with Phase 0 + Phase 1 only.

Why:
- lowest risk
- produces the policy kernel first
- gives us adversarial characterization before runtime rewiring
- aligns with your preference for tests in contra before implementation

---

## Acceptance criteria for the whole SDAO initiative

- solo by default is enforced, not merely suggested
- parallel execution requires demonstrable independence
- sequential execution is preferred over parallel under uncertainty
- explicit user prohibition of subagents is respected
- implementation tests in contra exist for each phase
- all work proven in worktree before any real rollout

---

## Next step

Execute only Phase 0 in the worktree first:
- write adversarial characterization tests for current behavior
- run them
- save the red/green evidence
- then move to Phase 1

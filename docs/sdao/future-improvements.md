# SDAO Future Improvements

This document tracks improvements that are not yet implemented but are good candidates for later phases.

## 1. True sequential subagent orchestration mode

Current state
- SDAO can classify work as `sequential`, but the strict gate currently blocks parallel delegation and leaves sequencing to the parent flow rather than executing a dedicated sequential child pipeline.

Future improvement
- Implement an explicit sequential delegation executor that runs child tasks in order under one orchestration contract.

Value
- closes the gap between classification and runtime execution
- makes sequential orchestration first-class

## 2. Better complexity inference

Current state
- Complexity and independence are inferred with lightweight heuristics and markers.

Future improvement
- Improve inference with richer signals such as:
  - task graph hints
  - file overlap
  - tool-type risk
  - explicit step structure
  - semantic dependency cues

Value
- fewer false positives and false negatives
- better routing quality under realistic prompts

## 3. Stronger ambiguity handling and explanations

Current state
- Ambiguity resolves conservatively.

Future improvement
- Return more structured policy explanations explaining exactly why SDAO chose solo, sequential, or blocked parallelism.

Value
- easier debugging
- easier user trust and operator inspection

## 4. Config knobs only if justified

Current state
- No rollout knobs were added yet.

Future improvement
- Add configuration only if strict default proves stable and there is a concrete need.

Possible knobs
- `orchestration.mode = strict`
- `orchestration.allow_parallel = true`
- `orchestration.require_explicit_user_opt_in = false`

Rule
- knobs must not weaken safety by default
- knobs must be covered by tests before rollout

## 5. Structured audit logging for orchestration decisions

Future improvement
- Record policy inputs and chosen orchestration mode in structured logs or trace events.

Value
- easier forensic debugging
- better observability for delegation behavior
- useful for future analytics and tuning

## 6. User-facing explanation surfaces

Future improvement
- Add optional concise user-visible explanations when a delegation request is blocked by SDAO.

Value
- clearer UX
- less confusion when parent stays solo or rejects parallelization

## 7. Extended E2E coverage

Future improvement
- Add cases for:
  - mixed-tool workloads
  - file mutation overlap
  - sequential follow-up chains
  - provider-specific delegation behavior
  - interaction with reasoning settings
  - child failure aggregation and recovery behavior

Value
- higher confidence before rollout

## 8. Rollout documentation

Future improvement
- Add an operator rollout guide covering:
  - worktree validation
  - backup strategy
  - revert steps
  - smoke tests
  - post-rollout checks

Value
- safer production adoption

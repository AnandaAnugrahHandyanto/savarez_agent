# Memory Fabric Architecture Convergence Snapshot v0.1

Date: 2026-05-24

This snapshot records where the Hermes Memory Fabric architecture has converged
after the first 30 read-only foundations and the follow-on real write executor
boundary planning modules. It is documentation and architecture analysis only.
It does not define a new write gate, executor, token issuer, proposal path,
operation ledger writer, Memory Graph writer, OpenClaw config mutation path, or
governance submission path. It is also not a code review gate.

## Scope

In scope:

- Summarize the current foundation chain from the benchmark scaffold through the
  real write executor code review plan.
- Identify the boundary between read-only candidates and any future real write
  executor.
- Prove that no real executor source file exists yet.
- Identify repeated module patterns that should be extracted before more gates
  are added.
- Recommend the next architecture work.

Out of scope:

- Creating `agent/memory_human_approval_token_real_write_executor.py`.
- Creating `tests/agent/test_memory_human_approval_token_real_write_executor.py`.
- Creating executor tests, executor fixtures, approval tokens, proposal files,
  token files, audit files, operation ledger events, or graph writes.
- Submitting anything to governance.

## Current Foundation Chain

The benchmark scaffold in `benchmarks/hermes_memory_bench/core.py` now acts as a
single read-only smoke chain. It evaluates fixture cases from
`benchmarks/hermes_memory_bench/fixtures/smoke_cases.json`, returns a structured
report, and carries a benchmark-level policy that explicitly keeps memory,
configuration, graph, and operation-ledger writes disabled.

The early foundations cover recall, temporal accuracy, source provenance,
governance write safety, project scope isolation, contradiction handling, hybrid
retrieval fusion, the bi-temporal fact graph, the contradiction engine, memory
compilation, memory blocks, review queue construction, review decisions,
proposal drafts, governance submission candidates, governance submission
packets, human review outcomes, real proposal planning, real proposal dry-runs,
and real proposal write-lock eligibility.

The human approval token foundations then add a longer read-only approval chain:

1. Human approval token request.
2. Human approval token review gate.
3. Human approval token issuance plan.
4. Human approval token issuance dry run.
5. Human approval token write lock gate.
6. Final confirmation request.
7. Final confirmation review gate.
8. Token write execution plan.
9. Token write execution dry run.
10. Token write final gate.

The first 30 foundations converge at
`memory_human_approval_token_write_final_gate`, whose successful status is
`eligible_for_real_token_write_executor`. That is the last foundation before the
architecture-only executor boundary.

Five follow-on modules then describe the future executor boundary without
creating or invoking it:

1. `agent/memory_human_approval_token_real_write_executor_contract.py` creates a
   read-only contract candidate when the final gate is eligible.
2. `agent/memory_human_approval_token_real_write_executor_contract_review_gate.py`
   creates a read-only contract review outcome candidate.
3. `agent/memory_human_approval_token_real_write_executor_implementation_plan.py`
   creates a read-only implementation plan candidate and names future interfaces
   and files with `create_in_v0_1: False`.
4. `agent/memory_human_approval_token_real_write_executor_implementation_dry_run.py`
   previews module, interface, idempotency, filesystem, audit, rollback, and test
   boundaries while keeping source-file creation false.
5. `agent/memory_human_approval_token_real_write_executor_code_review_plan.py`
   creates a read-only code review plan candidate whose routing requires a later
   code review gate before executor source creation.

`tests/benchmarks/test_hermes_memory_bench.py` asserts that the smoke chain
stays read-only, that graph and operation-ledger files are not created, and that
the real-write-executor contract through code-review-plan dimensions do not
invoke or implement a real executor.

## Real Write Executor Boundary

The current boundary is intentionally declarative. The real-write-executor
modules define candidate records, validation, explanations, recommendations,
summaries, future interface names, future file paths, and no-write acceptance
criteria. They do not perform writes.

Observed boundary guarantees:

- Policy dictionaries set `read_only: True`.
- Policy dictionaries set `would_write_memory`, `would_modify_config`, and
  `would_write_graph` to false.
- Operation ledger creation is forbidden with
  `does_not_create_operation_events: True`.
- Proposal, token, approval audit, and operation ledger writes remain false.
- Executor invocation and executor implementation flags remain false.
- Implementation plan and code review plan structures mention future executor
  files only with `create_in_v0_1: False`, `contains_executor_code_in_v0_1:
  False`, and `writes_files_in_v0_1: False`.
- The code review plan requires a later
  `real_token_write_executor_code_review_gate_required_before_executor_source_creation`
  route before any executor source can exist.

The product of this chain is therefore an architecture contract and review plan,
not an executor.

## Proof No Executor Source Exists

The repository currently has the architecture and planning modules, but the
future executor source and future executor test module are absent.

Checked paths:

- `agent/memory_human_approval_token_real_write_executor.py` does not exist.
- `tests/agent/test_memory_human_approval_token_real_write_executor.py` does not
  exist.

Local checks performed during this snapshot:

- `test -e agent/memory_human_approval_token_real_write_executor.py` returned
  exit code `1`.
- `test -e tests/agent/test_memory_human_approval_token_real_write_executor.py`
  returned exit code `1`.
- `rg --files agent tests/agent | rg '^agent/memory_human_approval_token_real_write_executor\.py$|^tests/agent/test_memory_human_approval_token_real_write_executor\.py$'`
  returned no matches.

This is consistent with the implementation plan and code review plan metadata:
the future executor paths are named as required review targets, not as created
files.

## Duplication Analysis

The current modules are coherent, but the chain now repeats enough structure
that more gate modules would increase maintenance risk.

Repeated create patterns:

- Every candidate builder deep-copies its source input.
- Each builder recomputes upstream validation before setting its own status.
- Each builder forwards a long list of source IDs and preview records.
- Each builder creates deterministic IDs using stable JSON plus SHA-256.
- Each builder attaches a validation result, next-step recommendation, source
  snapshot, and policy dictionary.

Repeated validate patterns:

- Required-key checks are locally enumerated per module.
- Source snapshot matching is repeated by comparing copied fields back to the
  source.
- Preview fields are checked for `preview_only: True`.
- Forbidden true flags are checked across the same write and executor keys.
- Policy fields are compared against expected false values.
- Lock reasons are recomputed and compared to stored lock reasons.

Repeated explain and recommend patterns:

- Explanation functions normalize validation status, routing, status, lock
  reason, source IDs, and policy.
- Recommendation functions map valid/locked states to the next route while
  restating that writes, executor invocation, and executor implementation remain
  false.
- The same no-write flags appear in many recommendation payloads.

Repeated summarize patterns:

- Summaries count total, valid, invalid, locked, and by-status records.
- Most summaries group by `block_type`, status, and lock reason.
- Each summary returns the local policy dictionary.

Repeated benchmark patterns:

- `benchmarks/hermes_memory_bench/core.py` rebuilds the same long candidate
  chain in every downstream dimension branch.
- Evidence payload assembly repeats the same candidate arrays and no-write
  flags.
- The benchmark therefore scales linearly in code size with every new gate.

## Shared Abstraction Candidates

The next code work should extract read-only helpers before adding more gates.
The target is not a framework rewrite; it is a small set of narrow utilities
that remove repeated safety logic while preserving explicit module contracts.

Candidate lifecycle utilities:

- Deterministic ID helper for versioned candidate identity hashes.
- Candidate envelope builder for status, routing, lock reason, validation,
  recommendation, source snapshot, and policy.
- Summary counter helper for total, valid, invalid, locked, by-status,
  by-lock-reason, and by-block-type counts.
- Source snapshot matcher that reports stable `field_must_match_source_snapshot`
  errors.

Preview integrity utilities:

- Shared preview field constants for proposal, ledger, token, audit, target path,
  and write payload previews.
- Shared `preview_only` checker.
- Shared forbidden true flag checker for `created`, `written`, `token_issued`,
  `approved`, `persisted`, `writes_*`, executor invocation, executor
  implementation, and executor source creation.
- Shared checklist preservation checks for no-write and no-executor controls.

Source lineage utilities:

- Shared source key tuples for proposal, governance, approval token, final gate,
  and executor-boundary lineages.
- Field copier for lineage IDs and source evidence IDs.
- Source evidence validator for `source_pattern_ids` and `source_fact_ids`.
- Compact lineage summary for explain and benchmark evidence payloads.

Policy assertion utilities:

- Shared read-only policy assertion for memory, graph, config, proposal, ledger,
  token, audit, governance, and executor flags.
- Shared policy merge or exact-match helper for local policy dictionaries.
- Shared error naming convention for `policy_<key>_must_be_true/false`.
- Optional static assertion list for future tests to ensure no executor creation
  flags drift to true.

Benchmark chain builder utilities:

- A read-only chain builder that can stop at a named stage and return all prior
  candidates.
- Evidence assembler that emits the repeated candidate arrays and no-write flags.
- Dimension dispatch metadata mapping stages to expected answer fields and
  summary functions.
- Fixture-light smoke case generation or validation so new stages do not require
  manually duplicating the full upstream chain in every branch.

## Proposed Module Families

These are architecture families, not required filenames:

- Candidate lifecycle utilities: own deterministic candidate IDs, candidate
  envelopes, validation-result attachment, recommendation attachment, and summary
  counters.
- Preview integrity utilities: own preview-only checks, forbidden true flag
  checks, required no-write checklist preservation, and write-preview field
  grouping.
- Source lineage utilities: own source ID propagation, source snapshot matching,
  source evidence validation, and compact lineage explain payloads.
- Policy assertion utilities: own read-only/no-write/no-executor policy
  assertions and error names.
- Benchmark chain builder utilities: own smoke chain construction, stage stopping,
  repeated evidence flags, and summary dispatch.

## What Must Not Be Merged Yet

Do not merge any of the following before the shared utilities and a separate
sandbox executor design contract exist:

- Real executor source module.
- Real executor tests.
- Real token write executor implementation.
- Real token write executor invocation path.
- Code review gate implementation that authorizes executor source creation.
- Approval token issuance or persistence.
- Token file writes.
- Approval audit writes.
- Proposal file writes.
- Operation ledger writes or operation events.
- Memory Graph writes.
- OpenClaw config changes.
- Governance submission execution.
- Benchmark cases that expect real writes as success.

## Minimum Safe Sandbox Executor Boundary

A future sandbox executor can be useful, but the minimum safe boundary must be
designed before implementation. The smallest acceptable sandbox boundary is:

- It must be sandbox-only and disabled for real Hermes memory paths by default.
- It must require an explicit caller-provided sandbox root that is not
  `HERMES_HOME`, not the Memory Graph path, not the proposal path, and not the
  operation ledger path.
- It must accept only already-approved read-only candidate inputs and recompute
  all upstream validations.
- It must reject source candidates when any preview, policy, lineage, or
  no-write checklist integrity check fails.
- It must write only disposable sandbox token and sandbox approval-audit payloads
  after resolving paths under the sandbox root.
- It must not write proposals, operation ledger entries, graph state, OpenClaw
  config, or durable memory.
- It must use deterministic payload fingerprints, atomic same-directory replace,
  and mismatch-on-existing-file lock behavior.
- It must return a sandbox receipt, not a durable approval token.
- It must remain separate from any future real executor.

This snapshot does not implement that boundary.

## Risk Table

| Risk | Current signal | Impact | Recommendation |
| --- | --- | --- | --- |
| Gate explosion | The chain now has many read-only gate and plan modules, and the benchmark repeats the whole chain per downstream dimension. | More gates will multiply code paths without increasing user-visible capability. | Pause new gate additions and extract shared read-only utilities first. |
| Benchmark bloat | `core.py` rebuilds the same upstream chain in many `if dimension == ...` branches. | Every new foundation adds large fixture and branch churn. | Add a benchmark chain builder before adding more dimensions. |
| Repeated validation logic | Preview, policy, source lineage, required-key, and deterministic-ID checks are locally repeated. | A safety invariant can drift in one module while staying correct elsewhere. | Extract preview integrity, policy assertion, source lineage, and lifecycle helpers. |
| Accidental real write | Future executor paths are named in plan metadata, and code review planning points toward source creation. | A later change could accidentally create files, issue tokens, or write audit state before the boundary is reviewed. | Keep executor source absent, require a sandbox design contract first, and assert absent real executor files in review. |
| Unclear product entrypoint | The architecture is deep, but the user-facing Subspace / Recall / Dashboard layer is not represented in this chain. | Work may continue optimizing gates instead of making Memory Fabric usable. | Start the product layer after utility extraction and the sandbox design contract. |

## Recommendations

Do not continue adding gates right now. The architecture has enough read-only
stages to describe the current governance boundary. More gates would increase
duplication and make the product harder to understand unless they replace real
risk, not just extend the chain.

Do not implement a minimal sandbox executor now. First extract shared read-only
candidate utilities and write a sandbox executor design contract that fixes the
sandbox root, receipt shape, atomicity rules, idempotency behavior, and
non-durable guarantees. A sandbox executor can follow after that contract is
reviewed.

Pivot to Subspace / Recall / Dashboard first after the utility extraction and
sandbox design contract are underway. The product layer can expose recall,
lineage, review status, and governance boundaries without needing real writes,
which makes it the safer next user-visible convergence point.

## Next Three Work Items

1. Extract shared read-only candidate utilities.
   Focus on lifecycle, preview integrity, source lineage, policy assertions, and
   summary helpers. Keep behavior identical and covered by existing module tests.

2. Create a sandbox executor design contract.
   Define the allowed sandbox root, input contract, receipt shape, idempotency
   strategy, atomic write model, rollback behavior, and explicit real-surface
   exclusions. Do not implement executor code in this step.

3. Start the Subspace / Recall / Dashboard product layer.
   Build the first read-only entrypoint around retrieval, lineage, review state,
   and Memory Fabric status rather than extending the write gate chain.

## Convergence Conclusion

Memory Fabric has reached a clear architecture boundary: the benchmark scaffold
and first 30 foundations establish read-only recall, provenance, governance, and
human approval token flow through the final gate; the five follow-on modules
describe, review, plan, dry-run, and code-review-plan the future real write
executor without creating it.

The next convergence move should be consolidation and product surfacing, not
another gate. Shared utilities should reduce duplication, a sandbox executor
contract should define the only acceptable non-durable write experiment, and
Subspace / Recall / Dashboard should become the first visible layer over the
read-only Memory Fabric.

## Appendix: Read-only Candidate Utilities v0.1

The first utility extraction target is
`agent/memory_read_only_candidate_utils.py`. It is a pure read-only helper module
for shared policy assertions, preview integrity checks, source lineage copying,
stable digests, and summary counters. It does not create a gate, executor,
proposal, token, ledger event, graph write, benchmark dimension, or OpenClaw
configuration change.

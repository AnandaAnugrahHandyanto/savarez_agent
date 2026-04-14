# Layered Memory Provider — Current Capability and Skill-Candidate Workflow

Goal: document the current shipped behavior of the `layered` provider after the multi-phase implementation pass, with emphasis on the skill-candidate lifecycle, approval strategies, evidence packaging, and the exposed CLI/tool surfaces.

Status: implemented in repo, locally testable, and covered by targeted regression.

---

## 1. What the layered provider now does

The `layered` provider is no longer just a Phase 1 storage scaffold.
It now acts as a local long-term memory orchestration layer for JARVIS-style evolution.

Implemented responsibilities:

- persistent local storage via SQLite
- FTS5-backed recall
- typed memory layers
- scored retrieval and recency-sensitive ordering
- semantic/procedural consolidation
- reflection extraction
- archive/episodic -> semantic promotion
- successful-pattern -> procedural promotion
- delegation capture
- skill-candidate detection
- skill-draft generation
- review-gated candidate packaging
- candidate indexing
- strategy-aware approval/install flow
- evidence-rich candidate payloads
- CLI slash surface
- formal Hermes tool surface

This means the provider now covers the end-to-end path from remembered execution patterns to candidate capability assets.

---

## 2. Memory layers

The provider persists records into these layers:

- `identity_core`
- `semantic`
- `episodic`
- `reflection`
- `archive`
- `procedural_index`

Operational intent:

- `identity_core`
  stable, high-value user/system constraints mirrored from built-in `user`

- `semantic`
  durable facts and promoted repeated facts

- `episodic`
  session summaries, compression checkpoints, delegation observations

- `reflection`
  extracted lessons, root-cause style statements, “worked because / failed because” patterns

- `archive`
  turn-level rolling historical capture

- `procedural_index`
  repeated successful workflows, procedural candidates, skill-candidate bridge records

---

## 3. Current promotion pipeline

### 3.1 Built-in memory mirroring

Explicit built-in memory writes are mirrored into layered storage:

- `target=user` -> `identity_core`
- `target=memory` -> `semantic`

### 3.2 Episodic/session capture

The provider persists:

- `sync_turn()` -> archive turn records
- `on_pre_compress()` -> episodic checkpoint + preservation hint
- `on_session_end()` -> session summary

### 3.3 Reflection and consolidation

At session end the provider can:

- extract lightweight reflection statements
- consolidate repeated semantic facts
- consolidate repeated procedural patterns

### 3.4 Promotion to procedural memory

Repeated successful workflows are promoted into `procedural_index`.

Current examples include:

- “Write failing tests first, then implement the fix, then verify tests pass.”
- “Use SQLite FTS with targeted tests to implement and verify layered memory retrieval changes.”

Delegation-derived successful patterns can also populate `procedural_index`.

---

## 4. Skill-candidate lifecycle

### 4.1 Candidate threshold

A procedural record becomes eligible for skill-candidate promotion when:

- effective recurrence reaches threshold
- current threshold is `3`
- effective recurrence uses:
  - `max(recurrence, metadata.occurrences)`

### 4.2 Review gate

Before packaging, candidates pass a lightweight gate:

- `confidence < 0.6` -> `rejected`, `low_confidence`
- insufficient recurrence -> rejected
- low signal but viable -> `pending`, human review needed
- otherwise -> `pending`, ready for human review

### 4.3 Generated artifacts

For reviewable candidates the provider generates:

1. draft markdown
   `HERMES_HOME/memory/layered_artifacts/skill_drafts/<skill_name>.md`

2. publish-ready candidate package
   `HERMES_HOME/memory/layered_artifacts/skill_candidates/<skill_name>/`

   Package contents:
   - `SKILL.md`
   - `candidate.json`

3. candidate index
   `HERMES_HOME/memory/layered_artifacts/skill_candidates/skill_candidates.json`

---

## 5. Candidate payload and evidence packaging

Each candidate can now carry richer metadata, including:

- `skill_candidate`
- `skill_candidate_threshold`
- `effective_recurrence`
- `review_status`
- `review_gate_reason`
- `skill_draft_path`
- `publish_ready_dir`
- `candidate_index_path`
- `approval_strategy`
- `installed_skill_path`

### 5.1 Evidence payload

`candidate.json` and provider inspection results now include `evidence` with fields such as:

- `source`
- `promoted_from`
- `session_id`
- `child_session_id`
- `effective_recurrence`
- `promotion_rationale`
- `sample_evidence`
- `verification_hints`

Intent:

- explain why this candidate exists
- show whether it came from promotion or delegation
- preserve enough evidence for future governance/review logic
- provide lightweight verification guidance before approval

---

## 6. Approval strategies

Approval is no longer a binary overwrite.

`decide_install_strategy()` currently returns one of:

- `create`
  target skill does not exist

- `duplicate_skip`
  existing installed skill matches candidate package content exactly

- `patch_existing`
  existing installed skill exists but differs from candidate package

- `create_variant`
  canonical name is reserved/locked and a variant should be installed instead

Current `create_variant` trigger:

- a `LOCKED` file exists in the existing skill directory

### 6.1 Approval behavior

`approve_skill_candidate(skill_name)` behaves as follows:

- `create`
  installs normal target skill

- `duplicate_skip`
  does not rewrite content, but marks candidate approved with strategy metadata

- `patch_existing`
  overwrites installed `SKILL.md`

- `create_variant`
  installs to a generated variant path like:
  `<skill_name>@variant-1`

All approval outcomes update candidate metadata and candidate index.

---

## 7. User/operator surfaces

### 7.1 CLI slash command

Implemented slash command:

`/skill-candidates`

Supported subcommands:

- `list`
- `inspect <name>`
- `approve <name>`
- `reject <name> [reason]`

Implementation entry:

- `hermes_cli/skill_candidates.py`

CLI wiring:

- `hermes_cli/commands.py`
- `cli.py`

### 7.2 Formal tool surface

Implemented formal tool:

- `skill_candidates`

Supported actions:

- `list`
- `inspect`
- `approve`
- `reject`

Tool file:

- `tools/skill_candidates_tool.py`

Imported via:

- `model_tools.py`

This allows the agent to manage candidates through standard tool-calling, not only through CLI interaction.

---

## 8. Current operator workflow

Recommended current flow:

1. inspect candidate list
   - CLI: `/skill-candidates list`
   - tool: `skill_candidates(action="list")`

2. inspect one candidate
   - review draft path
   - review package path
   - review evidence payload
   - review strategy if approval is likely

3. approve or reject
   - approve when candidate is valid and should join local skill assets
   - reject when confidence is weak or the pattern is undesirable

4. for existing skills, rely on approval strategy
   - duplicate -> skip
   - divergent but same name -> patch_existing
   - reserved canonical name -> create_variant

---

## 9. Known boundaries

Still intentionally limited:

- no direct `skill_manage` invocation inside provider
- no auto-publish into full Hermes skill lifecycle registry workflow beyond local install bridge
- no generalized semantic entity extraction beyond current heuristics
- no embeddings/hybrid retrieval yet
- no dedicated gateway/native slash candidate UI yet
- no evidence capture of changed files / exact test stdout yet

---

## 10. Recommended next steps

Most valuable next moves:

1. operator docs / repo docs polish
2. explicit candidate schema documentation
3. richer evidence capture:
   - touched files
   - test commands
   - test output summaries
   - sample task/result pairs
4. policy refinement:
   - patch-vs-variant rules
   - duplicate thresholds
   - eventual auto-approval policy for safe patterns
5. bridge from local install to broader Hermes skill lifecycle governance

---

## 11. Verification snapshot

Current targeted regression set used during this implementation line:

- `tests/agent/test_layered_memory_provider.py`
- `tests/agent/test_memory_provider.py`
- `tests/hermes_cli/test_web_server.py`
- `tests/cli/test_skill_candidates_command.py`
- `tests/tools/test_skill_candidates_tool.py`

Latest targeted result at cleanup time:

- `158 passed, 1 warning`

This confirms the current layered provider + candidate workflow stack is internally coherent at the targeted test boundary.

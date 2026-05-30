# Phase 2: UA Flywheel Integration — Orchestration Layer

> **Parent doc:** `.plans/ua-incorporation-strategy.md`
> **Prerequisite:** Phase 1 (Foundation) must be complete — `scripts/code-scan/scan_project.py`, `scripts/code-scan/language_registry.py`, `scripts/code-scan/graph_schema.py`, and `.hermesignore` must exist and pass verification.
> **Status:** Draft — awaiting approval for full-phase execution.

---

## Objective

Build the JIT skill layer that makes the Phase 1 scan scripts actionable by agents. Phase 2 delivers two skills (code-scan + validation-gate), the `extract_imports.py` script, and optional integration with `requesting-code-review`.

**Context budget:** ≤100 total lines when both skills are JIT-loaded (each SKILL.md ≤80 lines).

---

## Approval Scope

Approving Phase 2 authorizes Hermes to execute the full phase as a review-branch workstream, with slice-by-slice local verification and reviewer checks before any commit. It does **not** authorize merge, deployment, publishing, or production mutation.

### Included

1. Implement `scripts/code-scan/extract_imports.py` and tests.
2. Add `skills/code-analysis/code-scan/SKILL.md` and lightweight supporting references only if needed.
3. Add `skills/code-analysis/validation-gate/SKILL.md` and deterministic validation contract tests.
4. Prepare optional `requesting-code-review` integration as a documented follow-up or isolated final slice; execute it only if approval explicitly includes D4.

### Excluded / Deferred

- No dashboard, React UI, Vite server, graph visualization, or web endpoint.
- No automatic prompt/context injection and no always-on scanning.
- No new runtime dependency unless JC approves a dependency exception.
- No tree-sitter or WASM; regex/stdlib extraction only in Phase 2.
- No SQLite/summary store or `flywheel scan` CLI command; the older Phase 2 summary/CLI concept is deferred.
- No commit/push/merge/deploy beyond the local/branch checkpoint JC explicitly approves.

### Owners and Review

| Role | Responsibility |
|---|---|
| Hermes | Coordinates, maintains docs/state, verifies outputs, presents approval gates |
| coder subagent | Implements each approved slice; no commit/push authority |
| reviewer subagent | Reviews spec compliance, quality/security, context-budget, and scope preservation |
| JC | Approves full Phase 2 execution and separately approves commit/push/merge/deploy gates |

---

## Prerequisites

Phase 2 must not start until Phase 1 is complete and verified:

- `scripts/code-scan/scan_project.py` exists and emits stable JSON.
- `scripts/code-scan/language_registry.py` exists and is imported by `scan_project.py`.
- `scripts/code-scan/graph_schema.py` exists and can validate node/edge contracts.
- `.hermesignore` exists with default exclusions.
- Phase 1 tests pass on the selected test-bed repos.

---

## Test-Bed Repos

Use these local repos unless JC substitutes others before approval:

| Tier | Repo | Purpose |
|---|---|---|
| Small | `/home/jarrad/.hermes/hermes-agent/cass_memory_system` | Python package-scale scan/import extraction |
| Medium | `/home/jarrad/.hermes/hermes-agent/mission-control` | TypeScript/Node project with frontend-style imports |
| Large/current | `/home/jarrad/.hermes/hermes-agent` | Real Hermes repo smoke/performance guardrail |

If any test-bed path is moved outside this worktree before execution, update this table before starting Phase 2.

---

## Rollback / Off-Switch Plan

- Phase 2 is explicit invocation only: agents load `code-scan` / `validation-gate` only when requested or when a bead explicitly requires it.
- If a skill misbehaves, remove or revert only `skills/code-analysis/<skill>/` and keep Phase 1 scripts intact.
- If `extract_imports.py` fails on a language, return warnings and incomplete import coverage; do not block scan summaries unless JSON output is invalid.
- If performance exceeds budget, disable the optional D4 code-review integration first, then narrow language coverage before changing Phase 1 scanner behavior.
- No persistent project artifacts are written in Phase 2 except temporary scan/import JSON under an ignored output path agreed during implementation.

---

## Deliverables

### D1: `scripts/code-scan/extract_imports.py`

**Purpose:** Extract import/dependency maps from the scan_project.py output. Reads scan JSON, parses import statements, returns import map JSON.

**Scope:**
- Read `scan_project.py` JSON output
- Regex-based import extraction (start with regex; tree-sitter is Phase 4)
- Support: Python (`import X`, `from X import Y`), JavaScript/TypeScript (`import X from 'Y'`, `require()`), Rust (`use X::Y`), Go (`import "pkg"`), shell/bash (`source`, `.`)
- Output: `{ "files": { "path/to/file": ["imported_module1", ...] } }`
- No LLM involvement

**Acceptance criteria:**
- Runs standalone: `python scripts/code-scan/extract_imports.py <scan_output.json>`
- Correctly extracts imports from ≥5 supported languages
- Output is valid JSON parseable by downstream consumers
- Zero new runtime dependencies

---

### D2: `skills/code-analysis/code-scan/SKILL.md`

**Purpose:** JIT skill that orchestrates the scan pipeline. Agent loads this skill when analyzing a codebase.

**Frontmatter:** Must follow existing SKILL.md convention with `hermes.tags` including `on-demand`.

**Behavior:**
1. On activation, confirms target project directory
2. Runs `scan_project.py` against the project
3. Runs `extract_imports.py` on scan output
4. Reads the JSON artifacts
5. Uses LLM to synthesize non-deterministic fields: project name, one-line description, framework narrative
6. Renders structured summary to user

**Acceptance criteria:**
- SKILL.md ≤80 lines
- Skill loads via `agent/skill_commands.py` as user message (not system prompt)
- End-to-end scan of a 50-file project completes in <5s (script execution only; LLM synthesis excluded from timing)
- Agent produces correct scan output without hallucinating file structures

**Skill structure (proposed):**
```markdown
---
name: code-scan
hermes.tags: [on-demand, code-analysis, project-mapping]
---

# Code Scan Skill

When the user asks to analyze, map, or understand a codebase:

1. Run `scripts/code-scan/scan_project.py <target_dir>` → capture JSON output
2. Run `scripts/code-scan/extract_imports.py <scan_output.json>` → capture import map
3. Read both JSON artifacts
4. Synthesize: project name, one-line description, framework/stack narrative
5. Present structured summary

Constraints:
- Never hallucinate file structures — only report what the scan scripts return
- If scan fails, report the error; do not guess
- Respect `.hermesignore` rules

Output format:
## Project: <name>
- **Description:** <one-line>
- **Languages:** <detected>
- **Frameworks:** <detected>
- **Structure:** <top-level dirs + key files>
- **Import graph highlights:** <top 5 most-imported modules>
```

---

### D3: `skills/code-analysis/validation-gate/SKILL.md`

**Purpose:** Two-phase validation skill. Phase 1 runs a deterministic validation script; Phase 2 reads results and renders approval/rejection.

**Behavior:**
1. Accepts a target artifact (graph JSON, scan output, or analysis result)
2. Runs a Python validation script against it (uses `graph_schema.py` for schema validation)
3. Reads the JSON validation results
4. Renders: APPROVED / WARNING / REJECTED with structured notes
5. If REJECTED with critical issues, triggers revision gate

**Acceptance criteria:**
- SKILL.md ≤80 lines
- Validation script runs in <2s on typical outputs
- Warnings don't block; only critical issues trigger REJECTED
- Maps to existing Revision gate in gates taxonomy

**Skill structure (proposed):**
```markdown
---
name: validation-gate
hermes.tags: [on-demand, code-analysis, quality-gate]
---

# Validation Gate

When verifying analysis output, graph structures, or code mappings:

1. Write/run a Python validation script using `scripts/code-scan/graph_schema.py`
2. Execute the script → capture JSON results
3. Read and interpret results:
   - **APPROVED:** All checks pass
   - **WARNING:** Non-blocking issues found (render as notes)
   - **REJECTED:** Critical issues found (trigger revision)
4. Render structured report to user

Validation checks:
- Node types are valid (via NODE_TYPE enum)
- Edge types are valid (via EDGE_TYPE enum)
- No orphan nodes (all edges reference existing node IDs)
- No self-referencing edges (unless type allows)

Do NOT validate using LLM intuition — only report what the script returns.
```

---

### D4: Integration with `requesting-code-review` (Optional / Approval-Scoped)

**Purpose:** Extend the existing `requesting-code-review` skill to optionally run scan + validation gate on changed files in a PR/diff context.

**Scope:**
- Add an optional code-scan step when reviewing code changes
- Run `scan_project.py --changed` (or parse scan output for changed files only)
- Feed results into review skill context
- No new files — update existing skill

**Acceptance criteria:**
- Only activates when the user requests code analysis as part of review
- Does not slow down normal review flow when code-scan is not requested
- Existing `requesting-code-review` tests still pass

---

## Verification Plan

| Test | Command / Method | Pass Criteria |
|---|---|---|
| Unit: extract_imports.py | `pytest tests/tools/test_extract_imports.py` | All tests pass |
| Fixture coverage | Python, JS/TS, Rust, Go, shell fixture files | Expected imports match golden JSON |
| Integration: full scan pipeline | Agent loads code-scan skill, scans `cass_memory_system` and `mission-control` | Produces correct JSON, no hallucination |
| Large-repo smoke | Run scan/import pipeline against this Hermes repo | Completes without scanning ignored giant/vendor dirs; produces valid JSON |
| Integration: validation gate | Feed known-good and known-bad graph JSON to validation skill | Correct APPROVED/WARNING/REJECTED verdicts |
| Context budget check | Measure loaded SKILL.md total lines | ≤100 lines for both skills |
| Scope guardrail | Search diff for dashboard/React/tree-sitter/SQLite/auto-injection additions | No excluded feature enters Phase 2 |
| Existing tests | Targeted tests touched by Phase 2 plus any affected skill tests | No regression |

---

## Risks and Mitigations

| Risk | Mitigation |
|---|---|
| Import regex extraction misses edge cases | Acceptable for MVP; Phase 4 adds tree-sitter |
| Skill files exceed 80-line limit during iteration | Enforce in review; split into sub-skills if needed |
| Scan scripts become a maintenance burden | Keep scripts focused; each <200 LOC |
| Validation gate false positives | Separate warnings from critical issues; warnings never block |

---

## Phase 2 Deliverables Checklist

- [ ] Prerequisite: Phase 1 verified and committed before execution begins
- [ ] D1: `scripts/code-scan/extract_imports.py` + unit tests
- [ ] D2: `skills/code-analysis/code-scan/SKILL.md`
- [ ] D3: `skills/code-analysis/validation-gate/SKILL.md`
- [ ] D4: `requesting-code-review` integration only if explicitly included in approval
- [ ] Verification: tests pass, context budget met, scope guardrails pass
- [ ] Reviewer: spec compliance + quality/security + scope preservation PASS
- [ ] Approval: This entire Phase 2 plan approved by JC before execution

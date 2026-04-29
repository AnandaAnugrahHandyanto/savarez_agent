# Contributing

This file codifies how work happens in the Motion Granted Citation Database repo. It is written for agents (Claude Code instances) first and human contributors second. Read it together with:

- **`binding/v7.2.md`** — the ratified architectural authority.
- **`AGENT-DISCIPLINE.md`** — the operational doctrine. Contains the Zero-Inference rules (§1), the A-L high-hallucination-risk category table (§3), the scope-rules block (§5), and the self-audit protocol (§7).
- **`.claude/rules/`** — per-subsystem DO-NOT lists with explicit v7.2 cites (`producer-boundary.md`, `reports-readonly.md`, `scaffold-boundary.md`, plus the `example-rule.md` template).
- **`BACKLOG.md`** — ratified open items, Tier B carry-overs, §29 gap list with tier tags.

Every load-bearing schema / invariant / taxonomy / role / tier claim must cite a `v7.2 §N line M` or point at the `AGENT-DISCIPLINE.md` / `.claude/rules/` file that binds it.

---

## 1. The operator-only boundary

Agents never do the following; the operator does:

- **No `git push`** to `main` or any protected branch.
- **No `gh pr merge`**, no force-push, no tag creation, no release cut.
- **No direct commits to `main`** from a session. Feature branches only: `overnight/<task>-<date>`, worktree branches, or short-lived topic branches.
- **No Clay-binding rulings.** If an item requires Clay's signature (R-1, R-3, the §26 retention numbers, anything in v7.2 §24's "Clay ruling → Porter" lane), draft the recommendation and tag `<X>_PENDING_CLAY_RULING`. Emit the reverse option commented adjacent for a one-line flip on ruling.
- **No DB apply** (no `psql` against staging or production, no Supabase `apply_migration`, no `drafts/scaffold/*.sql` execution) unless the session mission explicitly authorizes staging-DB write.
- **No live S-5 audit** against MG CIV / Tannerize / Porter working trees. Archive-scope S-5 was covered in `reports/TAX-15to16-DELTA.md`; the live sweep is operator-owned (v7.2 §24 L1643-1660).
- **No counsel-gated decisions.** §26 retention numbers, legal-disclaimer wording, or anything requiring counsel ratification is off-limits.
- **No modifications under `archive/`.** Stale content in `archive/` stands as provenance. Corrections go in new files outside `archive/`.

Scope rules full text: `AGENT-DISCIPLINE.md §5` (lines 82-90). Any path outside the declared workspace triggers a `SCOPE_CREEP_INFERRED` quarantine tripwire.

---

## 2. Session shape

Long-horizon work is overnight-session-shaped:

1. **Pre-flight.** Mission brief is read; branch is cut; tooling inventory is taken; path-sanity checks run. Output: a `PRE-FLIGHT-*.md` under `worktree-session/`.
2. **Proceed signal.** Operator replies `proceed` (or equivalent). No execution before the proceed signal.
3. **Phased execution.** `PHASE-1` (probe / inventory) → `PHASE-2-WAVE-N` (architect-dispatched parallel swarm, 2-3 parallel typical, 5 max) → `PHASE-3` synthesis on the main thread → `PHASE-4+` commit.
4. **No push, no PR.** The session commits to its feature branch and stops. The operator pushes and opens the PR.

Each phase appends to `worktree-session/SESSION-LOG-*.md`. Wave outputs land under `worktree-session/swarm-raw/`. Empirical example: `SESSION-LOG-REBUILD.md` (six phases, two waves, six swarm outputs).

---

## 3. Plan-mode + revise rounds

Architect operates in `DISCOVER → EXTRACT → VERIFY` modes with halt-and-await-approval gates between each (`.claude/agents/architect.md` lines 25-42). Apply the same discipline at session level: the operator reviews the plan before the architect executes. Tighten via **revise rounds** — the operator names specific constraints the architect folds into the next iteration.

**Empirical ceiling: ~7 tightenings.** The operator-review-package session reached exactly 7 tightenings before execution (`SESSION-LOG-REVIEW.md:47`). Beyond ~7, the plan is carrying more patches than original intent and should be re-plan-moded from scratch.

Examples of high-leverage tightenings in this repo:

- "12 roles, not 11" (v7.2 §13 line 1015-1028 canonical count).
- "I-6a/b/c live at §6 line 407-409, not §1."
- "`created_at` is BANNED in promotion `ORDER BY` (I-6b) but ALLOWED in `CREATE INDEX` and `CHECK` constraints."
- "Single-option memo bodies with the alternative in an HTML comment for one-line flip."

---

## 4. Scope rules

See `AGENT-DISCIPLINE.md §5` (lines 82-90). Full text binds. Summary:

- Reads outside declared workspaces require explicit operator authorization. No fishing in pre-Clay HTMLs, `archive/` content, or external repos without authorization.
- Edits to `producer/**`, `reports/**`, `binding/**`, `archive/**`, `al/**` are **forbidden** unless the session mission explicitly authorizes.
- Outputs go to declared workspaces: e.g. `worktree-session/swarm-raw/`, `drafts/scaffold/`, `.claude/rules/`. Any path outside → `SCOPE_CREEP_INFERRED`.
- No DB apply, no `git push`, no PR creation unless explicitly authorized.

Per-subsystem extensions at `.claude/rules/`: `producer-boundary.md`, `reports-readonly.md`, `scaffold-boundary.md`.

---

## 5. Worktree isolation

Feature work lands in a sibling worktree, not in the primary clone:

```
git worktree add ../Case-Database-<name> -b overnight/<task>-<date>
cd ../Case-Database-<name>
# session work happens here; session log at worktree-session/SESSION-LOG-<name>.md
```

Benefits:

- The primary clone stays on `main` and remains usable for unrelated operator work during long sessions.
- A failed session can be abandoned by deleting the worktree without touching the primary clone's working tree.
- Parallel sessions in different worktrees do not fight over the same index / HEAD.

**Parallel-agent cap.** 2-3 parallel sub-agents is the empirical sweet spot; 5 is the ceiling (`AGENTS.md`). The cautionary tale is commit `a67b557`, where over-parallelism led to merge conflict and lost work.

Unmerged branches stay unmerged until Chen-reviewed. Session working material lives at `worktree-session/` and merges with the PR for that branch.

---

## 6. The triple safety-net

Zero-Inference is enforced in practice through three overlapping stages:

### 6.1 Read-before-replace

The `Edit` tool errors if `Read` has not been called on the target file in the session. This is a Claude Code harness behavior, not a repo file. The discipline it supports is `AGENT-DISCIPLINE.md §1.2` rule 3: "Names are grep-verified" — you cannot grep-verify a name you did not read.

### 6.2 `grep-verifier` sub-agent

Skeptical one-shot claim validator that returns CONFIRMED / LIKELY / INDETERMINATE / FALSE POSITIVE verdicts with grep evidence. Historical AI-audit false-positive rate across tracked projects: **38-54 %** (`.claude/agents/grep-verifier.md` line 36-37; `.claude/agents/code-reviewer.md` line 33).

Rules (`grep-verifier.md` lines 40-56): never accept a claim without grep evidence, rate every finding, show your work, check the live path not dead code, watch for phantom bugs.

### 6.3 `chen` sub-agent adversarial review

Four focus modes (deep subsystem, finding expansion, spec-to-code delta, pre-launch failure). Labels: CONFIRMED / HYPOTHESIS / UNVERIFIED / DISPROVEN. Severity rubric observed in session commits: **BLOCKER / MAJOR / MINOR / NIT** (per `5d2e4c8`, `2e3fd63`, `dec9f3e`).

Track record in this repo:

- `2e3fd63` — 3 BLOCKERs + 3 MAJORs in scaffold-rebuild PR #4 (REVIEW-PR-3).
- `dec9f3e` — 10 MAJOR + 6 MINOR citation defects in operator review package PR #3 (REVIEW-PR-4).
- `5d2e4c8` — 8 MAJOR citation defects in prior reports (pre-PR-3 remediation).

**The three nets overlap enough to be robust and differ enough not to be redundant:** read-before-replace catches stale-state edits; grep-verifier catches individual-claim mismatches; Chen catches subsystem-level defects, spec-to-code drift, and pattern-level issues.

---

## 7. Zero-Inference Discipline

See `AGENT-DISCIPLINE.md §1`. Do not duplicate; reference.

Summary:

- Every value emitted in any output file (SQL, Markdown, JSON, code) is quoted verbatim from an authoritative source with a section + line cite. Never inferred.
- **Counts are reporting facts.** A delta between v1 (N values) and v7.2 (N+K values) documents that K extra values exist; it does not license inventing the extra K.
- **Names are grep-verified.** Every identifier (table name, column, ENUM value, ERRCODE, migration number, section number, role name) is grep-confirmed against v7.2 before emission.
- **"Claude's recommendation" in v7.2 is advisory.** Where v7.2 pairs a recommendation with a "Clay ruling required," draft per the recommendation and tag `<X>_PENDING`; emit the reverse option commented adjacent.
- **Silence is a gap, not a default** (`AGENT-DISCIPLINE.md §1.3`). Where v7.2 does not speak, log the silence inline (`-- v7.2 silent; chose <X> per minimal-assumption default`) and surface it for operator review.

The A-L category table in `AGENT-DISCIPLINE.md §3` (lines 49-62) enumerates the 12 highest-hallucination-risk surfaces with v7.2 cites. Row G = roles (12, v7.2 §13 line 1015-1028). Row H = event classes. Row I = invariants (§1 + §6 for I-6a/b/c).

**Cautionary tale.** A prior session hallucinated four `al_treatment_type` values by reading v1 (15 lowercase) against v7.2 (16 UPPERCASE) and counting the delta. The correct 16 live verbatim at v7.2 §12 line 960-967. The invented values were not in v7.2. See `AGENT-DISCIPLINE.md §1.1` + `.claude/rules/reports-readonly.md` line 21.

---

## 8. Sub-agent routing

| Sub-agent | Invoke for | File |
|---|---|---|
| `architect` | Multi-file decomposition, extraction plans, **swarm orchestration** (sole authority). | `.claude/agents/architect.md` |
| `chen` | Adversarial audits against merged or staged work. Spec-to-code delta. Pre-launch failure. | `.claude/agents/chen.md` |
| `code-reviewer` | Post-change diff review, single pass. HYBRID grep + GitNexus where available. | `.claude/agents/code-reviewer.md` |
| `grep-verifier` | Per-claim validation with grep evidence. Mid-session claim checking. | `.claude/agents/grep-verifier.md` |

Other sub-agents route swarm requests through architect; they do not swarm directly.

---

## 9. Commit conventions

Format:

```
<type>(<scope>): <summary> per <authority>

<body if needed>

Co-Authored-By: Claude <noreply@anthropic.com>
```

- `type` ∈ `{feat, fix, docs, chore, reorganize, refactor}`.
- `scope` names the subsystem slice: `scaffold`, `producer`, `reports`, `review-pkg`, `findings`, `session`, `phase-1a`, `reorg`, `rebuild-doc`, and similar.
- `per <authority>` cites the ratifying reference: `per v7.2 §24 R-2`, `per Chen REVIEW-PR-3`, `per §13 line 1015-1028`.

Empirical examples from `git log`:

- `fix(scaffold): resolve 3 BLOCKERs + 3 MAJORs per Chen REVIEW-PR-3`
- `fix(review-pkg): correct 10 MAJOR + 6 MINOR citation defects per Chen REVIEW-PR-4`
- `reorganize(pr-3): promote 4 operator docs to docs/operator/, archive session artifacts`
- `docs(session): log Phase 5 branch reconciliation in PHASE-5-STATUS`
- `producer: V1 pipeline port to v7.2 (L0-L3 cascade, 194 tests, 4 xfail)`

The `Co-Authored-By` trailer is standard when an agent contributed; observed variance includes `the role assigned to primary_reasoning` and bare `Claude`. Feature commits with dense bodies sometimes omit the trailer.

---

## 10. Session artifact conventions

| Path | Role | Retention |
|---|---|---|
| `worktree-session/` | Current session's logs, swarm-raw outputs, pre-flight reports. | Ephemeral within the session; merges with the PR. |
| `archive/session-artifacts/<date>-<name>/` | Historical session evidence post-archive. | Read-only after archive. |
| `docs/operator/` | Chen-verified operator reference material. | Ratified; maintain against v7.2 cites. |
| `drafts/scaffold/` | 15 SQL migrations + 11 test files + `REBUILD-MANIFEST.md`. | On `main`; execution material for staging apply. |
| `drafts/runbook/`, `drafts/remediation/` | Phase-1A execution material. | **Not on `main`.** Staged on `overnight/phase-1a-ready-2026-04-23` (local-only); lands at Phase-1A ratification. |
| `reports/` | Session investigation outputs. Read-only per `.claude/rules/reports-readonly.md`. | On `main`; historical. |

---

## 11. `.claude/rules/` template + when to add one

Each `.claude/rules/*.md` file is a per-subsystem path-scoped discipline file. Template: `.claude/rules/example-rule.md`. Shape:

- **`paths`** — glob block naming the paths this rule governs.
- **`DO NOT`** — bulleted prohibitions, each with rationale + v7.2 or authority cite.
- **Architecture Notes** — entry points, source-of-truth files, state-management flow.
- **Thresholds** — parameters with values + reasons (optional, when numeric limits apply).
- **Key Files** — two-column table (File | Role).

Existing rule files (per origin/main):

- `producer-boundary.md` — governs `producer/**`. Authority: v7.2 §3 Interpretation A, §11 line 739, §12 line 893, §29.
- `reports-readonly.md` — governs `reports/**`. Carries the four-hallucinated-types cautionary tale.
- `scaffold-boundary.md` — governs `drafts/scaffold/**`. Authority: v7.2 §20, §12, §24 plus Zero-Inference.
- `example-rule.md` — the template.

**Write a new rule when:** a subsystem acquires a code surface large enough that its DO-NOTs cannot fit inside a single paragraph of `AGENT-DISCIPLINE.md §5`, when multiple agents are likely to touch it, or when it carries a distinct authority lineage (e.g., a new MCP-surface rule once §15 read surface ships). BACKLOG.md line 70 tracks anticipated additions.

---

## 12. PENDING-EXPECTED discipline

**PENDING-EXPECTED is a pattern, not a file.** Items tagged `<X>_PENDING_*` in scaffold source (e.g., `N-2_PENDING_CLAY_CONFIRM`, `R-1_PENDING_CLAY_RULING`, `R-3_PENDING_CLAY_RULING`) are **ratified draft states**, not defects. Reviewers and sub-agents MUST NOT flag them as bugs.

The current instance-list for active work is `worktree-session/CHEN-FALSE-POSITIVES.md` (git `549a3ef`, 12 items enumerated). The canonical tag roster lives implicitly across `BACKLOG.md` lines 10-65 (every §24 / §29 item) and in the `-- PENDING:` tagged lines in `drafts/scaffold/*.sql` migration files.

**Examples of PENDING-EXPECTED currently in the repo:**

- R-1 Option B active at `drafts/scaffold/005_authority.sql:52` — Clay ratified 2026-04-23 by email; BACKLOG checkbox sync pending.
- R-3 option (a) active at `drafts/scaffold/008_derivation.sql:70` — Clay ratified 2026-04-23.
- N-2 trigger active at `drafts/scaffold/012_functions_triggers.sql:174`; application feature flag OFF until T-OV-1 passes.
- Migrations 013 DRAFT, 014 OUTLINE (stubs raise NI001-NI005 in 012), 015 NI-stub + CREATE TRIGGER commented per Chen A-BLOCKER-2.
- 4 strict xfails in producer V1 tests (F3, F5, F7, F8); prompts IMMUTABLE until these close.

If Chen or grep-verifier is about to flag any of these, reference the allowlist-pattern first.

---

## 13. If something is ambiguous

Halt and ask. Do not guess.

`AGENT-DISCIPLINE.md §1.3`: "Silence in v7.2 is a gap, not a default." If v7.2 is silent on a schema / invariant / taxonomy question, it is an open Clay ask; log the silence, surface it to the operator, do not emit a fabricated value.

If v7.2 is silent on a producer / models / cost / phase question, it is Porter's engineering call (v7.2 §3 Interpretation A); make the call explicit with rationale.

---

## 14. Pointers for human contributors

- **`docs/operator/README.md`** — map of the operator execution package.
- **`docs/operator/OPERATOR-REVIEW-CHECKLIST.md`** — per-migration review checklist.
- **`docs/operator/ROADMAP-TIER-A-TO-D.md`** — the 28-prerequisite roadmap.
- **`BACKLOG.md`** — what is open, by tier.
- **`AGENT-DISCIPLINE.md`** — the operational doctrine in full.
- **`.claude/agents/`** — sub-agent contracts (architect, chen, code-reviewer, grep-verifier).
- **`CHANGELOG.md`** — chronological repo history.
- **`SECURITY.md`** — schema guardrails + vulnerability reporting.

Authority: `binding/v7.2.md`. Discipline: `AGENT-DISCIPLINE.md`.
